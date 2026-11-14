#!/usr/bin/env bash
# Source this file to install local packages on a selected DSM data volume.

volume_require_tools(){
    if ! command -v jq >/dev/null 2>&1 ||
            [[ ! -x /usr/syno/bin/synowebapi ]] ||
            [[ ! -x /usr/syno/bin/synopkg ]]; then
        echo "Volume selection requires jq, synowebapi, and synopkg on the NAS." >&2
        return 1
    fi
}

volume_webapi(){
    /usr/syno/bin/synowebapi --exec "$@"
}

volume_package_status(){
    /usr/syno/bin/synopkg status "$1" >/dev/null 2>&1
}

volume_package_target(){
    readlink -f "/var/packages/$1/target"
}

volume_is_mounted(){
    # Check the mount itself; a directory left behind after unmounting is unsafe.
    awk -v target="$1" '
        $2 == target && $4 ~ /(^|,)rw(,|$)/ { found = 1 }
        END { exit !found }
    ' /proc/mounts
}

volume_encode_string(){
    jq -cn --arg value "$1" '$value'
}

volume_api_call(){
    local output reply
    if ! output=$(volume_webapi "$@"); then
        echo "The package API command failed." >&2
        return 1
    fi
    # Reject malformed output and multiple documents. The command can print a
    # banner before its JSON response; do not discard arbitrary diagnostic text.
    if ! reply=$(printf '%s\n' "$output" |
            sed '/^\[Line [0-9][0-9]*\] Exec WebAPI:/d' |
            jq -ces '
                if length == 1 and (.[0] | type == "object") and
                   .[0].success == true and
                   (.[0].data | type == "object") and
                   all(.[0] | .. | objects | select(has("success")); .success == true) and
                   all(.[0] | .. | objects | select(has("has_fail")); .has_fail == false) and
                   all(.[0] | .. | objects | select(has("error"));
                       (.error == null) or (.error.code == 0))
                then .[0] else error("unsuccessful package API response") end
            ' 2>/dev/null); then
        echo "The package API did not return a valid successful response." >&2
        return 1
    fi
    printf '%s\n' "$reply"
}

volume_check_target(){
    local volume="$1" reply
    if [[ ! $volume =~ ^/volume[1-9][0-9]*$ ]]; then
        echo "Use a DSM data volume path such as /volume1." >&2
        return 1
    fi
    if ! volume_require_tools || ! volume_is_mounted "$volume"; then
        echo "The selected volume must be mounted and writable." >&2
        return 1
    fi
    reply=$(volume_api_call api=SYNO.Core.Package.Setting method=get version=1) || return 1
    if ! printf '%s\n' "$reply" | jq -e --arg volume "$volume" '
            (.data.volume_list | type == "array") and
            any(.data.volume_list[]; .mount_point == $volume)
            ' >/dev/null 2>&1; then
        echo "Package Center does not list the selected installation volume." >&2
        return 1
    fi
}

volume_install_spk(){
    # $1: downloaded package path; $2: package ID; $3: requested data volume.
    local spk="$1" package="$2" volume="$3" reply encoded_id encoded_path encoded_volume
    local target code attempt
    if [[ ! $package =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] ||
            [[ $spk != /* || ! -f $spk || ! -s $spk ]]; then
        echo "A package ID and a nonempty local package file are required." >&2
        return 1
    fi
    volume_check_target "$volume" || return 1
    encoded_id=$(volume_encode_string "$package") || return 1
    encoded_path=$(volume_encode_string "$spk") || return 1
    encoded_volume=$(volume_encode_string "$volume") || return 1
    reply=$(volume_api_call api=SYNO.Core.Package.Installation method=check version=1 \
        "id=$encoded_id" 'install_type=""' install_on_cold_storage=false \
        breakpkgs=null blCheckDep=false replacepkgs=null) || return 1
    if ! printf '%s\n' "$reply" | jq -e --arg volume "$volume" '
            .data.is_occupied == false and
            (.data.volume_list | type == "array") and
            any(.data.volume_list[]; .mount_point == $volume)
            ' >/dev/null 2>&1; then
        echo "The package pre-check did not allow the selected volume." >&2
        return 1
    fi
    reply=$(volume_api_call api=SYNO.Core.Package.Installation method=install version=1 \
        type=0 "volume_path=$encoded_volume" "path=$encoded_path" \
        check_codesign=true force=false installrunpackage=true 'extra_values="{}"') || return 1
    if ! printf '%s\n' "$reply" | jq -e '
            (.data.packageName | type == "string" and length > 0) and
            (.data | has("task_id") or has("taskid") | not) and
            (.data.finished != false)
            ' >/dev/null 2>&1; then
        echo "The local installation API did not report a completed installation." >&2
        return 1
    fi
    # Local installation is synchronous in the documented API. A task acceptance
    # response is not proof of success; registration and the final target must
    # appear before the caller changes package metadata or restarts services.
    for ((attempt=0; attempt<30; attempt++)); do
        if volume_package_status "$package"; then code=0; else code=$?; fi
        target=$(volume_package_target "$package")
        if [[ $code == 0 || $code == 17 || $code == 55 ]] &&
                [[ $target == "$volume/@appstore/$package" ]]; then
            return 0
        fi
        sleep 1
    done
    echo "Installation was not confirmed on the selected volume; inspect Package Center before retrying." >&2
    return 1
}
