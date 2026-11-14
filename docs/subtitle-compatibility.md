# Optional OpenSubtitles REST support

The optional adapter implements the Video Station 3.1.0 subtitle plugin command
contract against the current OpenSubtitles.com REST service. It keeps Video
Station 3.1.0-3153 and CodecPack 3.1.0-3005, replacing only the subtitle plugin.
It does not install Video Station 3.1.1 or change any codec binary.

This is an opt-in development feature. The client and installation/restore paths
have executable local tests. A real DSM plugin invocation, account login,
subtitle search, and playback have not been verified on a NAS.

## What changed between the official packages

The official x86_64 packages were downloaded and their archive header signatures
verified before extracting and comparing them:

| Package | SHA-256 of downloaded SPK |
| --- | --- |
| [3.1.0-3153](https://global.synologydownload.com/download/Package/spk/VideoStation/3.1.0-3153/VideoStation-x86_64-3.1.0-3153.spk) | `e9b1a4935e255aac649953fa6b8a10ebcb3114970552dcf00b9ff93d62065715` |
| [3.1.1-3168](https://global.synologydownload.com/download/Package/spk/VideoStation/3.1.1-3168/VideoStation-x86_64-3.1.1-3168.spk) | `e35b529fae8c0ac30d737f91305fc2e6a52284486ad019fb99610f2c1850db86` |

In `subtitle_plugins/syno_opensubtitles`, the old package uses `subtitle.php`,
`OpenSubtitles.php`, `Option.php`, and an XML-RPC client. The newer package uses
`subtitle.py`, `OpenSubtitles.py`, and `Language.py`, with an API-key parameter
and JSON REST responses. Its entry file and credential handling differ.

The newer package also adds `bin/handle_ame_post_install`,
`bin/synovideostation_check_need_codec`, and
`scripts/synovideostation_ame_pack_install.py`, and changes playback libraries.
Its `lib/libsynovideostation.so` adds dependencies on `libsynostoragecore.so.7`
and `libvsdbapi.so`. Therefore copying the newer subtitle directory or changing
the package version does not establish compatibility with the old installation.
No extracted vendor code, keys, or binaries are distributed here.

The replacement client uses the
[official REST specification](https://stoplight.io/api/v1/projects/opensubtitles/opensubtitles-api/nodes/open_api.json):
login returns a token and an API host, search results contain downloadable
`files[].file_id` values, and a download request returns a temporary subtitle
link. The client retains the old plugin's search/download JSON shape, including
hash-only searches with `--hash` and `--size`.

## Install on a test NAS

Use a NAS with a current backup. Keep the complete repository folder together;
the setup script reads its sibling `subtitle_plugins` directory. Confirm Video
Station reports version `3.1.0-3153` or the installer's advertised
`30.1.0-3153`. Stop Video Station in Package Center first; setup refuses a
package unless DSM reports it stopped. Alternate `--package-root` paths support
isolated filesystem fixtures; they do not verify a live package service.

Obtain an API consumer key from your OpenSubtitles.com account. The account and
key must belong to the `.com` service. Open a root Bash session and enter the key
without putting it in a command argument or shell history:

```sh
sudo bash
umask 077
key_file=$(mktemp)
read -r -s -p 'OpenSubtitles API key: ' subtitle_key
printf '\n'
printf '%s\n' "$subtitle_key" > "$key_file"
unset subtitle_key
bash /volume1/scripts/Video_Station_for_DSM_722/scripts/install-subtitle-plugin.sh --api-key-file="$key_file"
rm -f -- "$key_file"
unset key_file
```

Adjust the repository path to match your NAS. Setup keeps the original plugin
outside the scanned plugin directory at
`target/.subtitle-plugin-backups/syno_opensubtitles.original`, creates the replacement directory without
exposing the key during staging, and stores only the API key with mode `0640`.
It derives the reader group from the `VideoStation` runtime account's primary
group. If your installation uses another group, supply `--reader-group=GROUP`
after verifying the account that runs the subtitle plugin. Do not make the key
world readable to work around an access failure.

Start Video Station and enter your OpenSubtitles.com username and password in
its subtitle account settings. The adapter uses those supplied credentials; it
does not save a second password file. The older settings UI has a 32-character
password field; saving credentials through that UI is part of the outstanding
device verification. It logs neither credentials nor HTTP
response bodies. API-key and bearer headers go only to the regular or VIP API
host. Subtitle file downloads receive no account credentials, require HTTPS,
and are limited to OpenSubtitles.com hosts and 8 MiB responses.

The adapter requests SRT subtitles. It saves each selection next to the video
with a stable suffix such as `Film.rest-123.eng.srt`, retaining the old playback
library's language suffix while refusing traversal and
symlink destinations. Completed files are published without overwriting an
existing file. A repeated download returns the existing file without spending
another download request. Login is performed once per plugin invocation; the
service can rate-limit repeated searches or logins, and the adapter does not
retry authentication or quota failures automatically.

## Restore

Stop Video Station, then run:

```sh
sudo bash /volume1/scripts/Video_Station_for_DSM_722/scripts/install-subtitle-plugin.sh --restore
```

Start Video Station again. Restore reinstates the exact saved plugin directory
and removes the adapter's copied API key. A backup with no active plugin can
also be restored after an interrupted installation. Reinstallation is refused
until the existing adapter has been restored. Package upgrades or reinstalls
may replace plugin files; check the adapter state afterwards.

## Verification still required

Test the actual DSM plugin runner, access to the API-key file under its service
identity and confinement policy, a valid account's search and download, and
external-subtitle playback. Also verify that a normal Video Station/codec
restart still works after installing and restoring the adapter. The local tests
exercise the REST contract, host restrictions, credential separation, quota
errors, movie hashing, file handling, and backup restoration without contacting
the live account service.

On a workstation with PHP installed, run:

```sh
python3 -m unittest discover -s tests -p test_subtitle_plugin.py -v
```

Set `PHP_BINARY` to an alternate CLI interpreter path if needed. The PHP tests
skip when no interpreter is available; installation fixture tests still run.
The source avoids syntax newer than PHP 7.4 and was executed locally with
PHP 8.5. Static inspection of DSM 7.2.2 identifies PHP 8.1.9; that runtime was
not executed during validation. The native runner also needs PHP's cURL
extension. Device validation remains necessary.
