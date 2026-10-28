# Making a release

How a new version gets from this folder onto a mat. Follow it in order; every step exists
because skipping it has gone wrong at least once.

Run everything from the project folder — the one holding `run.sh` and `latest.json`. Your
prompt should end with `\salaah-pi>`.

Every command below can be pasted exactly as it stands. The version is read out of the file
that holds it, so there is nothing to substitute and nothing to get wrong. `$v` is set in
step 1, **after** the new files are in place — not before.

> That used to be the first thing on this page, above step 1, and it was wrong. Step 1 is what
> changes the version, so anything read before it holds the OLD one. `sign_release.py` then
> refuses, quite correctly, because the address says one version and the build says another;
> it prints "Nothing has been built and nothing signed" and leaves the folder empty, and the
> next thing you see is a release with no zip to attach. Read `$v` after the files land, never
> before.

If you open a new PowerShell window part way through, run the `$v` lines from step 1 again.

---

## 0. Before you start

Clear the staging folder. It is the single most common way the wrong file gets attached:

```
Remove-Item -Recurse -Force ..\salaah-release -ErrorAction SilentlyContinue
```

Nothing is lost — anything that was in there is already on a release, or is superseded.

The `-ErrorAction SilentlyContinue` is there because the folder is often not there to delete,
and without it PowerShell answers a successful no-op with six lines of red. Which reads exactly
like something breaking, at the one point in this page where you most need to be able to tell.

## 0b. Check the changes zip actually makes a working app

Before anything else is done with a changes zip, lay it on top of the release the mat is
running now and start it:

```
python tools\check_changes_zip.py --base ..\salaah-1.49.zip --changes "$HOME\Downloads\salaah-1.53-changes.zip"
```

(`--base` is the zip off the last release the mat actually installed; `--changes` takes several,
in order, if more than one has gone out since.)

This step exists because versions 1.50, 1.51 and 1.52 all went out broken and none of them had
to. 1.51 renamed a keyword argument in two files, shipped one of them and not the other. Every
test passed, because the tests run against a folder where both files had been changed -- which
proves the working tree is consistent and says nothing at all about whether the files picked out
of it to be shipped are the complete set. The mat got the half of the change it was sent, died
on startup, and the guard put the old version back three times over without ever saying why.

Thirty seconds here. It must end with "It starts, and says it is N. The zips are complete."

## 1. Put the new files in place

If the changes arrived as a zip, unpack it **over** the project so each file walks itself into
the right folder:

```
$zip = Get-ChildItem "$HOME\Downloads\salaah-*-changes*.zip" | Sort-Object LastWriteTime | Select-Object -Last 1
$zip.Name
Expand-Archive -Path $zip.FullName -DestinationPath . -Force
```

Check the name it printed is the one you meant. Windows saves repeat downloads as `(1)`, `(2)`.

**Then read the version out of the file that now holds it, and check it landed:**

```
$v = ([regex]'"(.+)"').Match((Select-String '__version__' salaah\__init__.py).Line).Groups[1].Value
$v
git status
```

- `$v` must print the new version. If it still says the old one, the files did not arrive —
  and everything after this point would be built for the wrong version.
- `git status` must list the changed files. "working tree clean" means nothing was replaced —
  stop and find out why rather than carrying on.

The version number lives in `salaah/__init__.py` and nowhere else. Everything downstream reads
it from there: the zip's filename, the manifest, what the mat compares against.

## 2. Commit and push

```
git add -A
git commit -m "<what changed, in a line>"
git push
```

Push before anything else touches GitHub, so the repo and the release agree.

## 3. Build and sign

```
python tools\sign_release.py --out ..\salaah-release --url "https://github.com/ProntoHS/Mysalaah/releases/download/v$v/salaah-$v.zip"
```

Two things to read, not skim:

- It must print the version you saw above. If it refuses because the address does not match
  the build, the version and the URL disagree — fix whichever is wrong. Do not work around it.
- The **KEPT OUT** block must list your licensed translations. They are private use only, and
  this is the last point at which they can be stopped.

This uses your signing key at `C:\Users\haroo\.salaah\signing-key`. It never leaves the machine.
It is the one thing here that cannot be replaced: without it no mat will accept an update, and
every mat would need a new app installed by hand.

## 4. Create the release on GitHub

**Releases** → **Draft a new release**.

- Tag: print it and copy what it prints, rather than typing it:

  ```
  "v$v"
  ```

  Choose "Create new tag on publish". **Lowercase v**, and a real version — `vN` is the
  placeholder from this page, not a tag.
- Drag the zip from `..\salaah-release` into the **"Attach binaries by dropping them here"**
  area. **Not** the description box.
- Wait for the upload bar to finish.
- **Publish release** — not "Save draft".

Then check the page says **Assets 3**, with the zip listed *inside* the Assets section and a
file size beside it. Two means the zip is not attached.

## 5. Check it, before any mat does

```
python tools\check_release.py
```

This does exactly what a mat does, with the same code: verifies the signature, downloads the
zip from the address in the manifest, checks its hash and size, looks inside it, and refuses if
a licensed file got in.

It must end with **"A mat offered this would install version …"** naming the version you
expect.

Read the `url` line it prints. The version appears in it **twice** — once as the tag, once as
the file name — and both have to be right. `check_release.py` now says so before it downloads
anything, and `sign_release.py` refuses to sign an address that disagrees with the build, but
read it anyway.

If it fails, fix that first. Every failure here is one that would otherwise be found by a mat,
in somebody's home, with nothing on screen but a short apology.

## 6. Publish the manifest

This is the switch. Nothing before it changes what any mat sees.

```
copy ..\salaah-release\latest.json .
git add latest.json
git commit -m "Publish $v"
git push
```

Then confirm what mats are actually being told:

```
python tools\check_release.py --live
```

## 7. Update the mat

Settings → **Check for updates** → **Update now**.

The screen sits still for a few seconds while it downloads, then restarts itself and comes back
on the new version. Leave it a minute before touching anything: `run.sh` watches the first minute, and if the
new version will not start it puts the old one back without being asked.

---

## Things that have caught us

| Symptom | Cause |
|---|---|
| "the address does not match the version" | the tag or the file name in the `--url` is wrong — most often `vN` pasted from this page. Nothing was published; fix the address and sign again |
| "the zip is not at that address" | the zip is not downloadable: attached to the description instead of the assets, a capital `V` in the tag, a draft release, or an upload that never finished |
| "the download does not match what was promised" | a different build was uploaded than the one signed |
| Mat says "up to date" when it should not | `latest.json` was never pushed (step 6) |
| Version on the mat does not match its contents | `salaah/__init__.py` was not bumped before signing |
| Two zips in the staging folder | step 0 was skipped; one of them will get attached by mistake |
| Nothing in `..\salaah-release` to attach | `sign_release.py` refused and said so. Almost always `$v` holding the old version because it was read before step 1 put the new files in. Re-read `$v` and sign again |

## Build it in a clone, never in a folder you happen to have

**1.89 went out broken and the code was never the problem.** It is worth the whole of this
section because nothing in step 1 would have caught it, and step 0b said the zip was fine.

The changes were unpacked into a folder on the Desktop that was a git clone but whose working
tree held an **old copy of the app** -- sixteen files from an earlier era, sitting there
unnoticed. `git add -A` cannot tell "files I just added" from "files that have quietly reverted
by nineteen versions", so the commit took `ArrowButton` and `TextSize` out of `render.py`, took
410 lines out of `mosque.py`, 262 out of `reading.py`, 127 out of `passages.py`, and deleted
`audio.py` altogether. Then a correctly built, correctly signed release was made from it.

The mat downloaded it and died in under a second:

    ImportError: cannot import name 'ArrowButton' from 'salaah.render'

with `ArrowButton` plainly on line 53 of the `render.py` in the repository. The guard rolled it
back three times and the mat never showed a thing. It was published as 1.90 in the end, because
the v1.89 tag already had the broken zip on it and replacing an asset under an existing tag
means the CDN can serve the old bytes against a freshly signed hash -- which the mat refuses,
correctly, in a way that looks like a different fault entirely.

So:

- **Unpack changes into a fresh clone**, not into a folder that has been on the Desktop for
  nineteen versions. `git clone` into a path that already exists refuses with
  `destination path ... already exists and is not an empty directory` -- read that line. It
  means every command after it ran somewhere you did not choose.
- **`git status` saying "working tree clean" after unpacking is not reassurance**, it is the
  alarm. Step 1 says so. It can also mean the tree was committed earlier in a state nobody
  checked.
- **Read `git diff --stat` before committing.** A release that adds two games should not be
  deleting a thousand lines from six files you never opened. One look at the `-` column says
  more than any test.

## Files left behind on mats

A changes zip **adds and replaces; it never deletes**. A picture or a film taken out of the tree
stays on every mat that already has it, for good, unless somebody removes it by hand. None of
them does any harm -- nothing reads them -- but they sit there taking up card, and a stray
`wudu.png` in `assets/children` is exactly the sort of thing that misleads whoever next reads
the folder trying to work out what the menu is made of.

So the list, newest first. On the Pi, in the app folder:

    rm salaah/game.py salaah/kaaba_jigsaw.py
    rm -rf salaah/__pycache__
    rm assets/knowledge/wudu.png assets/knowledge/kalima.png assets/knowledge/nasheeds.png
    rm assets/children/wudu.png

**1.97** retired two game modules, which is the first time this list has had code on it rather
than pictures:

- `salaah/game.py` -- the Prayer-Time Sky. Its tile now opens Prayer Day Journey, which asks
  the same question with a drawing of each sky instead of a list of words.
- `salaah/kaaba_jigsaw.py` -- replaced by `salaah/journey_jigsaw.py`, which has five pictures
  rather than one and three sizes rather than nine fixed pieces.

Nothing imports either, so a mat that keeps them runs correctly; they are inert. The
`__pycache__` line is there because a compiled copy of each will also be sitting beside them,
and deleting the source while leaving the bytecode is the stale-bytecode trap in reverse --
harmless here, since nothing imports them, but confusing to whoever next looks.

Their strings went too: the fifteen `game.*` and `jigsaw.*` keys were taken out of all nine
language packs, so a mat that still has the modules has nothing to draw them with. That is the
right way round. An orphan module is tidier than an orphan vocabulary nobody can audit.

**1.89** took all four out of the tree:

- `assets/knowledge/wudu.png` -- the main menu's Wu'du tile, gone since 1.88 when Children took
  its square. Wu'du is now one press behind Knowledge, which has its own drawing in
  `assets/knowledge-menu`.
- `assets/knowledge/kalima.png`, `assets/knowledge/nasheeds.png` -- the six kalima moved to the
  du'a menu, and Nasheeds became Radio at 1.70. Both stills outlived their tiles by nineteen
  versions.
- `assets/children/wudu.png` -- the children's menu is eleven games at 1.89 and has no Wu'du
  tile on it at all.

The other eight stills in `assets/knowledge` were **replaced**, not removed: the main menu went
from eight tiles in four rows to ten in five, so every box is a different shape and all ten
stills were recut from the new film. Those arrive in the zip like any other changed file.

## When `run.sh` changes

`run.sh` is **not** in the zip, and an update never replaces it. That is deliberate: it is the
guard that puts the old version back when a new one will not start, so a bad release must not be
able to break it.

The cost is that a change to it has to go onto each mat by hand, once. On the Pi, in the app
folder, with the app closed:

```
curl -L -o run.sh https://raw.githubusercontent.com/ProntoHS/Mysalaah/main/run.sh
chmod +x run.sh
grep -c "while true" run.sh
```

That last line must print at least 1. If it prints 0, GitHub's cache is still serving the old
file — wait a couple of minutes and pull it down again. Push to GitHub before you curl, or you
will fetch the version you are trying to replace.
