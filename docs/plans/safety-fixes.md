# Plan: safety-fixes

## What Sean asked for

"maintained copy, start the safety-fix job". This copy is now maintained here,
and the safety fixes from the 2026-11-27 repository review go first.

## What we found

- The script is still identical to the original project's v1.4.22. The review
  found five safety problems in how it downloads and installs packages as
  root, and in how it updates itself.
- Draft PR #3 already fixes some of them: the certificate check, failed
  downloads, downloading before uninstalling, and losing options after an
  update. But it mixes those fixes with untested new features, and it still
  reuses files left in `/tmp`. We'll copy the fixes across by hand and leave
  PR #3 alone.
- Synology doesn't publish checksums for these packages. We downloaded the
  three x86_64 files with the certificate check on. Their SHA-256 values match
  the one PR #3 already recorded for Video Station.
- The repository can't be tested on a Synology here. Tests run on this
  computer against stand-in versions of the Synology commands, inside a
  throwaway Linux container with no network.

## What we'll change

All script changes are in `videostation_for_722.sh`.

1. **Check packages are genuine before installing them.**
   - Turn the HTTPS certificate check back on (remove `curl -k`), and allow
     HTTPS only, even after a redirect.
   - Download each package file once for every CPU type the script supports
     (21 files, about 254 MB, public downloads, no sign-in), and write their
     SHA-256 values into the script.
   - Check every download against its value. A file without a value, or with
     the wrong value, is deleted. The script then tries the next download
     server and stops with an error if none works.
   - There is no switch to skip the checks.
   - *Checked by:* tests that a wrong file, a missing value and a `-k`
     download are all refused, and that every recorded value matches the
     downloaded file (`sha256sum`, also cross-checked against a second
     download server).
2. **Use a private download folder for each run.**
   - Each run creates its own folder with `mktemp -d`, readable only by root,
     downloads into it, installs from it, and deletes it on exit.
   - A package file already lying in `/tmp` is never used.
   - *Checked by:* a test that plants a fake package in `/tmp` and confirms it
     is ignored, and that the folder is gone afterwards.
3. **Treat a failed or partial download as a failure.**
   - Check curl's result as well as the checksum; delete partial files.
   - Messages say which check failed. A certificate error says to check the
     NAS's date and time and update DSM, and that nothing was changed.
   - *Checked by:* a test where every server fails stops with exit code 3,
     and nothing is installed or uninstalled.
4. **Download everything before changing anything.**
   - New order: choose packages, then work out what's needed without changing
     anything, then download and check every package, then edit the version
     limits, then uninstall, then install.
   - If a download fails, the NAS is left exactly as it was.
   - The menu choices (all / no Video Station / no Media Server / codecs
     only) still pick the same packages as today.
   - *Checked by:* a test that every download happens before the first
     settings edit or uninstall, for each menu choice.
5. **Turn off the self-updater.**
   - Remove the part that downloads a new version of the script from GitHub
     and runs it as root without checking it. Its "forgets your options" bug
     goes with it.
   - Point the script's project link at this repository.
   - Give this copy its own version, `v1.4.22-hbt.1`, so it can't be mistaken
     for the original.
   - Users update by downloading a new copy by hand.
   - *Checked by:* a test that the script never contacts the GitHub API and
     never restarts itself.
6. **Tests and notes.**
   - Add `tests/` with the stand-in Synology harness, adapted from PR #3's
     download and install-flow tests, covering steps 1-5.
   - Add a `CHANGES.txt` entry, and a short README note that this copy has
     these safety changes and no self-updater.
   - *Checked by:* `bash -n`, `shellcheck`, and the test suite in a Linux
     container with no network.

**How this work is done on GitHub.** Commits on this branch are made under
the HoneyBearTech Homelab Automation app's name
(`honeybeartech-homelab-automation[bot]`), each one signed off. They're pushed
through the app, and this PR is opened by the app, so Sean can approve it with
a normal review. This is set per commit; the machine's git settings don't
change.

## Who's on it

Research (done), engineering, testing, a security review, an independent code
review, and a final plain-English check of the report.

## Risks

- None of this has run on a real NAS. Before trusting it, run it once on a
  NAS with codecs only (`--install=onlyamc`). That is the lowest-risk choice.
- If the NAS's certificate store is very old, downloads will now stop with an
  error, where before they went through unchecked. That is on purpose.
- Whether DSM's installer works from a root-only folder is unproven. That's
  the first thing to look at on the NAS.
- The checksums record the files as Synology serves them today. If Synology
  ever changes a file, the script will refuse it until the value is updated.
- Downloading everything first still isn't a full undo. If an install fails
  after the old package was removed, that package is still gone.
- PR #3 will conflict with this change, and will need rebasing or splitting
  later.

## Out of scope

- PR #3's new features (choosing the install volume, REST subtitles).
- The other review findings:
  - the scheduler guide's `install=` typo;
  - exit codes for bad options;
  - package start/stop timeouts;
  - the options that do nothing;
  - the yearly workflow;
  - the Renovate notes.

  They stay on the roadmap.
- Repository settings, workflows, and the governance files (security policy,
  contribution guide, badge).
