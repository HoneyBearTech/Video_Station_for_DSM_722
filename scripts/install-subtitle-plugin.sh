#!/usr/bin/env bash
# Install or restore the optional REST subtitle adapter without changing codecs.
set -euo pipefail
umask 077

usage() {
    echo "Usage: $0 --api-key-file=PATH [--package-root=PATH] [--reader-group=GROUP]"
    echo "       $0 --restore [--package-root=PATH]"
}

package_root=/var/packages/VideoStation
reader_group=
key_file=
restore=no
for option in "$@"; do
    case "$option" in
        --api-key-file=*) key_file=${option#*=} ;;
        --package-root=*) package_root=${option#*=} ;;
        --reader-group=*) reader_group=${option#*=} ;;
        --restore) restore=yes ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
if [[ $restore == yes && -n $key_file ]]; then
    echo "--restore takes no API key file." >&2
    exit 2
fi
if [[ $EUID != 0 ]]; then
    echo "Run as root after stopping Video Station." >&2
    exit 1
fi
if [[ ! -f $package_root/INFO || ! -d $package_root/target/subtitle_plugins ]]; then
    echo "Video Station package layout was not found." >&2
    exit 1
fi
version=$(sed -n 's/^version="\([^"]*\)"$/\1/p' "$package_root/INFO")
if [[ $version != 3.1.0-3153 && $version != 30.1.0-3153 ]]; then
    echo "This adapter requires Video Station 3.1.0-3153." >&2
    exit 1
fi
if [[ -x /usr/syno/bin/synopkg ]]; then
    if /usr/syno/bin/synopkg status VideoStation >/dev/null 2>&1; then
        package_status=0
    else
        package_status=$?
    fi
    case "$package_status" in
        3|17) ;;  # Stopped on the supported package status conventions.
        *)
            echo "Stop Video Station in Package Center and verify its stopped status before changing the plugin." >&2
            exit 1
            ;;
    esac
elif [[ $package_root == /var/packages/VideoStation ]]; then
    echo "The DSM package command is required to verify Video Station is stopped." >&2
    exit 1
fi
plugin_parent=$package_root/target/subtitle_plugins
plugin=$plugin_parent/syno_opensubtitles
state_dir=$package_root/target/.subtitle-plugin-backups
if [[ -L $state_dir ]]; then
    echo "Refusing a symlinked backup directory." >&2
    exit 1
fi
mkdir -p -- "$state_dir"
chmod 0700 "$state_dir"
backup=$state_dir/syno_opensubtitles.original
if [[ -L $plugin || -L $backup ]]; then
    echo "Refusing a symlinked plugin or backup directory." >&2
    exit 1
fi
# Print a path in the backup directory that does not exist yet.
unused_state_path() {
    local path
    path=$(mktemp -d "$state_dir/$1.XXXXXX") || return 1
    rmdir "$path" || return 1
    printf '%s\n' "$path"
}
staging=
retired=          # the adapter taken out by --restore; removed once replaced
replaced_plugin=  # an unmarked plugin moved aside by --restore; always kept
older_backup=     # an earlier backup moved aside by a reinstall; always kept
cleanup() {
    local status=$?
    # Put a plugin back, trying each copy in turn until one is in place.
    local candidate
    for candidate in "$replaced_plugin" "$backup" "$retired"; do
        [[ ! -e $plugin ]] || break
        [[ -n $candidate && -d $candidate ]] || continue
        mv "$candidate" "$plugin" || echo "Could not move $candidate back to $plugin." >&2
    done
    # The backup slot is only empty here if a reinstall did not finish.
    if [[ -n $older_backup && -d $older_backup && ! -e $backup ]]; then
        mv "$older_backup" "$backup" || echo "Restore the earlier backup from $older_backup." >&2
    fi
    if [[ -n $staging && -d $staging ]]; then rm -r -- "$staging"; fi
    # If the adapter was moved back, $retired is gone and nothing is removed.
    if [[ -e $plugin && -n $retired && -d $retired ]]; then rm -r -- "$retired"; fi
    return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ $restore == yes ]]; then
    if [[ ! -d $backup ]]; then
        echo "No original plugin backup was found." >&2
        exit 1
    fi
    if [[ ! -e $plugin ]]; then
        mv "$backup" "$plugin"
    elif [[ -f $plugin/.rest-adapter ]]; then
        retired=$(unused_state_path .subtitle-retired)
        mv "$plugin" "$retired"
        mv "$backup" "$plugin"
    elif [[ -d $plugin ]]; then
        # No marker: a Video Station update has put its own plugin back.
        replaced_plugin=$(unused_state_path syno_opensubtitles.replaced)
        mv "$plugin" "$replaced_plugin"
        mv "$backup" "$plugin"
        echo "The plugin in place was not this adapter. It was kept at $replaced_plugin"
    else
        echo "The plugin path is not a directory; nothing was changed." >&2
        exit 1
    fi
    echo "Original subtitle plugin restored. Start Video Station."
    exit 0
fi
if [[ -z $key_file || ! -f $key_file || -L $key_file || ! -s $key_file ]]; then
    echo "Provide a nonempty API key file, not a symlink." >&2
    exit 2
fi
if [[ ! -d $plugin ]]; then
    echo "Original plugin is missing; restore it before reinstalling." >&2
    exit 1
fi
# A backup beside an unmarked plugin means a Video Station update replaced the
# adapter. Beside the adapter itself, it means the adapter is still installed.
if [[ -e $backup && ( ! -d $backup || -f $plugin/.rest-adapter ) ]]; then
    echo "A backup already exists; restore before reinstalling." >&2
    exit 1
fi
key_text=$(cat -- "$key_file")
if [[ -z $key_text || $key_text == *$'\n'* || $key_text == *$'\r'* || $key_text == *[[:space:]]* ]]; then
    echo "API key file must contain one nonempty key without whitespace." >&2
    exit 2
fi
unset key_text
if [[ -z $reader_group ]]; then
    reader_group=$(id -gn VideoStation) || {
        echo "Cannot find the subtitle runtime account; supply --reader-group explicitly." >&2
        exit 2
    }
fi
if ! getent group "$reader_group" >/dev/null; then
    echo "The requested reader group does not exist." >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_dir=$script_dir/../subtitle_plugins/opensubtitles_rest
staging=$(mktemp -d "$state_dir/.subtitle-rest.XXXXXX")
chmod 0755 "$staging"
cp "$source_dir/INFO" "$source_dir/subtitle.php" "$staging/"
chmod 0644 "$staging/INFO" "$staging/subtitle.php"
cp -- "$key_file" "$staging/api-key"
chown "root:$reader_group" "$staging/api-key"
chmod 0640 "$staging/api-key"
: > "$staging/.rest-adapter"
if [[ -e $backup ]]; then
    # The plugin in place now becomes the one that --restore brings back.
    older_backup=$(unused_state_path syno_opensubtitles.previous)
    mv "$backup" "$older_backup"
fi
mv "$plugin" "$backup"
if ! mv "$staging" "$plugin"; then
    mv "$backup" "$plugin"
    exit 1
fi
staging=
if [[ -n $older_backup ]]; then
    echo "The earlier plugin backup was kept at $older_backup"
fi
echo "REST subtitle adapter installed; original plugin retained for --restore."
echo "Start Video Station and use your OpenSubtitles.com login in subtitle settings."
