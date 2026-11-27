# Roadmap

What's planned for this copy of Video_Station_for_DSM_722, and what's done.
What shipped is in the [pass map](pass-map.md); the reasons are in the
[decisions log](decisions-log.md).

## Done

- 2026-11-20: Renovate merges its own pull requests (#4).
- 2026-11-27: Whole-repository review
  ([report](reports/2026-11-27-repo-review.md)).
- 2026-11-27: Owner chose a maintained copy.
- 2026-11-27: Script safety fixes, `v1.4.22-hbt.1` (#7): checked downloads,
  a private download folder, failed downloads stop the script, everything is
  downloaded first, and the self-updater is removed.

## In progress

- 2026-11-27: Draft PR #3's two features rebuilt on current `main`, as two
  drafts that wait for NAS tests:
  - install volume, `--volume=/volumeN`, `v1.4.22-hbt.2` (#8);
  - optional REST subtitle plugin (#9).

  #8 also makes bad options stop with exit code 2, and fixes the scheduler
  guide's `install=` typo.

## Waiting on the owner

- Run `v1.4.22-hbt.1` once on a real NAS, codecs only first
  (`--install=onlyamc`). Check that downloads pass the certificate check and
  that DSM installs from the private folder.
- Run the NAS checks in `docs/plans/pr3-rebase.md`, then mark #8 and #9
  ready and merge them. Whichever merges second needs a one-line fix in
  `CHANGES.txt`. For the volume check, write down whether DSM says an
  installed package "is occupied", and whether `chmod go-w` works on an
  ACL shared folder.
- Close draft PR #3 (replaced by #8 and #9). Its branch is kept.

## Next

- Optional: carry over PR #3's read-only package-settings inspector
  (`scripts/inspect-package-settings.sh`) as a small separate change.
- Tag a first release of this copy, so the README can link to releases.
- Check settings-file edits and package start/stop timeouts (bad options
  already exit 2 with #8).

## Repository upkeep

- Add a security policy and turn on private vulnerability reporting; give bug
  reports somewhere to go (Issues are off).
- Run the standard repository bootstrap (contribution guide, code of conduct,
  OpenSSF badge, and a check on pull requests that runs `shellcheck` and the
  `tests/` suite in the image with `jq` and PHP). PR #3's contribution guide,
  pre-commit config and `.gitignore` are a starting point.
- Year workflow: pin `actions/checkout` by commit, add top-level
  `permissions`, skip the commit when nothing changed, and work with the
  branch rule (or remove the workflow).
- Correct the Renovate notes ("once every check passes" vs `ignoreTests`), and
  check that Renovate can see the repository (no update PR for
  `checkout@v3` yet).
- README: warn about the third-party one-line installer, and say that the
  installed packages no longer get updates and how to undo that.
