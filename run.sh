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

if [ -z "$SALAAH_NO_GUARD" ] && on_trial; then
    if [ "$(attempts)" -ge 1 ]; then
        put_the_old_one_back            # started before and never settled: it is not going to
    else
        count_attempt
    fi
fi

"$PY" -m salaah "$@"
code=$?

# Died before settling. Put the old one back and start that, rather than leaving a dark mat.
if [ "$code" -ne 0 ] && [ -z "$SALAAH_NO_GUARD" ] && on_trial; then
    if put_the_old_one_back; then
        exec "$PY" -m salaah "$@"
    fi
fi
exit "$code"
