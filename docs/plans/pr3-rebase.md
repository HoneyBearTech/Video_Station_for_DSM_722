# Plan: pr3-rebase

## What Sean asked for

"start the PR #3 rebase job". Carry draft PR #3's two new features over onto
today's `main`, which now has the safety fixes (#7), and keep only those
features.

## What we found

- PR #3 is a single commit made before the safety fixes. About half of its
  script changes are older versions of things `main` now does better: checked
  downloads, a private download folder, downloading first, and the
  self-updater. Those parts are dropped. A straight rebase would bring the old
  code back, so the features are copied across by hand.
- **Install volume** (`--volume=/volumeN`): lets you choose which volume the
  packages are installed on. It uses a DSM web service that has never been
  tried on a real NAS, and it only runs after the old packages have been
  removed. If it fails at that point, the package is left uninstalled.
- **REST subtitles**: an optional replacement for Video Station's
  OpenSubtitles plugin, with its own setup and restore script. It doesn't
  touch the install script at all. It verifies HTTPS certificates and keeps
  the API key in a file only the plugin's group can read. One bug was found
  by reading the code: after a Video Station update, neither restore nor
  reinstall would work.
- With PR #3's new files placed on `main`, all 56 tests pass, once the test
  container also has `jq` and PHP (the volume and subtitle tests need them).

## What we'll change

Two pull requests, one per feature. They need different tests on the NAS,
and one shouldn't hold up the other. Both open as **drafts** and are only
merged after the NAS checks listed below.

**PR A: install volume** (branch `team/pr3-rebase`, which also holds this
plan)

1. **Add the `--volume=/volumeN` option to the install script.**
   - Copy over PR #3's `lib/package_volume.sh`.
   - Wire it into `main`'s current flow: install from the private download
     folder, and keep every checksum and order rule.
   - Without `--volume`, nothing changes.
   - *Checked by:* tests that the right volume and the private-folder file are
     passed to the installer, and that a normal run is unchanged.
2. **Check the volume before changing anything.**
   - Before any download, confirm the volume is mounted, writable and offered
     by DSM.
   - Where DSM can answer, also ask it whether each package can be installed
     there, before anything is removed.
   - If it fails after a package was removed, say exactly what was removed and
     how to rerun without `--volume`.
   - *Checked by:* tests that a bad volume stops with nothing downloaded or
     changed, and that a late failure gives that message and a non-zero exit
     code.
3. **Stricter option handling** (from PR #3, needed so a mistyped option
   can't silently install to the wrong place):
   - bad or extra options stop with exit code 2;
   - `-t`/`--trace` works;
   - the options that did nothing are removed.
   - Also fix the scheduler guide's `install=` typo (it must be `--install=`).
   - *Checked by:* argument tests, ported from PR #3.
4. **Notes.**
   - Add `docs/package-volume.md`, updated for the private folder and stating
     the "removed then failed" risk plainly.
   - Add a README section and the option to the usage text.
   - Set the script version to `v1.4.22-hbt.2`, with a `CHANGES.txt` entry.

**PR B: REST subtitles** (branch `team/pr3-rebase-subtitles`, built on this
plan)

5. **Add the subtitle plugin and its setup script** as PR #3 has them:
   - `subtitle_plugins/opensubtitles_rest/`;
   - `scripts/install-subtitle-plugin.sh`.

   Plus these fixes:
   - Restore and reinstall must work after a Video Station update has
     replaced the plugin folder.
   - The docs say which details leave the NAS: the video's file name and a
     fingerprint of the file are sent to OpenSubtitles when searching.
   - The docs say that Video Station passes the sign-in details to the
     plugin itself.
   - *Checked by:* PR #3's subtitle tests, plus a new test for the
     after-update case.
6. **Notes.** Add `docs/subtitle-compatibility.md`, a README section and a
   `CHANGES.txt` entry. The install script and its version don't change.

**Both PRs**

7. **Test container.**
   - Tests that need `jq` or PHP are skipped (and say so) when those are
     missing, rather than failing.
   - The full test command, using a small container image with `jq` and PHP
     added, goes in the test notes.
   - *Checked by:* the suite passes both in the plain container and in the
     full one.

**Left out on purpose:**
- the package-settings inspector script (a separate small item);
- PR #3's contribution guide, pre-commit config and `.gitignore` (these go
  to the repository bootstrap job);
- whitespace-only edits;
- its combined `docs/compatibility.md` (its NAS checklist moves into the two
  feature docs).

**PR #3.** Once both new PRs are open, we'll close it with links to them and
a list of what was left out. Its branch is kept.

**How this work is done on GitHub.** The same way as #7:
- commits are made under the HoneyBearTech Homelab Automation app's name, set
  per commit and signed off;
- they're pushed through the app, and the app opens the PRs.

## NAS checks before either PR is merged

Back up first, and note the model, CPU and DSM version.

- **First, for both:** `--install=onlyamc` without `--volume`. This is
  still the first real-NAS test of `v1.4.22-hbt.1`.
- **Volume:**
  - a fresh `--install=onlyamc --volume=/volume2` lands in
    `/volume2/@appstore` and starts;
  - then all three packages, a reboot, and playing a video (including HEVC);
  - replacing the v4 codec pack;
  - a missing, read-only or unlisted volume stops with nothing changed;
  - a rerun, and a scheduled-task run;
  - Package Center's default volume is unchanged.
- **Subtitles:**
  - the plugin can read its key;
  - DSM's PHP has cURL and working certificates;
  - sign in from Video Station's settings (including a long password);
  - search, download and play a subtitle;
  - the password doesn't show in logs;
  - `--restore` brings the original back, including after a Video Station
    update.

## Who's on it

Research (done), two engineers (one per PR, on separate files), testing, a
security review and an independent code review covering both PRs, and a
final plain-English check.

## Risks

- The volume feature depends on a DSM web service whose requests and replies
  have only been seen in stand-ins. The early check reduces the "removed then
  failed" risk, but may not remove it: DSM may not answer for a package that's
  still installed.
- Packages already at the right version stay on their current volume, so
  packages can end up split across volumes. The docs will say so.
- Whether DSM's installer can read files from the root-only download folder
  is still unproven. The first NAS test above settles it.
- The subtitle API key is readable by the plugin's group. That's needed for
  Video Station to use it.
- The two PRs both edit the README and `CHANGES.txt`, so whichever merges
  second may need a small conflict fix.

## Out of scope

- The settings inspector, the governance files and other roadmap items.
- Any change to repository settings or workflows.
- Merging before the NAS checks pass.
