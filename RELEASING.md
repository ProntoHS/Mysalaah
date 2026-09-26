# Making a release

How a new version gets from this folder onto a mat. Follow it in order; every step exists
because skipping it has gone wrong at least once.

Run everything from the project folder — the one holding `run.sh` and `latest.json`. Your
prompt should end with `\salaah-pi>`.

Every command below can be pasted exactly as it stands. The version is read out of the file
that holds it, so there is nothing to substitute and nothing to get wrong. Do this first, in
the project folder, and check that it prints the version you expect:

```
$v = ([regex]'"(.+)"').Match((Select-String '__version__' salaah\__init__.py).Line).Groups[1].Value
$v
```

`$v` then stands for that version for the rest of the session. If you open a new PowerShell
window, run those two lines again.

---

## 0. Before you start

Clear the staging folder. It is the single most common way the wrong file gets attached:

```
Remove-Item -Recurse -Force ..\salaah-release
```

Nothing is lost — anything that was in there is already on a release, or is superseded.

## 1. Put the new files in place

If the changes arrived as a zip, unpack it **over** the project so each file walks itself into
the right folder:

```
$zip = Get-ChildItem "$HOME\Downloads\salaah-*-changes*.zip" | Sort-Object LastWriteTime | Select-Object -Last 1
$zip.Name
Expand-Archive -Path $zip.FullName -DestinationPath . -Force
```

Check the name it printed is the one you meant. Windows saves repeat downloads as `(1)`, `(2)`.

**Then verify it landed, before anything else:**

```
Select-String "__version__" salaah\__init__.py
git status
```

- The version must be the new **N**. If it still says the old one, the files did not arrive.
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

- Tag: type **`v`** followed by the version — **lowercase v**, e.g. `v1.18`. Choose "Create new
  tag on publish".
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
expect. If the address it prints contains anything that is not a real version number, stop.

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
on N. Leave it a minute before touching anything: `run.sh` watches the first minute, and if the
new version will not start it puts the old one back without being asked.

---

## Things that have caught us

| Symptom | Cause |
|---|---|
| "nothing has been published to update to yet" | the zip is not downloadable: attached to the description instead of the assets, a capital `V` in the tag, a draft release, or an upload that never finished |
| "the download does not match what was promised" | a different build was uploaded than the one signed |
| Mat says "up to date" when it should not | `latest.json` was never pushed (step 6) |
| Version on the mat does not match its contents | `salaah/__init__.py` was not bumped before signing |
| Two zips in the staging folder | step 0 was skipped; one of them will get attached by mistake |

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
