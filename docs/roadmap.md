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

## Waiting on the owner

- Run `v1.4.22-hbt.1` once on a real NAS, codecs only first
  (`--install=onlyamc`). Check that downloads pass the certificate check and
  that DSM installs from the private folder.

## Next

- Draft PR #3: rebase it onto these fixes and keep only its new features
  (install volumes, REST subtitles), to land after a test on a NAS.
- Fix `how_to_run_from_scheduler.md` (`--install=`, not `install=`).
- Tag a first release of this copy, so the README can link to releases.
- Make failures return a non-zero exit code; check settings-file edits and
  package start/stop timeouts.

## Repository upkeep

- Add a security policy and turn on private vulnerability reporting; give bug
  reports somewhere to go (Issues are off).
- Run the standard repository bootstrap (contribution guide, code of conduct,
  OpenSSF badge, and a check on pull requests that runs `shellcheck` and the
  `tests/` suite).
- Year workflow: pin `actions/checkout` by commit, add top-level
  `permissions`, skip the commit when nothing changed, and work with the
  branch rule (or remove the workflow).
- Correct the Renovate notes ("once every check passes" vs `ignoreTests`), and
  check that Renovate can see the repository (no update PR for
  `checkout@v3` yet).
- README: warn about the third-party one-line installer, and say that the
  installed packages no longer get updates and how to undo that.
