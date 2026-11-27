# Repository review, 2026-11-27

Job `repo-review`. A whole-repository review of `main` at `8843975`: the
install script, its documentation, the workflow, the Renovate config and the
repository's security set-up. Nothing was changed. The script was read and
linted, and some failure paths were tested with stand-in commands. It was not
run on a Synology NAS.

## The short version

- The install script here is **exactly the same** as the original author's
  latest release, v1.4.22. Every script problem below is also in the original
  project.
- The script runs as the NAS's most powerful user (root). It has a few gaps that
  matter for that: it downloads packages without checking they are genuine, and
  it can remove your current packages before it knows it can install the
  replacements.
- The script still updates itself from the **original author's** project, not
  this one. Changes made here would be overwritten the first time someone
  accepts an update.
- Draft PR #3 (opened 2026-11-14, still a draft) already fixes several of these
  problems, and also adds new features that have not been tried on a real NAS.
- Nothing secret is in the repository or its history, and nothing in it credits
  an outside tool.

## What we found

Lines refer to `videostation_for_722.sh` unless another file is named.

### Most important (fix these first if this copy is going to be run or kept up)

1. **Packages are downloaded without checking they are genuine** (line 603).
   The download skips the HTTPS certificate check (`curl -k`), and there is no
   checksum. The file is then installed as root (line 564). Someone who can
   tamper with the network at that moment could supply their own package. That
   is unlikely on a home network, but the damage would be a fully taken-over
   NAS. All three Synology download servers passed a normal certificate check
   during this review, so the skip looks unnecessary.
2. **Any package file already sitting in the shared temporary folder is
   installed as-is** (line 597). If `/tmp/<package>.spk` already exists, the
   download is skipped and that file is installed. Anything else on the NAS that
   can write to `/tmp` could leave a file there for the next run. All file names
   are fixed and predictable (lines 393-395, 597-603).
3. **The self-updater is unverified and points at the original project**
   (lines 33, 217-345). It downloads the latest release of
   `007revad/Video_Station_for_DSM_722`, unpacks it in `/tmp`, copies it over
   the running script and restarts. There is no checksum. It only runs if
   someone types `y` within 30 seconds, so scheduled runs don't update. It also
   **forgets the options you started with**: line 217 saves the options again
   after they have already been used up, so after an update an
   `--install=onlyamc` run falls back to "install everything".
4. **A failed or partial download still counts as a success** (lines 603-613).
   The only check is whether the file exists. A dropped connection or a full
   `/tmp` leaves a half-written file, which is then handed to the installer.
   This was confirmed with stand-in commands.
5. **Your current packages can be removed before the replacements are
   downloaded** (lines 680-705, then 710, 726, 745). If the network fails at
   that point, the NAS is left without Video Station, Media Server or the codec
   pack, and there is no undo.
6. **There is no way to report a security problem in this copy.** There is no
   `SECURITY.md`, GitHub Issues are off, private vulnerability reporting is
   off, and the script's "create an issue" link (line 384) points at the
   original project.

### Worth fixing

- **A timeout waiting for a package to start or stop is treated as success**
  (lines 498-510). The script waits about 20 seconds and then carries on as if
  it worked, so it can still print "Finished".
- **Changes to system settings files are not checked** (lines 665-676, 715,
  733, 750). If one of these edits fails, the script carries on, and DSM may
  later offer the incompatible update the script meant to block.
- **Some failures report success to the Task Scheduler.** A bad option
  (lines 191-194) and an unsupported CPU (lines 379-385) both end with exit
  code 0, so a scheduled task shows success when nothing was installed.
- **The scheduler guide gives the option wrongly.**
  `how_to_run_from_scheduler.md:19` says `install=`, but the script needs
  `--install=`. A task set up that way is silently ignored and installs all
  three packages.
- **`--install=onlyamc` still starts Video Station and Media Server** if they
  were installed and stopped (lines 769-785).
- **Any 3.x codec pack is accepted as "already installed"** (lines 680,
  709-719), even if it is not the 3.1.0-3005 version the script promises.
- **Options that do nothing.** `--log`, `--debug` and `--autoupdate` are
  accepted but unused. `--trace` is not recognised at all, and `-t` is
  rejected as invalid (lines 125-186).
- **The script file isn't marked as runnable** in the repository (mode 644),
  but `README.md:74-75` tells people to run it directly.
- **The yearly README workflow** (`.github/workflows/update-year.yml`):
  - it uses an old action version (`actions/checkout@v3`), pinned by tag
    rather than by exact commit;
  - it sets permissions only per job, with nothing at the top level;
  - it fails when the year is already current, because it tries to commit
    with nothing to commit;
  - it pushes straight to `main`, which the branch rules require to go through
    a pull request, so it would probably be rejected anyway.
- **The Renovate notes say updates merge "once every check passes"**, but the
  config sets `ignoreTests: true`, which tells Renovate to ignore checks. The
  merge rule itself was Sean's decision on 2026-11-20 and is not being
  reopened; only the wording is wrong. Also, the dependency dashboard needs
  GitHub Issues, which are off, and no Renovate update PR has appeared for the
  old `checkout@v3`, so it is worth checking Renovate can see this repository.
- **The README tells readers to paste a third-party one-line installer**
  (`bash -c "$(curl ...)"`, `README.md:110`) that always fetches the latest
  code from someone else's repository.
- **By design, the script blocks updates for the packages it installs**
  (lines 664-676 and the version edits). That is how it works, but it means
  those older packages never get security fixes. The README doesn't say so,
  and there is no documented way to undo it.
- **Upstream pointers.** The README badges, download links, `FUNDING.yml` and
  bug-report links all point at the original author. The README never says
  this is a copy. The original `LICENSE` notice is correctly kept.

### Checked and clean

- No passwords, keys, tokens, private addresses or `.env` files, now or in
  history. GitHub secret scanning and push protection are on, with no alerts.
- No commit, trailer or file credits an outside tool.
- The option handling (`eval set -- "$options"`) is the standard safe pattern,
  and the release tag is only used inside quotes. No command-injection path
  was found.
- `shellcheck`: four unused-variable warnings only. `bash -n`: passes.

### Repository security set-up (OpenSSF)

- **In place:** MIT license; a `main` rule that blocks force-pushes and
  deletion and requires a pull request; read-only default workflow token;
  secret scanning; vulnerability alerts.
- **Missing for Baseline Level 1 and Best Practices Passing:** a security
  policy and contact; a place to report bugs (Issues are off); a contribution
  guide; automated tests or a lint check; an OpenSSF badge.
- **Also missing for Level 2 and Silver:** explicit least-privilege workflow
  permissions, tagged releases of this copy, a code of conduct, governance and
  roles, and a roadmap. The branch rule requires no approvals and no checks,
  and admins can bypass it.
- The repository also has no guidelines file for contributors' tooling. The
  standard bootstrap would add the missing files.

## What Sean could do next

1. **Recommended: keep this as Sean's own maintained copy, safety fixes
   first.**
   - Take the safety fixes from draft PR #3 (or redo them) as one small change:
     certificate checks on, never reuse a file already in `/tmp`, treat failed
     downloads as failures, download before removing anything, keep options
     across an update.
   - In the same change, point the self-updater at this repository, or turn it
     off.
   - Leave PR #3's new features (install volumes, REST subtitles) until they
     have been tried on a NAS.
   - Fix the scheduler guide and say in the README that this is a modified
     copy.
   - *Risks:* pulling in later changes from the original project gets harder;
     Sean owns support for this copy; turning the certificate check on could
     fail on a NAS with very old certificates; nothing is proven until it runs
     on a real NAS.
2. **Keep it as a plain mirror of the original.** Close PR #3 and copy the
   original project's changes from time to time. Every script problem above
   stays, and the only fix would be to report them to the original author,
   which is Sean's call.
3. **Add the repository security files only** (security policy, contribution
   guide, badge, lint check, workflow fixes). This is useful either way, but on
   its own it makes unchanged code look maintained. It is best done after
   option 1, not instead of it.

## Limits of this review

- Nothing was run on a Synology NAS. Whether DSM's package installer checks
  package signatures itself is unknown, so the download findings assume it
  doesn't.
- Draft PR #3 (24 files, about 2,300 added lines) was not reviewed in full.
  It needs its own review before any of it is merged.
- The planned second, independent security review could not run (the service
  was unavailable), so the security findings come from one security review
  plus the independent code review, which found the same top issues.
