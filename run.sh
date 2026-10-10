#!/bin/bash
# Starts the prayer app. Options: --windowed (not full screen), --cursor (show the mouse pointer)
#
# This script is also the guard for updates, which is why an update never replaces it. A newly
# installed version is put "on trial": it has to run for a minute before the app marks it good.
# If it crashes before then, or is started twice without ever settling, this puts the previous
# version back on its own.
#
# The putting-back is done here in plain shell, and deliberately does NOT call into the app.
# The whole point of the guard is that it still works when the installed version is broken, and
# code from a broken version cannot be trusted to undo its own installation.
#
# To take the guard out of the picture, start it with SALAAH_NO_GUARD=1.
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi

STATE="update-state.json"
REPLACED="salaah assets"          # must match REPLACES in salaah/update.py

# These read and write the state file with nothing but json, so they keep working when the app
# itself does not.
on_trial() {
    [ -f "$STATE" ] || return 1
    "$PY" -c 'import json,sys
try: sys.exit(0 if json.load(open(sys.argv[1])).get("trial") else 1)
except Exception: sys.exit(1)' "$STATE"
}

attempts() {
    "$PY" -c 'import json,sys
try: print(int(json.load(open(sys.argv[1])).get("attempts", 0)))
except Exception: print(0)' "$STATE" 2>/dev/null || echo 0
}

count_attempt() {
    "$PY" -c 'import json,os,sys
path = sys.argv[1]
try: state = json.load(open(path))
except Exception: raise SystemExit(0)
state["attempts"] = int(state.get("attempts", 0)) + 1
open(path + ".tmp", "w").write(json.dumps(state, indent=2))
os.replace(path + ".tmp", path)' "$STATE" 2>/dev/null
}

put_the_old_one_back() {
    echo "salaah: the new version did not settle; putting the previous one back" >&2
    local ok=1
    for name in $REPLACED; do
        [ -d "$name.prev" ] || ok=0
    done
    [ "$ok" = 1 ] || { echo "salaah: nothing to go back to" >&2; return 1; }
    for name in $REPLACED; do
        rm -rf "$name.failed"
        [ -e "$name" ] && mv "$name" "$name.failed"
        mv "$name.prev" "$name"
        rm -rf "$name.failed"
    done
    "$PY" -c 'import json,os,sys,time
path = sys.argv[1]
try: state = json.load(open(path))
except Exception: state = {}
out = {"rolled_back_from": state.get("trial", ""), "at": time.time()}
open(path + ".tmp", "w").write(json.dumps(out, indent=2))
os.replace(path + ".tmp", path)' "$STATE" 2>/dev/null
    return 0
}

# The app is started in a loop, because two things need it started again without anyone here to
# do it: an update that has just been installed, and a version that has been put back after a
# bad one. Everything else -- closing the app, Ctrl+Q -- exits cleanly and stops the loop.
RESTART=42                        # must match RESTART in salaah/update.py
restarts=0

# Starting again after an ordinary crash -- not an update, not a rollback, just the app falling
# over while somebody is using it. Before this the mat was left on the desktop until a person
# came and started it again, which on a prayer mat in a hall is the whole thing broken.
#
# Two numbers keep that from becoming a flicker loop. A run that lasted at least SETTLED
# seconds counts as "it was working", so the count starts over: a mat that has been up all day
# and falls over at midnight gets its restarts, however many days that goes on. A run shorter
# than that is a crash on startup -- broken artwork, a missing file -- and after CRASH_TRIES of
# them in a row this stops and leaves the error on screen, because a mat that restarts five
# times a second tells nobody anything and a visible error can be read out over the phone.
# Both can be set in the environment, which is how the tests exercise this without sitting
# through twenty seconds a run, and how a mat that turns out to need different numbers can be
# told so without editing the guard.
CRASH_SETTLED=${SALAAH_CRASH_SETTLED:-20}   # seconds up that counts as having worked
CRASH_TRIES=${SALAAH_CRASH_TRIES:-5}        # quick crashes in a row before giving up
CRASH_LOG="crash-log.txt"
crashes=0

note_crash() {
    # Kept because the traceback scrolls away when the app starts again, and then there is
    # nothing at all to say what happened. Trimmed so it cannot grow for ever on a mat nobody
    # looks at.
    printf '%s  exit %s after %ss up\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2" >> "$CRASH_LOG"
    tail -n 50 "$CRASH_LOG" > "$CRASH_LOG.tmp" 2>/dev/null && mv "$CRASH_LOG.tmp" "$CRASH_LOG"
}

while true; do
    if [ -z "$SALAAH_NO_GUARD" ] && on_trial; then
        if [ "$(attempts)" -ge 1 ]; then
            put_the_old_one_back        # started before and never settled: it is not going to
        else
            count_attempt
        fi
    fi

    began=$SECONDS
    "$PY" -m salaah "$@"
    code=$?
    ran=$((SECONDS - began))

    # An update has been installed and wants the new version running.
    if [ "$code" -eq "$RESTART" ]; then
        restarts=$((restarts + 1))
        if [ "$restarts" -le 5 ]; then
            continue
        fi
        # Something is asking to restart over and over. Treat it as a failure so the guard
        # below puts the previous version back, rather than spinning here for ever.
        echo "salaah: asked to restart too many times; treating it as a failure" >&2
        code=1
    fi

    # A version built before that code existed stands down with an ordinary clean exit after
    # installing an update, so the exit code alone cannot be relied on. The state file says what
    # happened regardless: a version on trial that has never been started means the app has just
    # installed it and bowed out. Start it rather than leaving the mat on the desktop.
    #
    # This deliberately does not fire when the trialled version HAS been started -- then a clean
    # exit is somebody closing the app, and closing the app must close it.
    if [ "$code" -eq 0 ] && [ -z "$SALAAH_NO_GUARD" ] && on_trial \
       && [ "$(attempts)" -eq 0 ]; then
        restarts=$((restarts + 1))
        if [ "$restarts" -le 5 ]; then
            continue
        fi
    fi

    # Died before settling. Put the old one back and start that, rather than leaving a dark mat.
    if [ "$code" -ne 0 ] && [ -z "$SALAAH_NO_GUARD" ] && on_trial; then
        if put_the_old_one_back; then
            continue
        fi
    fi

    # Crashed, and not because of an update. Start it again.
    #
    # After the rollback above on purpose: a version on trial that falls over is a bad update
    # and wants the old one back, not the same broken one over and over. By the time it gets
    # here either it is not on trial or there was nothing to go back to.
    if [ "$code" -ne 0 ] && [ -z "$SALAAH_NO_GUARD" ]; then
        note_crash "$code" "$ran"
        if [ "$ran" -ge "$CRASH_SETTLED" ]; then
            crashes=0               # it had been running; this is not a startup crash
        fi
        crashes=$((crashes + 1))
        if [ "$crashes" -le "$CRASH_TRIES" ]; then
            echo "salaah: exited with $code after ${ran}s; starting it again" \
                 "($crashes of $CRASH_TRIES)" >&2
            sleep 2                 # not a strobe, and a moment for whatever it was to clear
            continue
        fi
        echo "salaah: $crashes crashes in a row, none lasting ${CRASH_SETTLED}s." \
             "Leaving it down so the error can be read. See $CRASH_LOG." >&2
    fi
    exit "$code"
done
