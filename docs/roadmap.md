# Roadmap

What's planned for this copy of Video_Station_for_DSM_722, and what's done.
What shipped is in the [pass map](pass-map.md); the reasons are in the
[decisions log](decisions-log.md).

## Done

- 2026-11-20: Renovate merges its own pull requests (#4).
- 2026-11-27: Whole-repository review
  ([report](reports/2026-11-27-repo-review.md)).

## Waiting on the owner

- Decide whether this is a maintained copy or a plain mirror of the original
  project. Most items below depend on it.

## Next (if maintained)

- Script safety fixes, in one small change:
  - turn the HTTPS certificate check back on;
  - download into a private folder and never reuse an existing file;
  - treat a failed or partial download as a failure;
  - download everything before removing any package;
  - keep the original options across a self-update.
- Point the self-updater at this repository, or turn it off.
- Split draft PR #3: the safety fixes first, and the new features (install
  volumes, REST subtitles) after a test on a NAS.
- Fix `how_to_run_from_scheduler.md` (`--install=`, not `install=`) and say
  in the README that this is a modified copy.
- Make failures return a non-zero exit code; check settings-file edits and
  package start/stop timeouts.

## Repository upkeep

- Add a security policy and turn on private vulnerability reporting; give bug
  reports somewhere to go (Issues are off).
- Run the standard repository bootstrap (contribution guide, code of conduct,
  OpenSSF badge, lint check on pull requests).
- Year workflow: pin `actions/checkout` by commit, add top-level
  `permissions`, skip the commit when nothing changed, and work with the
  branch rule (or remove the workflow).
- Correct the Renovate notes ("once every check passes" vs `ignoreTests`), and
  check that Renovate can see the repository (no update PR for
  `checkout@v3` yet).
- README: warn about the third-party one-line installer, and say that the
  installed packages no longer get updates and how to undo that.
