# Decisions log

Why things are the way they are: each entry gives the decision, the reason and
what was turned down. Newest first. What shipped is in the [pass
map](pass-map.md).

## 2026-11-27: Review only; next steps left to the owner

Job `repo-review`.

**Decision.** Record the review and change nothing. The recommended next step
is to keep this as the owner's own maintained copy and land the safety fixes
first (certificate checks, a private download folder, real download-failure
handling, download before uninstall, keep options across an update), with the
self-updater pointed at this repository or turned off. Draft PR #3's new
features wait for a test on a NAS.

**Why.** The script is identical to the original project's latest release, so
every script problem is shared with it. Any fix made here would be overwritten
by the original project's next release while the self-updater points there.
Whether to maintain a copy or stay a mirror is the owner's call.

**Alternatives.** Stay a plain mirror and report the problems to the original
author (leaves the root-level download risks in place); add only the
repository security files (makes unchanged code look maintained).

**Review findings set aside.**
- "The year workflow is not registered, so it never runs": not confirmed from
  the API alone; listed as something to check, not a defect.
- The `/tmp` symlink race was rated must-fix by one reviewer. It was folded
  into the "reuses files already in `/tmp`" finding, because one fix (a private
  download folder) covers both.
- The second, independent security review was skipped because the service was
  unavailable. Nothing replaced it.

## 2026-11-20: Renovate merges its own pull requests

Job `renovate-automerge` (#4).

**Decision.** Renovate merges its pull requests itself once every check passes,
majors included; new versions wait 3 days, security fixes and image rebuilds
don't, on the model homelab-atlas already uses. Kept manual: nothing kept
manual. `platformAutomerge` is false and `ignoreTests: true`: no checks run on
pull requests (its only workflow uses no secrets).

**Why.** The owner asked for every repo with Renovate to merge its updates
automatically (2026-11-20) and chose this model, majors included, over keeping
majors manual.

**Not done.** Repository settings and branch rules (owner only) and workflows
are unchanged. A group merges automatically only when every update in it may, so
each manual exception gets its own pull request.

**Review findings.** Fixed: stale docs that still promised a manual review or
named Dependabot, and (where it applied) exceptions that sat inside the update
group. None declined.
