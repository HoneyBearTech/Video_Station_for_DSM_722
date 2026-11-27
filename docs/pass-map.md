# Pass map

A short record of each piece of work on Video_Station_for_DSM_722: what shipped,
or what a review found, and where to look. Newest first. The reasons behind the
choices are in the [decisions log](decisions-log.md).

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
