# Package Center settings storage

The default package installation volume is stored in `/etc/synoinfo.conf` under
`pkg_def_intall_vol`. The spelling `intall` is literal; changing it to `install`
would query a different, unused key.

This location was confirmed by static inspection of the official DS224+ firmware
for DSM 7.2.2-72806, 7.3.2-86009, and 7.4-90075. This establishes the code path in
those x86_64 builds. It does not establish behavior on every model or prove that
a package was installed on a running NAS.

## Settings and inspection

Package Center preferences are distributed across multiple stores. The following
scalar settings are read from `/etc/synoinfo.conf` by the inspected package
libraries and settings API implementation:

| Preference | Configuration key |
| --- | --- |
| Default installation volume | `pkg_def_intall_vol` |
| Update channel | `package_update_channel` |
| Enable automatic package updates | `enable_pkg_autoupdate_all` |
| Automatically update all packages | `pkg_autoupdate_all` |
| Automatically update important packages | `pkg_autoupdate_important` |
| Package update email notifications | `upgrade_pkg_email_notification` |
| Package update desktop notifications | `upgrade_pkg_dsm_notification` |

The API exposes friendlier field names such as `default_vol`, `enable_email`,
and `enable_dsm`; these are not necessarily the on-disk key names. Other package
state is separate: the libraries reference `/usr/syno/etc/packages/feeds`,
`/usr/syno/etc/packages/<auto_update_pkgs>`, and
`/usr/syno/etc/packages/<auto_update_important_pkgs>`. The angle brackets are
literal filename characters in the inspected references. Do not treat those
paths as a complete inventory of every Package Center setting.

Run the bundled read-only inspector on a NAS:

```sh
sudo bash scripts/inspect-package-settings.sh
```

Or inspect an extracted firmware tree on a workstation:

```sh
bash scripts/inspect-package-settings.sh --root /path/to/extracted-root
```

The inspector compares the active and factory-default preference files. It
prints only the seven known keys and validated scalar values, suppresses unrelated
configuration fields, and never evaluates configuration text as shell code.
`[not set]` means a readable file did not contain the key; `[unavailable]` means
the file could not be read. An empty default volume is reported as
`[no default volume]`; this is the stored preference, not a claim that no usable
volume exists. `[unrecognized]` requires investigation rather than a guessed value.

Do not edit `/etc.defaults/synoinfo.conf` to select an installation volume. Prefer
Package Center's UI for persistent preferences and the install operation's
`volume_path` parameter for a single installation. A filesystem preference alone
does not prove that a volume exists, is mounted, is writable, or can host a package.

## Firmware evidence

The reviewed artifacts are available directly from Synology:

- [DSM DS224+ 7.2.2-72806](https://global.synologydownload.com/download/DSM/release/7.2.2/72806/DSM_DS224%2B_72806.pat)
- [DSM DS224+ 7.3.2-86009](https://global.synologydownload.com/download/DSM/release/7.3.2/86009/DSM_DS224%2B_86009.pat)
- [DSM DS224+ 7.4-90075](https://global.synologydownload.com/download/DSM/release/7.4/90075/DSM_DS224%2B_90075.pat)

The archive headers passed signature verification during extraction. Each
artifact's `VERSION` file supplied the build identity. The contained `hda1.tgz`
is XZ-compressed despite its filename suffix. No firmware, archive keys, or
proprietary libraries are distributed with this repository.

The exported `SYNOPackageTool::PMSGetPackageDefVol` function in
`usr/lib/libsynopkg.so.1` loads `/etc/synoinfo.conf` and `pkg_def_intall_vol`, calls
`SLIBCFileGetKeyValue`, and validates the resulting volume. Its paired
`PMSSavePackageDefVolPath` function writes that key via `SLIBCINFOSetKeyValue`.
The `SYNO_PACKAGE::PackageWebAPI::GetSetting` implementation in
`usr/syno/synoman/webapi/lib/SYNO.Core.Package.so` reads the notification and
update-channel keys from the same preference file. The installed API descriptor
advertises `SYNO.Core.Package.Setting` and `SYNO.Core.Package.Setting.Volume`
version 1, with separate `get` and `set` methods.

The libraries omit section headers. Exported function addresses can be recovered
from their dynamic symbol tables, and the x86_64 code inspected using raw-binary
disassembly. In the reviewed files, executable-segment file offsets match the
virtual addresses listed below.

| DSM build | `PMSGetPackageDefVol` | `PMSSavePackageDefVolPath` |
| --- | --- | --- |
| 7.2.2-72806 | `0x156000` | `0x156250` |
| 7.3.2-86009 | `0x157490` | `0x1576e0` |
| 7.4-90075 | `0x15a150` | `0x15a3a0` |

SHA-256 fingerprints make this analysis reproducible without redistributing the
firmware:

| DSM build | Official PAT SHA-256 |
| --- | --- |
| 7.2.2-72806 | `4875a0f3fd4071fc640f8bc5285dc2cd7f0c0b9bd106e4f16e3edaa7c98adcf5` |
| 7.3.2-86009 | `41a92af08c5b091dc3b2c0a2ef806deaf1b892555f41c224400001ff563a5d4d` |
| 7.4-90075 | `92afd32db60cc2ff551a65181d21471f7fc7eee69750d9d97445a51087942ba6` |

| DSM build | `usr/lib/libsynopkg.so.1` SHA-256 |
| --- | --- |
| 7.2.2-72806 | `ee5d94ce9e43859457f65e712a4f1788da55c3bfebdc12af6043a854e512cd81` |
| 7.3.2-86009 | `cd2c2402d789e93eefb4f21d3fcc140fbad1db0665a5a5a5c21c518ca43cfc5b` |
| 7.4-90075 | `152f586f09db2d38a5bfdbf1fbd05203c38bae288d3c1e293fb68ad550a44a8b` |

Live verification can now compare the UI/API result with this exact key without
searching or publishing unrelated system configuration. Other CPU architectures
and later firmware builds still require their own confirmation.
