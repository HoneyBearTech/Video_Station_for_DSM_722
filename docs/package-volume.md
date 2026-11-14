# Installing new packages on a selected volume

Use `--volume=/volumeN` to request a specific internal DSM data volume for newly
installed packages. Keep the `lib` folder beside the main script when copying
this repository to the NAS:

```sh
sudo bash /volume1/scripts/videostation_for_722.sh --install=all --volume=/volume2
```

The folder containing the script and the installation volume are independent.
The option does not move a package already installed with the expected version.
Omit `--volume` to retain the original `synopkg install` path.

## Requirements and behavior

Explicit volume selection requires `jq` on the command path and DSM's
`/usr/syno/bin/synowebapi` and `/usr/syno/bin/synopkg`. The official DSM
DS224+ 7.2.2-72806 filesystem contains `jq` at `/usr/bin/jq`. The installer checks
for these dependencies rather than assuming that another DSM build has them.
No Python installation is required on the NAS.

Before package compatibility limits or installed packages change, the installer
checks that the requested path has the form `/volume1`, `/volume2`, and so on,
that it is mounted read/write, and that Package Center lists it as an available
volume. A directory remaining after a volume has been unmounted is insufficient.

For each installation, the helper checks package eligibility and requests that
DSM install the already-downloaded SPK on the selected volume. It preserves
signature checking and does not request a forced installation. It never calls
the settings API's `set` method or changes Package Center's default volume.

An API process exit code of zero alone is insufficient. The helper requires a
single valid JSON response with `success: true`, rejects nested failures and
task-acceptance responses, and checks both package registration and the final
installation path. A package
must be registered as running, starting, or stopped, and its resolved target
must be `/volumeN/@appstore/PackageID`. Up to 30 seconds are allowed for that
registration to appear after the installation API returns.

If installation cannot be confirmed, the installer stops before changing the
new package's advertised version or restarting it. Inspect Package Center
before retrying: an API failure or interruption can leave a package operation
in progress, and installation is not an atomic rollback transaction. A package
pre-check does not establish that its signature, compatibility, or dependencies
will pass the subsequent installation operation.

## Source contract

The [maintained API client](https://github.com/N4S4/synology-api/blob/master/synology_api/core_package.py)
provides an `install_package` operation for already-downloaded files. It calls
`SYNO.Core.Package.Installation` version 1 with `check`, followed by `install`
using `type=0`, `volume_path`, and `path`. This repository follows that request
shape, sets `check_codesign=true` and `force=false`, and encodes string values as
JSON for the local API runner. The string-valued `extra_values` parameter
contains an empty JSON object; it is encoded as a JSON string, not an object.

The official DSM 7.2.2-72806 `SYNO.Core.Package.lib` descriptor registers both
methods at version 1. Its `SYNO.Core.Package.so` library exports `InstallSPK`
and references `InstallSpkImpl` and `InstallPackageFromDownloadedSpk`, providing
additional static evidence for this route. In that build, the local-file branch
calls `InstallSPK`, waits for `InstallSpkImpl` to return, and then handles its
result; it is distinct from the branch that downloads a server package. These
files were inspected outside
the repository; no firmware or proprietary library is redistributed here.

The [local API runner notes](https://github.com/akari-sora/synology-nas-cli/blob/main/docs/DSM-API-NOTES.md)
describe JSON parameter encoding and the banner preceding a response. The helper
accepts the known banner and rejects other unparsed output rather than treating
text matching the word “success” as installation proof.

## Verification limits

Regression tests mock the NAS API, mounted-volume check, package status, and
installation symlink. They cover rejected volumes, malformed or failed API
replies, signature/force parameters, exact local-file selection, and a response
that reports success without the expected final target.

A NAS installation has not been performed during development. Before releasing
this option, test fresh installations, missing and read-only volumes, existing
packages on a different volume, failed installations, interruptions, and reruns
after DSM updates on each supported DSM version. Verify package startup and
playback separately; a correct installation directory does not establish codec
compatibility.
