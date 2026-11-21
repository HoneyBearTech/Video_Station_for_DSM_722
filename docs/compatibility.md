# Compatibility and verification status

Reviewed on 2026-11-14. The installer retains Video Station 3.1.0-3153,
Advanced Media Extensions 3.1.0-3005, and Media Server 2.0.5-3152. Local tests
and static firmware inspection do not establish installation or playback on a NAS.

## Selecting an installation volume

The installer now accepts `--volume=/volumeN` for new package installations:

```sh
sudo bash /volume1/scripts/videostation_for_722.sh --install=all --volume=/volume2
```

Keep the accompanying `lib` folder beside the main script. The helper uses the
local-package installation API with a per-install destination, keeps signature
checking enabled, and does not change Package Center's global default volume.
It checks API responses and confirms the installed package's resolved target.
Existing packages with the expected version are retained on their current volume.

The original `synopkg install <spk>` path remains the default when `--volume` is
omitted. The volume argument in `install_from_server` does not apply to that
local-file command. See [volume installation details](package-volume.md) for
requirements, request evidence, failure behavior, and device checks.

Required package downloads now finish before compatibility limits change or an
existing package is uninstalled. Network failure therefore leaves the installed
packages untouched. An installation failure after those changes is not an atomic
rollback; inspect Package Center before retrying.

## Package Center settings storage

Official DS224+ firmware for DSM 7.2.2-72806, 7.3.2-86009, and 7.4-90075 reads
the default installation volume from `/etc/synoinfo.conf`, using the literal
key `pkg_def_intall_vol`. The spelling is intentional. Related update and
notification preferences also live in that file.

A read-only inspector prints only known, validated preference values:

```sh
sudo bash scripts/inspect-package-settings.sh
```

It also supports `--root DIRECTORY` for extracted firmware. It never sources the
configuration as shell code and does not print unrelated settings. See
[settings storage evidence](settings-storage.md) for the confirmed keys, firmware
hashes, and the limits of static inspection. Use Package Center to change global
preferences; the inspector does not edit them.

## OpenSubtitles without replacing codecs

The optional REST subtitle adapter targets Video Station 3.1.0's existing plugin
interface. It preserves playback and codec binaries and can restore the original
subtitle plugin from a retained backup. It requires an OpenSubtitles.com API key
and account credentials. Installation is a separate, explicit action; rerunning
the main package installer does not enable it.

See [subtitle compatibility and setup](subtitle-compatibility.md) for the package
comparison, setup and restoration commands, API restrictions, and local tests.
This is a source implementation of the REST integration, not a claim that the
entire Video Station 3.1.1 package works with the older codec package.

## Remaining device verification

Before treating the optional features as production-ready:

- Test selected-volume installs, failed installs, unavailable volumes, reruns,
  and existing packages on another volume on each supported DSM version.
- Compare the settings inspector's output with the running NAS's Package Center
  settings; static firmware inspection does not read a deployed system.
- Test the subtitle adapter through Video Station's actual plugin runner,
  account login, search, download, and external subtitle selection.
- Verify playback, HEVC decoding, restarts, rollback, and recovery after a DSM
  update on each affected CPU architecture.

The original package combination remains the default. None of these device
checks has been performed during this development run.
