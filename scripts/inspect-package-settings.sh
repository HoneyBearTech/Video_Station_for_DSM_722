#!/usr/bin/env bash
# Read only a fixed set of Package Center preferences; never load shell code.

set -u

usage() {
    echo "Usage: $(basename "$0") [--root DIRECTORY]"
    echo "Inspect Package Center preferences in an installed or extracted DSM tree."
    echo "Only known settings and validated scalar values are printed. No files are changed."
}

root=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --root)
            if [[ $# -lt 2 || ! -d $2 ]]; then
                echo "--root requires an existing directory" >&2
                exit 2
            fi
            root=${2%/}
            shift 2
            ;;
        *) usage >&2; exit 2 ;;
    esac
done

# Values outside this allowlist are suppressed, including malformed config lines.
read_setting() {
    local file=$1 wanted=$2 line key value result="[not set]"
    if [[ ! -r $file ]]; then
        printf '%s' '[unavailable]'
        return
    fi
    while IFS= read -r line || [[ -n $line ]]; do
        [[ $line =~ ^[[:space:]]*([a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]*=[[:space:]]*(.*)$ ]] || continue
        key=${BASH_REMATCH[1]}
        [[ $key == "$wanted" ]] || continue
        value=${BASH_REMATCH[2]}
        if [[ $value =~ ^\"([^\"]*)\"[[:space:]]*$ ]]; then
            value=${BASH_REMATCH[1]}
        elif [[ $value =~ ^([^[:space:]\"\']*)[[:space:]]*$ ]]; then
            value=${BASH_REMATCH[1]}
        else
            result="[unrecognized]"
            continue
        fi
        case "$wanted" in
            pkg_def_intall_vol)
                if [[ $value =~ ^/volume[1-9][0-9]*$ ]]; then
                    result=$value
                elif [[ -z $value ]]; then
                    result="[no default volume]"
                else
                    result="[unrecognized]"
                fi
                ;;
            package_update_channel)
                case "$value" in
                    stable|beta) result=$value ;;
                    *) result="[unrecognized]" ;;
                esac
                ;;
            *)
                case "$value" in
                    yes|no) result=$value ;;
                    *) result="[unrecognized]" ;;
                esac
                ;;
        esac
    done < "$file"
    printf '%s' "$result"
}

for relative in /etc/synoinfo.conf /etc.defaults/synoinfo.conf; do
    printf '%s\n' "$relative"
    for key in pkg_def_intall_vol package_update_channel \
        enable_pkg_autoupdate_all pkg_autoupdate_all pkg_autoupdate_important \
        upgrade_pkg_email_notification upgrade_pkg_dsm_notification; do
        printf '  %s=%s\n' "$key" "$(read_setting "$root$relative" "$key")"
    done
done
