# Decisions log

Why things are the way they are: each entry gives the decision, the reason and
what was turned down. Newest first. What shipped is in the [pass
map](pass-map.md).

## 2026-11-27: PR #3's features rebuilt as two pull requests

Job `pr3-rebase` (#8, #9).

**Decision.**
- **Rebuilt by hand:** PR #3's install-volume and REST-subtitle features were
  redone on current `main` instead of rebasing PR #3. A rebase would have
  brought back its older download and self-updater code.
- **Split in two:** they are two pull requests, because each needs its own
  NAS test and one shouldn't hold up the other.
- **Left out:** the package-settings inspector, the contribution guide,
  pre-commit and `.gitignore`. The roadmap has the inspector as a separate
  item, and the bootstrap job covers the rest.
- **Volume checks:** a clear "no" from DSM's package check stops the run
  before anything changes, even for a package that is still installed. Only
  a check that couldn't run lets an installed package go ahead, with a
  warning.
- **Helper ownership:** the helper is only loaded when the script folder and
  `lib/` are owned by root and not writable by others. The folders above the
  script folder are not checked; the docs say they must be root- or
  admin-only, because the script file itself depends on that too.

**Why.** These are the roadmap's next step after the safety fixes. The
volume feature uses a DSM service seen only in stand-ins, so it fails safe.

**Alternatives.**
- One combined PR: rejected, because both would wait for both NAS tests.
- Keeping PR #3's extra files: rejected, because that goes beyond "only its
  new features" and gets ahead of the bootstrap job.
- Checking every folder above the script: rejected, because it would refuse
  most shared-folder setups and adds little while the script file has the
  same exposure.

**Review findings.**
- **Fixed in the volume PR:**
  - DSM refusing an installed package was treated as "couldn't check";
  - the late-failure report claimed things it hadn't confirmed (removed /
    not removed, wrong volume vs. unknown location);
  - the helper was loaded as root with no ownership check;
  - rejected values were printed with `echo -e`.
- **Fixed in the subtitle PR:**
  - a failed restore could leave the plugin missing;
  - the API key file was read twice;
  - the key file's owner wasn't checked;
  - the sign-in reply's host wasn't checked strictly enough;
  - the changelog entry wasn't marked unreleased;
  - `--restore` with a key file gave a misleading message.
- **Declined:**
  - Re-checking every package just before each uninstall: DSM may not
    answer for an installed package, and a clear refusal already stops the
    run.
  - Refusing abbreviated options such as `--vol=`: these are standard and
    harmless.
- **Not run:** the independent plan check (service unavailable). The second
  security review ran on the fallback service and found nothing.

## 2026-11-27: Safety fixes for the maintained copy

Job `safety-fixes` (#7).

**Decision.** This is the owner's maintained copy (owner's choice, 2026-11-27).
- **Self-updater:** removed rather than repointed. A repointed updater would
  still run unverified code as root; users now update by downloading a new
  copy.
- **Checksums:** pinned for all 21 package files. They were downloaded with the
  certificate check on and cross-checked against the servers' ETags and a
  second Synology server. Synology publishes none, so these record the files
  as served on 2026-11-27.
- **Failures:** no switch skips the checks; a failure stops the script before
  any change.
- **Version:** `v1.4.22-hbt.1`, which shows the original version this is based
  on and still compares correctly.
- **Commits:** made under the HoneyBearTech Homelab Automation app's identity,
  and the app opens the pull request (owner's request).

**Why.** These were the top findings of the repository review. Draft PR #3 had
some of them mixed with untested features, so the fixes were redone by hand.
PR #3 is left alone and will need rebasing.

**Alternatives.**
- Keep the updater and point it here: rejected, as it still runs unverified
  code as root.
- Pin only the x86_64 checksums: rejected, as it leaves six CPU types
  unchecked.
- Rely on the certificate check alone: rejected, as it doesn't catch a changed
  file on a mirror.

**Review findings.**
- **Fixed:** the install step relied on decisions made before uninstalling,
  so an uninstall that left the package, or removing the v4 codec pack taking
  another package with it, was mishandled. Now each install re-checks the live
  state, the script stops if an uninstall didn't work, and possibly-affected
  packages are downloaded up front.
- **Also fixed:**
  - install links still pointed at the original project;
  - "Nothing was changed" printed even when a later server worked;
  - no message when the private folder couldn't be made;
  - `curl` read `.curlrc`;
  - the tests checked only 3 of the 21 checksums;
  - the tests could run the installer outside a container.
- **Declined:** trailing space after `pkg_sha256(){`, which matches the
  script's existing function style.
- **Not run:**
  - The independent plan check, the second security review and the
    plain-English check were skipped: the service was unavailable.
  - One code-review session stalled on an approval prompt and was replaced.

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
