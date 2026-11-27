# Installing the packages on a chosen volume

> **Not yet tested on a real NAS.** This option uses a DSM web service that has
> only been tried against stand-ins. Read [the risk](#the-risk-removed-then-failed)
> and back up first. Run without `--volume` if you don't need it.

Use `--volume=/volumeN` to choose which volume the packages are installed on:

```sh
sudo bash /volume1/scripts/videostation_for_722.sh --install=all --volume=/volume2
```

Keep the `lib` folder that comes with the script in the same folder as the
script. The folder the script is in and the volume the packages go on don't
have to be the same.

Without `--volume`, the script works exactly as before: DSM's
`synopkg install` puts the packages on Package Center's default volume.

## What it needs

- `jq` and `timeout` on the NAS, and DSM's `/usr/syno/bin/synowebapi` and
  `/usr/syno/bin/synopkg`. DSM 7.2.2-72806 has `jq` at `/usr/bin/jq`; the
  script checks for all of them rather than assuming.
- A volume path of the form `/volume1`, `/volume2` and so on. Anything else
  stops the script with exit code 2 before it does anything.

## What it does

1. **Before downloading anything** it checks that the volume:
   - is mounted read-write (a folder left behind after a volume was removed
     doesn't count);
   - is offered by Package Center as an install volume.
2. Still before downloading, it asks DSM (`SYNO.Core.Package.Installation`,
   method `check`) whether each package it needs to install can go on that
   volume. This doesn't change anything.
   - For a package that isn't installed, a "no" stops the script.
   - DSM may not answer for a package that is still installed (one that is
     about to be replaced). The script then prints a note and carries on; that
     package is checked again just before it is installed.
3. It downloads and checks every package as usual: HTTPS with the certificate
   checked, a SHA-256 checksum for every file, into a private folder only root
   can read.
4. It removes the old packages as usual, then installs each new one from the
   private folder with the web service, on the chosen volume. Just before each
   install it checks the volume and the package again.
5. After each install it waits up to 30 seconds for DSM to show the package as
   installed in `/volumeN/@appstore/<package>`. Only then does it carry on.

If any of the checks in steps 1 and 2 fails, the script says
**"Nothing was changed on the NAS."** and exits with code 2.

It never changes Package Center's default volume, keeps DSM's signature check
on, and never forces an install.

## Packages already at the right version stay where they are

`--volume` only affects packages the script installs. A package that is
already the right version is not touched, so it stays on its current volume.
Your packages can end up on different volumes. To move one, uninstall it in
Package Center (keep its data) and run the script again with `--volume`.

## The risk: removed, then failed

The old packages are removed before the new ones are installed. If installing
on the chosen volume fails at that point, **the package stays uninstalled**.
The early check in step 2 makes this less likely, but can't rule it out,
because DSM may not answer it for a package that is still installed.

If this happens, the script:

- names every package this run removed that is not installed now, with the
  version it had;
- prints the command to run again **without** `--volume`, which installs
  the packages on Package Center's default volume instead;
- exits with code 1.

For example:

```
ERROR Video Station could not be installed on /volume2
This run removed these packages and they are not installed now:
  - Video Station 30.1.1-3168
Video Station is not installed.
To install the packages on Package Center's default volume, run the script again without --volume:
  sudo bash /volume1/scripts/videostation_for_722.sh --install=all
```

An install that was interrupted may still be running in DSM. Look in Package
Center before you run the script again.

## Where the request format comes from

The [synology-api client](https://github.com/N4S4/synology-api/blob/master/synology_api/core_package.py)
installs an already downloaded file by calling `SYNO.Core.Package.Installation`
version 1 with `check`, then `install` with `type=0`, `volume_path` and `path`.
This script sends the same requests, with `check_codesign=true` and
`force=false`. String values are sent JSON-encoded, as DSM's local
`synowebapi --exec` runner expects; `extra_values` is the string `"{}"`.

DSM 7.2.2-72806's `SYNO.Core.Package.lib` lists both methods at version 1, and
its `SYNO.Core.Package.so` has the code for installing a local file. This was
read from the firmware outside this repository; no firmware is included here.

The [local API runner notes](https://github.com/akari-sora/synology-nas-cli/blob/main/docs/DSM-API-NOTES.md)
describe the JSON encoding and the `[Line N] Exec WebAPI:` line printed before
the reply. The script accepts that line and nothing else: any other text, more
than one reply, a reply without `success: true`, or any nested failure counts
as a failure.

## Tests

The tests use stand-ins for the web service, `/proc/mounts`, `synopkg` and the
package install folder. They cover bad, missing, read-only and unlisted volumes,
a "no" from the package check, bad replies, the file and volume sent to DSM,
the late-failure message, and a normal run without `--volume`. The tests that
need `jq` are skipped without it; see `tests/harness.py` for the full test
command.

## NAS checks before this is merged

Back up first, and note the model, CPU and DSM version.

1. `--install=onlyamc` **without** `--volume` still works (first real-NAS test
   of `v1.4.22-hbt.1`).
2. A fresh `--install=onlyamc --volume=/volume2` lands in `/volume2/@appstore`
   and starts. This also shows whether DSM can read the file from the root-only
   download folder.
3. All three packages with `--volume=/volume2`, a reboot, and playing a video
   (including HEVC).
4. Replacing the v4 codec pack (Advanced Media Extensions 4.x) with
   `--volume=/volume2`. Note whether the early check answered for it or printed
   the note.
5. A missing, read-only and unlisted volume each stop with "Nothing was
   changed on the NAS."
6. A rerun, and a run from a scheduled task.
7. Package Center's default volume is unchanged afterwards.
