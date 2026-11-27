#!/usr/bin/env bash
#------------------------------------------------------------------------------
# https://www.synology.com/en-au/releaseNote/VideoStation
# https://www.synology.com/en-au/releaseNote/CodecPack
# https://www.synology.com/en-au/releaseNote/MediaServer
# https://www.synology.com/en-au/releaseNote/DSM
#
# Video Station does not support TrueHD or DTS audio.
# Video Station does not decode AAC audio.
#------------------------------------------------------------------------------
# https://archive.synology.com/download/Package
# https://web.archive.org/web/20240825163306/https://archive.synology.com/download/Package
#------------------------------------------------------------------------------
# To get Video Station to work I needed to install an older version of AME...
# which means Drive and Surveillance Station may not work
# (unless I install older versions of them).
#------------------------------------------------------------------------------
# I've seen evidence of:
#   VideoStation="3.2.0-3173" (when you try to manually install 3.1.1)
#   CodecPack="4.0.0-4003"
# It looks like Synology were developing a new video station for DSM 7.2.2
# before someone decided to scrap it and cannibalise AME to save a few dollars
#------------------------------------------------------------------------------
# TODO
# Figure out where package center saves it's settings
# Figure out how to run VideoStation 3.1.1-3168 with CodecPack 3.1.0-3005
#   or add OpenSubtitle changes from 3.1.1-3168 to 3.1.0-3153
#------------------------------------------------------------------------------

scriptver="v1.4.22-hbt.2"
script=Video_Station_for_DSM_722
repo="HoneyBearTech/Video_Station_for_DSM_722"

ding(){ 
    printf \\a
}

# Save options used for getopt
args=("$@")

usage(){ 
    cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -h, --help            Show this help message
  -v, --version         Show the script version
  -t, --trace           Show which script functions are called
      --volume=/volumeN Install packages that need installing on volume N
                        (e.g. --volume=/volume2). Needs the lib folder that
                        comes with this script. See docs/package-volume.md
      --install=OPTION  Automatically install OPTION (for use when scheduled)
                        OPTION can be either: 
                          'all' to install Video Station, Media Server and
                            Advanced Media Codecs
                          'novs' to install all except Video Station
                          'noms' to install all except Media Server
                          'onlyamc' to only install Advanced Media Codecs
                        Examples:
                          videostation_for_722.sh --install=all
                          videostation_for_722.sh --install=novs
                          videostation_for_722.sh --install=noms
                          videostation_for_722.sh --install=onlyamc
                          videostation_for_722.sh --install=all --volume=/volume2

EOF
}

scriptversion(){ 
    cat <<EOF
$script $scriptver - by 007revad

See https://github.com/$repo
EOF
    exit 0
}


install_volume=""
install_choice=""

# Check for flags with getopt
if options="$(getopt -o hvt -l \
    install:,volume:,help,version,trace -- "${args[@]}")"; then
    eval set -- "$options"
    while true; do
        case "${1,,}" in
            -h|--help)          # Show usage options
                usage
                exit
                ;;
            -v|--version)       # Show script version
                scriptversion
                ;;
            -t|--trace)         # Show which functions are called
                trace="yes"
                ;;
            --volume)           # Volume to install packages on
                if [[ ! $2 =~ ^/volume[1-9][0-9]*$ ]]; then
                    ding
                    echo -e "Invalid --volume value '$2' (use /volume1, /volume2 etc)\n"
                    usage
                    exit 2  # Invalid argument
                fi
                install_volume="$2"
                shift
                ;;
            --install)             # Specify pkgs to install or skip
                color=no        # Disable colour text in task scheduler emails
                if [[ ${2,,} == "all" ]]; then
                    auto="yes"
                    choice="Installing All"
                elif [[ ${2,,} == "novs" ]]; then
                    auto="yes"
                    no_vs="yes"
                    choice="Skipping Video Station"
                elif [[ ${2,,} == "noms" ]]; then
                    auto="yes"
                    no_ms="yes"
                    choice="Skipping Media Server"
                elif [[ ${2,,} == "onlyamc" ]]; then
                    auto="yes"
                    no_vs="yes"
                    no_ms="yes"
                    choice="Only installing Advanced Media Codecs"
                else
                    ding
                    echo -e "Invalid --install value '$2'\n"
                    usage
                    exit 2  # Invalid argument
                fi
                install_choice="${2,,}"
                shift
                ;;
            --)
                shift
                break
                ;;
            *)                  # Show usage options
                ding
                echo -e "Invalid option '$1'\n"
                usage
                exit 2  # Invalid argument
                ;;
        esac
        shift
    done
else
    echo
    usage
    exit 2  # Invalid option
fi

# Nothing is allowed after the options
if [[ $# -gt "0" ]]; then
    ding
    echo -e "Unexpected argument '$1'\n"
    usage
    exit 2  # Invalid argument
fi

# Check script is running as root
if [[ $( whoami ) != "root" ]]; then
    ding
    echo -e "${Error}ERROR${Off} This script must be run as sudo or root!"
    exit 1  # Not running as sudo or root
fi

# Get NAS model
model=$(cat /proc/sys/kernel/syno_hw_version)
#modelname="$model"


# Show script version
#echo -e "$script $scriptver\ngithub.com/$repo\n"
echo "$script $scriptver"

# Get DSM full version
productversion=$(/usr/syno/bin/synogetkeyvalue /etc.defaults/VERSION productversion)
buildphase=$(/usr/syno/bin/synogetkeyvalue /etc.defaults/VERSION buildphase)
buildnumber=$(/usr/syno/bin/synogetkeyvalue /etc.defaults/VERSION buildnumber)
smallfixnumber=$(/usr/syno/bin/synogetkeyvalue /etc.defaults/VERSION smallfixnumber)

# Get CPU arch and platform_name
arch="$(uname -m)"
platform_name=$(/usr/syno/bin/synogetkeyvalue /etc.defaults/synoinfo.conf platform_name)

# Show DSM full version and model
if [[ $buildphase == GM ]]; then buildphase=""; fi
if [[ $smallfixnumber -gt "0" ]]; then smallfix="-$smallfixnumber"; fi
echo "$model DSM $productversion-$buildnumber$smallfix $buildphase"

# Show CPU arch and platform_name
echo "CPU $platform_name $arch"

# Show options used
if [[ ${#args[@]} -gt "0" ]]; then
    echo -e "Using options: ${args[*]}\n"
else
    echo ""
fi


# Shell Colors
if [[ $color != "no" ]]; then
    #Black='\e[0;30m'   # ${Black}
    #Red='\e[0;31m'      # ${Red}
    #Green='\e[0;32m'   # ${Green}
    #Yellow='\e[0;33m'   # ${Yellow}
    #Blue='\e[0;34m'    # ${Blue}
    #Purple='\e[0;35m'  # ${Purple}
    Cyan='\e[0;36m'     # ${Cyan}
    #White='\e[0;37m'   # ${White}
    Error='\e[41m'      # ${Error}
    #Warn='\e[47;31m'   # ${Warn}
    Off='\e[0m'         # ${Off}
fi


#------------------------------------------------------------------------------

# Get script location
# https://stackoverflow.com/questions/59895/
source=${BASH_SOURCE[0]}
while [ -L "$source" ]; do # Resolve $source until the file is no longer a symlink
    scriptpath=$( cd -P "$( dirname "$source" )" >/dev/null 2>&1 && pwd )
    source=$(readlink "$source")
    # If $source was a relative symlink, we need to resolve it
    # relative to the path where the symlink file was located
    [[ $source != /* ]] && source=$scriptpath/$source
done
scriptpath=$( cd -P "$( dirname "$source" )" >/dev/null 2>&1 && pwd )
scriptfile=$( basename -- "$source" )
echo "Running from: ${scriptpath}/$scriptfile"

#------------------------------------------------------------------------------

# Check script is needed
if [[ $buildnumber -lt "72803" ]]; then
    echo -e "\nYour DSM version does not need this script"
    exit
fi

# Check model is supported
spks_list=("armada37xx" "armada38x" "armv7" "monaco" "rtd1296" "rtd1619b" "x86_64")
if [[ ${spks_list[*]} =~ $arch ]]; then
    cputype="$arch"
elif [[ ${spks_list[*]} =~ $platform_name ]]; then
    cputype="$platform_name"
elif [[ $platform_name == "alpine" || $platform_name == "alpine4k" ]]; then
    # DS1817, DS1517 and DS416
    cputype="armv7"
else
    echo -e "\nUnsupported or unknown CPU platform_name or architecture"
    echo "  - CPU type: $cputype"
    echo "  - Platform: $platform_name"
    echo -e "Please see:"
    echo -e "https://github.com/$repo\n"
    exit
fi
echo "Using CPU type: $cputype"

safe_to_source(){ 
    # $1 is a file or folder that root will read code from
    # Owned by the user running the script (root) and not group- or world-writable
    local mode
    if [[ -L $1 ]] || [[ ! -O $1 ]]; then
        return 1
    fi
    # Only the mode column is read; ls -ld works the same on every DSM version
    # shellcheck disable=SC2012
    mode=$(ls -ld -- "$1" 2>/dev/null | cut -c1-10)
    if [[ ${#mode} != "10" ]] || [[ ${mode:5:1} != "-" ]] || [[ ${mode:8:1} != "-" ]]; then
        return 1
    fi
}

# Check the volume set with --volume before downloading or changing anything
if [[ -n $install_volume ]]; then
    if [[ ! -f "$scriptpath/lib/package_volume.sh" ]]; then
        ding
        echo -e "${Error}ERROR${Off} --volume needs $scriptpath/lib/package_volume.sh"
        echo "Copy the lib folder that comes with this script into the same folder as the script."
        echo "Nothing was changed on the NAS."
        exit 2
    fi
    # This file runs as root, so only root may be able to change it
    for libpath in "$scriptpath/lib" "$scriptpath/lib/package_volume.sh"; do
        if ! safe_to_source "$libpath"; then
            ding
            echo -e "${Error}ERROR${Off} --volume won't load $libpath"
            echo "It must be owned by root, not a link, and not writable by group or others,"
            echo "because it runs as root and anyone who can change it could run commands as root."
            echo "To fix it, run:"
            echo "  sudo chown -R root:root $(printf '%q' "$scriptpath/lib")"
            echo "  sudo chmod -R go-w $(printf '%q' "$scriptpath/lib")"
            echo "Nothing was changed on the NAS."
            exit 2
        fi
    done
    # shellcheck source=lib/package_volume.sh
    if ! source "$scriptpath/lib/package_volume.sh"; then
        ding
        echo -e "${Error}ERROR${Off} Failed to load $scriptpath/lib/package_volume.sh"
        echo "Nothing was changed on the NAS."
        exit 2
    fi
    if ! volume_require_tools || ! volume_check_target "$install_volume"; then
        ding
        echo -e "${Error}ERROR${Off} Packages can't be installed on $install_volume"
        echo "It must be mounted read-write and listed by Package Center."
        echo "Nothing was changed on the NAS."
        exit 2
    fi
    echo "Packages that need installing will be installed on: $install_volume"
    echo "Packages that are already the right version stay where they are."
fi

#------------------------------------------------------------------------------

cleanup(){ 
    arg1=$?
    # Delete this run's private download folder
    if [[ -n $workdir ]]; then
        rm -rf -- "$workdir"
    fi
    exit "${arg1}"
}

workdir=""
trap cleanup EXIT

# Private download folder for this run (only root can read it)
if ! workdir=$(mktemp -d /tmp/vs722.XXXXXX); then
    workdir=""
    ding
    echo -e "${Error}ERROR${Off} Failed to create the private download folder in /tmp!"
    echo "Nothing was changed on the NAS."
    exit 1
fi

progbar(){ 
    # $1 is pid of process
    # $2 is string to echo
    string="$2"
    local dots
    local progress
    dots=""
    while [[ -d /proc/$1 ]]; do
        dots="${dots}."
        progress="$dots"
        if [[ ${#dots} -gt "10" ]]; then
            dots=""
            progress="           "
        fi
        echo -ne "  ${2}$progress\r"; sleep 0.3
    done
}

progstatus(){ 
    # $1 is return status of process
    # $2 is string to echo
    # $3 line number function was called from
    local tracestring
    local pad
    tracestring="${FUNCNAME[0]} called from ${FUNCNAME[1]} $3"
    pad=$(printf -- ' %.0s' {1..80})
    [ "$trace" == "yes" ] && printf '%.*s' 80 "${tracestring}${pad}" && echo ""
    if [[ $1 == "0" ]]; then
        echo -e "$2            "
    else
        ding
        echo -e "Line ${LINENO}: ${Error}ERROR${Off} $2 failed!"
        echo "$tracestring"
        if [[ $exitonerror != "no" ]]; then
            exit 1  # Skip exit if exitonerror != no
        fi
    fi
    exitonerror=""
    #echo "return: $1"  # debug
}

package_status(){ 
    # $1 is package name
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    /usr/syno/bin/synopkg status "${1}" >/dev/null
    code="$?"
    # DSM 7.2       0 = started, 55 = starting, 17 = stopped, 255 = not_installed, 150 = broken
    # DSM 6 to 7.1  0 = started,  4 = starting,  3 = stopped,   4 = not_installed, 150 = broken
    if [[ $code == "0" ]]; then
        #echo "$1 is started"  # debug
        return 0
    elif [[ $code == "55" ]]; then
        #echo "$1 is starting"  # debug
        return 55
    elif [[ $code == "17" ]] || [[ $code == "3" ]]; then
        #echo "$1 is stopped"  # debug
        return 1
    elif [[ $code == "255" ]] || [[ $code == "4" ]]; then
        #echo "$1 is not installed"  # debug
        return 255
    elif [[ $code == "150" ]]; then
        #echo "$1 is broken"  # debug
        return 150
    else
        return "$code"
    fi
}

check_pkg_installed(){ 
    # $1 is package
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    /usr/syno/bin/synopkg status "${1:?}" >/dev/null
    code="$?"
    if [[ $code == "255" ]] || [[ $code == "4" ]]; then
        return 1
    else
        return 0
    fi
}

package_is_running(){ 
    # $1 is package name
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    /usr/syno/bin/synopkg is_onoff "${1}" >/dev/null
    code="$?"
    return "$code"
}

wait_status(){ 
    # Wait for package to finish stopping or starting
    # $1 is package
    # $2 is start or stop
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    local num
    if [[ $2 == "start" ]]; then
        state="0"
    elif [[ $2 == "stop" ]]; then
        state="1"
    fi
    if [[ $state == "0" ]] || [[ $state == "1" ]]; then
        num="0"
        package_status "$1"
        while [[ $? != "$state" ]]; do
            sleep 1
            num=$((num +1))
            if [[ $num -gt "20" ]]; then
                break
            fi
            package_status "$1"
        done
    fi
}

package_stop(){ 
    # $1 is package name
    # $2 is package display name
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    timeout 5m /usr/syno/bin/synopkg stop "$1" >/dev/null &
    pid=$!
    #string="Stopping ${Cyan}${2}${Off}"
    string="Stopping ${2}"
    progbar "$pid" "$string"
    wait "$pid"
    progstatus "$?" "$string" "line ${LINENO}"

    # Allow package processes to finish stopping
    wait_status "$1" stop
}

package_start(){ 
    # $1 is package name
    # $2 is package display name
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    timeout 5m /usr/syno/bin/synopkg start "$1" >/dev/null &
    pid=$!
    #string="Starting ${Cyan}${2}${Off}"
    string="Starting ${2}"
    progbar "$pid" "$string"
    wait "$pid"
    progstatus "$?" "$string" "line ${LINENO}"

    # Allow package processes to finish starting
    wait_status "$1" start
}

package_uninstall(){ 
    # $1 is package name
    # $2 is package display name
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    /usr/syno/bin/synopkg uninstall "$1" >/dev/null &
    pid=$!
    string="Uninstalling ${Cyan}${2}${Off}"
    progbar "$pid" "$string"
    wait "$pid"
    progstatus "$?" "$string" "line ${LINENO}"
}

package_install(){ 
    # $1 is package filename
    # $2 is package display name
    # $3 is package ID (CodecPack, VideoStation or MediaServer)
    [ "$trace" == "yes" ] && echo "${FUNCNAME[0]} called from ${FUNCNAME[1]}"
    local code
    if [[ -n $install_volume ]]; then
        volume_install_spk "${workdir:?}/$1" "${3:?}" "$install_volume" >/dev/null &
        pid=$!
        string="Installing ${Cyan}${2}${Off} on ${Cyan}$install_volume${Off}"
    else
        /usr/syno/bin/synopkg install "${workdir:?}/$1" >/dev/null &
        pid=$!
        string="Installing ${Cyan}${2}${Off}"
    fi
    progbar "$pid" "$string"
    wait "$pid"
    code="$?"
    if [[ $code != "0" ]] && [[ -n $install_volume ]]; then
        exitonerror="no"
        progstatus "$code" "$string" "line ${LINENO}"
        volume_install_failed "$2"
        exit 1
    fi
    progstatus "$code" "$string" "line ${LINENO}"
}

pkg_name(){ 
    # $1 is package ID
    case "$1" in
        CodecPack)    echo "Advanced Media Extensions" ;;
        VideoStation) echo "Video Station" ;;
        MediaServer)  echo "Media Server" ;;
        *)            echo "$1" ;;
    esac
}

volume_install_failed(){ 
    # $1 is display name of the package that failed to install
    # Re-read each package's state and only say what is confirmed,
    # then say how to finish without --volume
    local pkg
    local code
    local version
    local target
    local missing
    local uncertain
    local changed
    local rerun
    missing=()
    uncertain="no"
    changed="no"
    echo ""
    echo -e "${Error}ERROR${Off} $1 could not be installed on $install_volume"
    echo "What DSM reports now:"
    for pkg in CodecPack VideoStation MediaServer; do
        case "$pkg" in
            CodecPack)    [[ $need_ame == "yes" ]] || [[ -n ${versions_before[$pkg]} ]] || continue ;;
            VideoStation) [[ $need_vs == "yes" ]] || [[ -n ${versions_before[$pkg]} ]] || continue ;;
            MediaServer)  [[ $need_ms == "yes" ]] || [[ -n ${versions_before[$pkg]} ]] || continue ;;
        esac
        /usr/syno/bin/synopkg status "$pkg" >/dev/null 2>&1
        code="$?"
        if [[ $code == "255" ]] || [[ $code == "4" ]]; then
            if [[ -n ${versions_before[$pkg]} ]]; then
                echo "  - $(pkg_name "$pkg"): not installed (was ${versions_before[$pkg]} when this run started)"
                missing+=("$pkg")
            else
                echo "  - $(pkg_name "$pkg"): not installed"
            fi
        elif [[ $code == "0" ]] || [[ $code == "17" ]] || [[ $code == "3" ]] || [[ $code == "55" ]]; then
            version=$(/usr/syno/bin/synopkg version "$pkg" 2>/dev/null)
            if [[ -n ${versions_before[$pkg]} ]] && [[ $version != "${versions_before[$pkg]}" ]]; then
                # Removed and installed again
                changed="yes"
            fi
            target=$(volume_package_target "$pkg" 2>/dev/null)
            if [[ $target == "$install_volume/@appstore/$pkg" ]]; then
                echo "  - $(pkg_name "$pkg"): installed ($version) on $install_volume"
            elif [[ -n $target ]]; then
                echo "  - $(pkg_name "$pkg"): installed ($version) but not on $install_volume (it is in $target)"
            else
                echo "  - $(pkg_name "$pkg"): installed ($version) but not on $install_volume (where is not known)"
            fi
        else
            echo "  - $(pkg_name "$pkg"): state uncertain (synopkg status $code) - check Package Center"
            uncertain="yes"
        fi
    done
    if [[ ${#missing[@]} -gt "0" ]]; then
        echo "This run removed:"
        for pkg in "${missing[@]}"; do
            echo "  - $(pkg_name "$pkg") ${versions_before[$pkg]}"
        done
    elif [[ $uncertain == "yes" ]]; then
        echo "Check Package Center to see what this run changed."
    elif [[ $changed == "no" ]]; then
        echo "This run did not remove any package."
    else
        echo "No package that was installed before this run is missing now."
    fi
    rerun="sudo bash $(printf '%q' "${scriptpath}/$scriptfile")"
    if [[ -n $install_choice ]]; then
        rerun="$rerun --install=$install_choice"
    fi
    echo "To install the packages on Package Center's default volume, run the script again without --volume:"
    echo "  $rerun"
}

pkg_sha256(){ 
    # $1 is the package file name
    # SHA-256 of each package file as downloaded from Synology (certificate check on)
    case "$1" in
        CodecPack-armada37xx-3.1.0-3005.spk)
            echo "5db7166d7186004e72eb8bc2d650a8dd8a17760afe141c9dc3aedec13bf0119b" ;;
        CodecPack-armada38x-3.1.0-3005.spk)
            echo "496a6276aa7bf79fcdca238d6078bf890b25384ff445b357165b8766111b5717" ;;
        CodecPack-armv7-3.1.0-3005.spk)
            echo "e38bb5dc81b7ac4551162c42ae2e3f2cf64b767624669bf65ca0dd53dbb9a185" ;;
        CodecPack-monaco-3.1.0-3005.spk)
            echo "b6917fadbcc5f8c26a1a6cd694ffe9928fcaba0890df3dad9827a27ad5169e90" ;;
        CodecPack-rtd1296-3.1.0-3005.spk)
            echo "6c46f434c02f0a56071844ec67fd91051179f543a18457d6b7e22bee9c13a743" ;;
        CodecPack-rtd1619b-3.1.0-3005.spk)
            echo "d50b70dc1d89c607cd545d5ab70b6d047355cf13aa628823ef63079b3b54d44d" ;;
        CodecPack-x86_64-3.1.0-3005.spk)
            echo "c4dcb4ab66cdd83cba7dcb909658bb239feab0325bfa794e3925c87e8656b85a" ;;
        VideoStation-armada37xx-3.1.0-3153.spk)
            echo "cc5070f3d6794ec6740301e7cc8698cd100d49d008ac634d37aeaf77912ab977" ;;
        VideoStation-armada38x-3.1.0-3153.spk)
            echo "e93727ea8495753017dc635ed352b40a1dec14995eda9cf7d7bd045c9357928f" ;;
        VideoStation-armv7-3.1.0-3153.spk)
            echo "5b4cfc4bd43b0c4f896a38f850f09d4673ae49e9d72eeea0180865d9a7e28230" ;;
        VideoStation-monaco-3.1.0-3153.spk)
            echo "8c1dd917b28c9184ef5bcecf6087e24d48ea65fd0ad457f37f9e03ae95236963" ;;
        VideoStation-rtd1296-3.1.0-3153.spk)
            echo "4f94403b959c1697ea1b21b5decff4777201ada72370dd31c45ecbadcdf00d4d" ;;
        VideoStation-rtd1619b-3.1.0-3153.spk)
            echo "d38267b4cdae6f2e69ba45a76aa9554cfbd5b503264783c68284f060f80325fd" ;;
        VideoStation-x86_64-3.1.0-3153.spk)
            echo "e9b1a4935e255aac649953fa6b8a10ebcb3114970552dcf00b9ff93d62065715" ;;
        MediaServer-armada37xx-2.0.5-3152.spk)
            echo "17e11f8146a62712861cb1c8df9a223a5eee02fe7ea08cd86899ba2d3f4366a8" ;;
        MediaServer-armada38x-2.0.5-3152.spk)
            echo "3d90c6157b7e01bb2c46901f35224a8d7530bf28b69db2e48c0daf070b6cda53" ;;
        MediaServer-armv7-2.0.5-3152.spk)
            echo "87da07b1d33b56c2186b682a1dbb313d4f4889fae39947c34276fce951ba379b" ;;
        MediaServer-monaco-2.0.5-3152.spk)
            echo "5e8aa508b5ae772bc30356e8e39b86e4b215b4b67fa2898b4b7d63f37b9259b1" ;;
        MediaServer-rtd1296-2.0.5-3152.spk)
            echo "fa82ac4d020ffd7b79d793191bdda102b3866434c6879ce47a69d29c17f4364a" ;;
        MediaServer-rtd1619b-2.0.5-3152.spk)
            echo "62c467ddc566f8c5afee6ba2be05ff029cc9a09c1926c51aa9a6eab355e51564" ;;
        MediaServer-x86_64-2.0.5-3152.spk)
            echo "38e77b230f339e78721e7bdb7543ed56c48ff84564665220dcd62baa5fb32e8e" ;;
        *)
            return 1 ;;
    esac
}

download_pkg(){ 
    # $1 is the package folder name
    # $2 is the package version to download
    # $3 is the package file to download
    
    # https://cndl.synology.cn/download/Package/spk/VideoStation/3.1.0-3153/VideoStation-x86_64-3.1.0-3153.spk
    # https://global.synologydownload.com/download/Package/spk/VideoStation/3.1.0-3153/VideoStation-x86_64-3.1.0-3153.spk

    local url
    local host
    local file
    local expected
    local actual
    local curlcode

    # Can't check the download without sha256sum
    if ! command -v sha256sum >/dev/null 2>&1; then
        ding
        echo -e "${Error}ERROR 3${Off} sha256sum not found so ${3:?} can't be checked!"
        echo "Nothing was changed on the NAS."
        exit 3
    fi

    file="${workdir:?}/${3:?}"
    expected=$(pkg_sha256 "$3")

    language=$(synogetkeyvalue /etc/synoinfo.conf language)
    if [[ $language =~ chs|cht ]] && readlink -q /etc/localtime | grep -iq china;
    then
        # Try China download site first for Chinese users
        bases=("https://cndl.synology.cn/download/Package/spk/")
        bases+=("https://global.synologydownload.com/download/Package/spk/")
        bases+=("https://global.download.synology.com/download/Package/spk/")
    else
        bases=("https://global.synologydownload.com/download/Package/spk/")
        bases+=("https://global.download.synology.com/download/Package/spk/")
        bases+=("https://cndl.synology.cn/download/Package/spk/")
    fi
    # Never reuse a file that is already there
    rm -f -- "$file"
    for base in "${bases[@]}"; do
        url="${base}${1:?}/${2:?}/${3}"
        host=$(echo "$base" | cut -d"/" -f3)
        echo -en "\nDownloading ${Cyan}${3}${Off} from "
        echo "$host"
        curl -q -fL --proto '=https' --proto-redir '=https' --connect-timeout 30 --retry 1 "$url" -o "$file"
        curlcode=$?
        if [[ $curlcode != "0" ]]; then
            # Delete partial download
            rm -f -- "$file"
            if [[ $curlcode == "60" ]] || [[ $curlcode == "77" ]]; then
                echo -e "${Error}ERROR${Off} Certificate check failed for $host!"
                echo "Check the NAS date and time are correct, and update DSM."
            else
                echo -e "${Error}ERROR${Off} Failed to download ${3} from $host (curl exit code $curlcode)!"
            fi
            continue
        fi
        if [[ -z $expected ]]; then
            rm -f -- "$file"
            echo -e "${Error}ERROR${Off} No SHA-256 checksum is recorded for ${3}!"
            continue
        fi
        actual=$(sha256sum "$file" 2>/dev/null | cut -d" " -f1)
        if [[ $actual != "$expected" ]]; then
            rm -f -- "$file"
            echo -e "${Error}ERROR${Off} SHA-256 checksum check failed for ${3} from $host!"
            echo "  Expected: $expected"
            echo "  Actual:   $actual"
            continue
        fi
        echo "SHA-256 checksum OK"
        return 0
    done
    rm -f -- "$file"
    ding
    echo -e "${Error}ERROR 3${Off} Failed to download ${3}!"
    echo "Nothing was changed on the NAS."
    exit 3
}

need_pkg_file(){ 
    # $1 is the package file that must already be downloaded and checked
    if [[ ! -f "${workdir:?}/${1:?}" ]]; then
        ding
        echo -e "${Error}ERROR${Off} ${1} was not downloaded before changes were made!"
        exit 1
    fi
}


# Only install the packages the user wants
echo ""
if [[ $auto != "yes" ]]; then
    PS3="Select package(s) to install: "
    options=("Install All" "Only Advanced Media Codecs" "Skip Video Station" "Skip Media Server")
    TMOUT=20  # Timeout and install all if no choice made within 20 seconds (for task scheduler)
    select choice in "${options[@]}"; do
        case "$choice" in
            "Install All")
                break
            ;;
            "Skip Video Station")
                no_vs="yes"
                break
            ;;
            "Skip Media Server")
                no_ms="yes"
                break
            ;;
            "Only Advanced Media Codecs")
                no_vs="yes"
                no_ms="yes"
                break
            ;;
            "")
                echo "Invalid Choice!"
                ;;
            *)
                break
            ;;
        esac
    done
    unset TMOUT
    if [[ -z "$choice" ]]; then
        echo "No selection made. Installing all packages."
    else
        echo -e "You selected: ${Cyan}$choice${Off}"
    fi
else
    echo "$choice"
fi


# Work out which packages may be needed (this does not change anything)
need_ame=""
need_vs=""
need_ms=""
ame_version=$(/usr/syno/bin/synopkg version CodecPack)
if ! check_pkg_installed CodecPack || [[ ${ame_version:0:1} -gt "3" ]]; then
    need_ame="yes"
fi
if [[ $no_vs != "yes" ]]; then
    vs_version=$(/usr/syno/bin/synopkg version VideoStation)
    if ! check_pkg_installed VideoStation || [[ ${vs_version} != "30.1.0-3153" ]]; then
        need_vs="yes"
    elif [[ ${ame_version:0:1} -gt "3" ]]; then
        # Uninstalling AME v4 could also remove Video Station
        need_vs="yes"
    fi
fi
if [[ $no_ms != "yes" ]]; then
    ms_version=$(/usr/syno/bin/synopkg version MediaServer)
    if ! check_pkg_installed MediaServer || [[ ${ms_version} != "20.0.5-3152" ]]; then
        need_ms="yes"
    elif [[ ${ame_version:0:1} -gt "3" ]]; then
        # Uninstalling AME v4 could also remove Media Server
        need_ms="yes"
    fi
fi

# Ask DSM if each package can go on the --volume volume, before any change
declare -A versions_before=()
if [[ -n $install_volume ]]; then
    for pkg in CodecPack VideoStation MediaServer; do
        if check_pkg_installed "$pkg"; then
            versions_before[$pkg]=$(/usr/syno/bin/synopkg version "$pkg")
        fi
    done
    for pkg in CodecPack VideoStation MediaServer; do
        case "$pkg" in
            CodecPack)    [[ $need_ame == "yes" ]] || continue ;;
            VideoStation) [[ $need_vs == "yes" ]] || continue ;;
            MediaServer)  [[ $need_ms == "yes" ]] || continue ;;
        esac
        volume_check_package "$pkg" "$install_volume" 2>/dev/null
        code="$?"
        if [[ $code == "0" ]]; then
            continue
        elif [[ $code == "3" ]]; then
            ding
            echo -e "${Error}ERROR${Off} DSM refused to install $(pkg_name "$pkg") on $install_volume"
            echo "Nothing was changed on the NAS."
            exit 2
        elif [[ -n ${versions_before[$pkg]} ]]; then
            # DSM may not answer for a package that is still installed
            echo "Note: DSM could not check $(pkg_name "$pkg") for $install_volume while it is installed."
            echo "      It is checked again just before it is installed."
        else
            ding
            echo -e "${Error}ERROR${Off} DSM could not check if $(pkg_name "$pkg") can be installed on $install_volume"
            echo "Nothing was changed on the NAS."
            exit 2
        fi
    done
fi

# Download and check every package needed before changing anything
if [[ $need_ame == "yes" ]]; then
    download_pkg CodecPack "3.1.0-3005" "CodecPack-${cputype}-3.1.0-3005.spk"
fi
if [[ $need_vs == "yes" ]]; then
    #download_pkg VideoStation "3.1.1-3168" "VideoStation-${cputype}-3.1.0-3168.spk"
    download_pkg VideoStation "3.1.0-3153" "VideoStation-${cputype}-3.1.0-3153.spk"
fi
if [[ $need_ms == "yes" ]]; then
    download_pkg MediaServer "2.0.5-3152" "MediaServer-${cputype}-2.0.5-3152.spk"
fi


# Backup synopackageslimit.conf if needed
if [[ ! -f /etc.defaults/synopackageslimit.conf.bak ]]; then
    cp -p /etc.defaults/synopackageslimit.conf /etc.defaults/synopackageslimit.conf.bak
fi

# Make DSM let us install the packages we want
/usr/syno/bin/synosetkeyvalue /etc.defaults/synopackageslimit.conf VideoStation "3.1.0-3153"
/usr/syno/bin/synosetkeyvalue /etc/synopackageslimit.conf VideoStation "3.1.0-3153"

/usr/syno/bin/synosetkeyvalue /etc.defaults/synopackageslimit.conf CodecPack "3.1.0-3005"
/usr/syno/bin/synosetkeyvalue /etc/synopackageslimit.conf CodecPack "3.1.0-3005"

/usr/syno/bin/synosetkeyvalue /etc.defaults/synopackageslimit.conf MediaServer "2.0.5-3152"
/usr/syno/bin/synosetkeyvalue /etc/synopackageslimit.conf MediaServer "2.0.5-3152"

# Uninstall AME v4 if installed
if [[ ${ame_version:0:1} -gt "3" ]]; then
    # Uninstall AME v4
    echo ""
    package_uninstall CodecPack "Advanced Media Extensions"
fi

# Uninstall VideoStation if wrong version
if [[ $no_vs != "yes" ]]; then
    #if check_pkg_installed VideoStation && [[ ${vs_version:0:2} != "30" ]]; then
    if check_pkg_installed VideoStation && [[ ${vs_version} != "30.1.0-3153" ]]; then
        # Uninstall VideoStation (wrong version)
        echo ""
        package_uninstall VideoStation "Video Station"
    fi
fi

# Uninstall MediaServer if wrong version
if [[ $no_ms != "yes" ]]; then
    #if check_pkg_installed MediaServer && [[ ${ms_version:0:2} != "20" ]]; then
    if check_pkg_installed MediaServer && [[ ${ms_version} != "20.0.5-3152" ]]; then
        # Uninstall MediaServer (wrong version)
        echo ""
        package_uninstall MediaServer "Media Server"
    fi
fi

# Check the uninstalls worked before installing anything
if check_pkg_installed CodecPack; then
    ame_version=$(/usr/syno/bin/synopkg version CodecPack)
    if [[ ${ame_version:0:1} -gt "3" ]]; then
        ding
        echo -e "${Error}ERROR${Off} Uninstalling Advanced Media Extensions $ame_version didn't work!"
        echo "Stopping so nothing is installed over it."
        exit 1
    fi
fi
if [[ $no_vs != "yes" ]] && check_pkg_installed VideoStation; then
    vs_version=$(/usr/syno/bin/synopkg version VideoStation)
    if [[ ${vs_version} != "30.1.0-3153" ]]; then
        ding
        echo -e "${Error}ERROR${Off} Uninstalling Video Station $vs_version didn't work!"
        echo "Stopping so nothing is installed over it."
        exit 1
    fi
fi
if [[ $no_ms != "yes" ]] && check_pkg_installed MediaServer; then
    ms_version=$(/usr/syno/bin/synopkg version MediaServer)
    if [[ ${ms_version} != "20.0.5-3152" ]]; then
        ding
        echo -e "${Error}ERROR${Off} Uninstalling Media Server $ms_version didn't work!"
        echo "Stopping so nothing is installed over it."
        exit 1
    fi
fi

# CodecPack (Advanced Media Extensions)
if ! check_pkg_installed CodecPack; then
    need_pkg_file "CodecPack-${cputype}-3.1.0-3005.spk"
    package_install "CodecPack-${cputype}-3.1.0-3005.spk" "Advanced Media Extensions" CodecPack
    package_stop CodecPack "Advanced Media Extensions"
    # Prevent package updating and "update available" messages
    echo "Preventing Advanced Media Extensions from auto updating"
    /usr/syno/bin/synosetkeyvalue /var/packages/CodecPack/INFO version "30.1.0-3005"
    package_start CodecPack "Advanced Media Extensions"
    rm -f "$workdir/CodecPack-${cputype}-3.1.0-3005.spk"
else
    ame_version=$(/usr/syno/bin/synopkg version CodecPack)
    echo -e "\n${Cyan}Advanced Media Extensions${Off} $ame_version already installed"
fi

# VideoStation
if [[ $no_vs != "yes" ]]; then
    if ! check_pkg_installed VideoStation; then
        need_pkg_file "VideoStation-${cputype}-3.1.0-3153.spk"
        #package_install "VideoStation-${cputype}-3.1.1-3168.spk" "Video Station"
        package_install "VideoStation-${cputype}-3.1.0-3153.spk" "Video Station" VideoStation
        package_stop VideoStation "Video Station"
        # Prevent package updating and "update available" messages
        echo "Preventing Video Station from auto updating"
        #/usr/syno/bin/synosetkeyvalue /var/packages/VideoStation/INFO version "30.1.1-3168"
        /usr/syno/bin/synosetkeyvalue /var/packages/VideoStation/INFO version "30.1.0-3153"
        package_start VideoStation "Video Station"
        #rm -f "$workdir/VideoStation-${cputype}-3.1.0-3168.spk"
        rm -f "$workdir/VideoStation-${cputype}-3.1.0-3153.spk"
    else
        vs_version=$(/usr/syno/bin/synopkg version VideoStation)
        echo -e "\n${Cyan}Video Station${Off} $vs_version already installed"
    fi
fi

# MediaServer
if [[ $no_ms != "yes" ]]; then
    if ! check_pkg_installed MediaServer; then
        need_pkg_file "MediaServer-${cputype}-2.0.5-3152.spk"
        package_install "MediaServer-${cputype}-2.0.5-3152.spk" "Media Server" MediaServer
        package_stop MediaServer "Media Server"
        # Prevent package updating and "update available" messages
        echo "Preventing Media Server from auto updating"
        /usr/syno/bin/synosetkeyvalue /var/packages/MediaServer/INFO version "20.0.5-3152"
        package_start MediaServer "Media Server"
        rm -f "$workdir/MediaServer-${cputype}-2.0.5-3152.spk"
    else
        ms_version=$(/usr/syno/bin/synopkg version MediaServer)
        echo -e "\n${Cyan}Media Server${Off} $ms_version already installed"
    fi
fi

# Start packages if needed (i.e. after DSM update)
if check_pkg_installed CodecPack; then
    if ! package_is_running CodecPack; then
        # Check if package is already starting
        synopkg status CodecPack >/dev/null
        code=$?
        if [[ $code != "55" ]]; then
            package_start CodecPack "Advanced Media Extensions"
        fi
    fi
fi
if check_pkg_installed VideoStation; then
    if ! package_is_running VideoStation; then
        # Check if package is already starting
        synopkg status VideoStation >/dev/null
        code=$?
        if [[ $code != "55" ]]; then
            package_start VideoStation "Video Station"
        fi
    fi
fi
if check_pkg_installed MediaServer; then
    if ! package_is_running MediaServer; then
        # Check if package is already starting
        synopkg status MediaServer >/dev/null
        code=$?
        if [[ $code != "55" ]]; then
            package_start MediaServer "Media Server"
        fi
    fi
fi

echo -e "\nFinished :)"

echo -e "\nTo enable HEVC decoding:"
echo " 1. Open Package Center > Installed"
echo " 2. Click Advanced Media Extensions"
echo " 3. Click on Open"
echo -e " 4. Click on Install then OK \n"

