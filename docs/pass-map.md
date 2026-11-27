# Pass map

A short record of each piece of work on Video_Station_for_DSM_722: what shipped,
or what a review found, and where to look. Newest first. The reasons behind the
choices are in the [decisions log](decisions-log.md).

## 2026-11-27: `safety-fixes`

Script safety fixes, version `v1.4.22-hbt.1` (#7):
- HTTPS certificate check on, HTTPS only, and `curl` ignores `.curlrc`.
- Every package file is checked against a pinned SHA-256 (21 files, one per
  package and CPU type).
- A private download folder for each run, and never a file already in `/tmp`.
- A failed or partial download stops the script before any change (exit 3).
- Everything is downloaded before the version limits are edited or anything
  is uninstalled.
- Each install re-checks the live package state, and the script stops if an
  uninstall didn't work.
- Self-updater removed.
- Install links in the README point here.
- New `tests/` with stand-in Synology commands (25 tests, run in an offline
  container).

Not yet run on a real NAS.

## 2026-11-27: `repo-review`

Whole-repository review of `main`; nothing changed. The script matches the
original project's v1.4.22. Top findings: packages downloaded without a
certificate check or checksum and installed as root, files already in `/tmp`
reused, the self-updater unverified and pointed at the original project, failed
downloads counted as success, packages removed before replacements download,
and no way to report a security problem. Draft PR #3 already covers some of
this. Full report: [reports/2026-11-27-repo-review.md](reports/2026-11-27-repo-review.md).

## 2026-11-20: `renovate-automerge`

Renovate merges its pull requests itself once every check passes, majors
included; new versions wait 3 days, security fixes and image rebuilds don't.
Nothing kept manual. `platformAutomerge` is false and `ignoreTests: true`: no
checks run on pull requests (its only workflow uses no secrets). (#4)
