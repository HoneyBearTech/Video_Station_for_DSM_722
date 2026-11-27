"""Run the installer against stand-in DSM commands in a throwaway folder.

The stand-ins (curl, synopkg, synowebapi, synogetkeyvalue, synosetkeyvalue,
whoami and uname) are put first on PATH, and the DSM paths in the script and
in lib/ are rewritten to point inside a temporary folder, so nothing outside
it is touched and no network is used. Each stand-in call is appended to a
JSON-lines log, and the simulated package state is kept in a JSON file.

The script needs bash 4 or later, and runs as if it were root, so run the
tests in a throwaway container with no network, from the repository root.

Full coverage (the --volume tests need jq, so add it to the image first):

  printf 'FROM python:3.13-slim\nRUN apt-get update -qq && apt-get install -y -qq --no-install-recommends jq php-cli php-curl\n' \
      | docker build -q -t vs722-test -
  docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/w:ro" -w /w \
      vs722-test python3 -m unittest discover -s tests -v

The plain image also works; the tests that need jq are then skipped and say so:

  docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/w:ro" -w /w \
      python:3.13-slim python3 -m unittest discover -s tests -v

Outside a container the installer runs are skipped, unless VS722_TESTS_ON_HOST=1
is set.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "videostation_for_722.sh"
SOURCE = SCRIPT.read_text()
LIBRARY = ROOT / "lib" / "package_volume.sh"

HAS_JQ = shutil.which("jq") is not None
needs_jq = unittest.skipUnless(
    HAS_JQ, "jq is not installed; build the vs722-test image described in tests/harness.py")

CPUTYPES = ("armada37xx", "armada38x", "armv7", "monaco", "rtd1296", "rtd1619b", "x86_64")
PACKAGES = (("CodecPack", "3.1.0-3005"), ("VideoStation", "3.1.0-3153"), ("MediaServer", "2.0.5-3152"))
ALL_FILES = [f"{name}-{cpu}-{version}.spk" for name, version in PACKAGES for cpu in CPUTYPES]

# Lines of the script's pkg_sha256 table: the file name, then the value.
HASH_ENTRY = re.compile(r'^( +)(\S+\.spk)\)\n +echo "([0-9a-f]{64})" ;;\n', re.MULTILINE)

HOSTS = ("global.synologydownload.com", "global.download.synology.com", "cndl.synology.cn")


def in_container():
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def require_container():
    """Skip the calling test unless it runs in a container (or the user opts in)."""
    if not in_container() and os.environ.get("VS722_TESTS_ON_HOST") != "1":
        raise unittest.SkipTest(
            "installer runs only inside a container (no /.dockerenv or /run/.containerenv); "
            "set VS722_TESTS_ON_HOST=1 to run them here anyway")


def genuine(filename):
    """Contents of the stand-in 'genuine' download for a package file."""
    return f"genuine {filename}\n"


def tampered(filename):
    return f"tampered {filename}\n"


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def recorded_hashes(source=SOURCE):
    return {match[2]: match[3] for match in HASH_ENTRY.finditer(source)}


MOCK_COMMAND = r'''#!@PYTHON@ -I
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

name = Path(sys.argv[0]).name
args = sys.argv[1:]
state_path = Path(os.environ["MOCK_STATE"])
state = json.loads(state_path.read_text())

def log(row):
    with open(os.environ["MOCK_LOG"], "a") as stream:
        stream.write(json.dumps(row) + "\n")

def save():
    state_path.write_text(json.dumps(state))

if name != "curl":
    log([name, *args])

if name == "whoami":
    print("root")
elif name == "uname":
    print(os.environ.get("MOCK_ARCH", "x86_64"))
elif name == "synogetkeyvalue":
    values = {
        "productversion": "7.2.2", "buildphase": "GM", "buildnumber": "72806",
        "smallfixnumber": "0", "platform_name": os.environ.get("MOCK_ARCH", "x86_64"),
        "language": "enu",
    }
    print(values[args[1]])
elif name == "synosetkeyvalue":
    path, key, value = args
    if path.endswith("/INFO") and key == "version":
        state[Path(path).parent.name]["version"] = value
        save()
elif name == "curl":
    output = Path(args[args.index("-o") + 1]) if "-o" in args else None
    urls = [arg for arg in args if "://" in arg]
    url = urls[-1] if urls else ""
    # Record whether a file was already waiting at the output path.
    log(["curl", *args, {"preexisting": bool(output and output.exists())}])
    host = urlparse(url).hostname or ""
    filename = Path(urlparse(url).path).name
    modes = json.loads(os.environ.get("MOCK_CURL", "{}"))
    mode = modes.get(host, modes.get("*", "ok"))
    if output is None or not host.endswith((".synology.com", ".synologydownload.com", ".synology.cn")):
        sys.exit(7)
    if mode == "fail":
        output.write_text("partial package fixture")
        sys.exit(22)
    if mode == "cert":
        sys.exit(60)
    if mode == "wrong":
        output.write_text("tampered " + filename + "\n")
    else:
        output.write_text("genuine " + filename + "\n")
elif name == "synowebapi":
    # MOCK_WEBAPI: {"volumes": [...] listed by Package Center,
    #   "refuse_check": [<pkg>, ...] the pre-check says no,
    #   "check_installed": true to answer the pre-check for installed packages,
    #   "fail_install": [<pkg>, ...] the install call fails}
    web = json.loads(os.environ.get("MOCK_WEBAPI", "{}"))
    fields = dict(arg.split("=", 1) for arg in args if "=" in arg)
    api, method = fields.get("api"), fields.get("method")
    volumes = [{"mount_point": volume} for volume in web.get("volumes", ["/volume1", "/volume2"])]
    print("[Line 206] Exec WebAPI: api=" + str(api))
    def reply(data=None):
        if data is None:
            print(json.dumps({"success": False, "error": {"code": 4501}}))
        else:
            print(json.dumps({"success": True, "data": data}))
    if args[0] != "--exec":
        raise SystemExit("Unexpected web API call")
    if api == "SYNO.Core.Package.Setting" and method == "get":
        reply({"volume_list": volumes})
    elif api == "SYNO.Core.Package.Installation" and method == "check":
        package = json.loads(fields["id"])
        if package in web.get("refuse_check", []) or (package in state and not web.get("check_installed")):
            reply()
        else:
            reply({"is_occupied": False, "volume_list": volumes})
    elif api == "SYNO.Core.Package.Installation" and method == "install":
        path = Path(json.loads(fields["path"]))
        volume = json.loads(fields["volume_path"])
        filename = path.name
        package = filename.split("-", 1)[0]
        match = re.search(r"-(\d+\.\d+\.\d+-\d+)\.spk$", filename)
        # Only accept a genuine file from this run's private folder.
        if (package in web.get("fail_install", []) or not match or not path.is_file()
                or not path.parent.name.startswith("vs722.")
                or path.read_text() != "genuine " + filename + "\n"
                or volume not in [entry["mount_point"] for entry in volumes]):
            reply()
        else:
            state[package] = {"version": match[1], "running": True}
            save()
            target = Path(os.environ["MOCK_PACKAGES"]) / package / "target"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                target.unlink()
            target.symlink_to(volume + "/@appstore/" + package)
            reply({"packageName": package})
    else:
        raise SystemExit("Unexpected web API call")
elif name == "synopkg":
    action, target = args[:2]
    package = state.get(target)
    if action == "version":
        print(package["version"] if package else "")
    elif action == "status":
        sys.exit(0 if package and package["running"] else 17 if package else 255)
    elif action == "is_onoff":
        sys.exit(0 if package and package["running"] else 1)
    elif action == "uninstall":
        # MOCK_UNINSTALL: {"<pkg>": {"stuck": true}} reports success but leaves
        # the package; {"<pkg>": {"also": ["<other>", ...]}} removes others too.
        how = json.loads(os.environ.get("MOCK_UNINSTALL", "{}")).get(target, {})
        if not how.get("stuck"):
            state.pop(target, None)
        for other in how.get("also", []):
            state.pop(other, None)
        save()
    elif action == "install":
        path = Path(target)
        filename = path.name
        match = re.search(r"-(\d+\.\d+\.\d+-\d+)\.spk$", filename)
        # Only accept a genuine file from this run's private folder.
        if (not match or not path.is_file() or not path.parent.name.startswith("vs722.")
                or path.read_text() != "genuine " + filename + "\n"):
            sys.exit(2)
        state[filename.split("-", 1)[0]] = {"version": match[1], "running": True}
        save()
    elif action in ("start", "stop") and package:
        package["running"] = action == "start"
        save()
    else:
        raise SystemExit("Unexpected package operation")
else:
    raise SystemExit("Unexpected simulated command")
'''


class Run:
    """Result of one installer run."""

    def __init__(self, result, state, operations, backup, downloads_left, planted):
        self.result = result
        self.returncode = result.returncode
        self.output = result.stdout + result.stderr
        self.state = state
        self.operations = operations
        self.backup = backup
        self.downloads_left = downloads_left
        self.planted = planted

    def curl_calls(self):
        return [row for row in self.operations if row[0] == "curl"]

    def downloaded_files(self):
        return [Path(row[row.index("-o") + 1]).name for row in self.curl_calls()]

    def mutations(self):
        """Indexes of calls that change the NAS."""
        return [index for index, row in enumerate(self.operations)
                if row[0] == "synosetkeyvalue"
                or (row[0] == "synopkg" and row[1] in ("uninstall", "install", "start", "stop"))
                or (row[0] == "synowebapi" and "method=install" in row)]

    def webapi_calls(self, method=None):
        """Web API calls as dicts of their key=value arguments."""
        calls = [dict(arg.split("=", 1) for arg in row[1:] if "=" in arg)
                 for row in self.operations if row[0] == "synowebapi"]
        return [call for call in calls if method is None or call.get("method") == method]


DEFAULT_MOUNTS = ("/volume1", "/volume2")


def run_installer(choice="all", installed=None, arch="x86_64", curl=None, plant=None,
                  drop_hashes=(), source_edits=(), uninstall=None, extra_args=(), args=None,
                  lib=True, lib_edits=(), mounts=None, webapi=None):
    """Run the whole installer with --install=<choice> and return a Run.

    extra_args are added after --install; args replaces all the arguments.
    lib=False leaves out the lib folder. mounts lists the volumes in the
    stand-in /proc/mounts, as "/volumeN" (read-write) or ("/volumeN", "ro").
    webapi sets how the stand-in synowebapi answers (see MOCK_WEBAPI).
    """
    require_container()
    with tempfile.TemporaryDirectory(prefix="vs722-test-") as directory:
        folder = Path(directory)
        binary = folder / "bin"
        binary.mkdir()
        command = binary / "mock-command"
        command.write_text(MOCK_COMMAND.replace("@PYTHON@", sys.executable))
        command.chmod(0o755)
        for name in ("whoami", "uname", "synogetkeyvalue", "synosetkeyvalue", "curl", "synopkg",
                     "synowebapi"):
            (binary / name).symlink_to(command.name)
        state_path = folder / "state.json"
        state_path.write_text(json.dumps(installed or {}))
        log_path = folder / "operations.jsonl"
        log_path.touch()
        (folder / "model").write_text("test-model\n")
        defaults = folder / "etc.defaults"
        defaults.mkdir()
        (defaults / "synopackageslimit.conf").write_text("original limits\n")
        (folder / "etc").mkdir()
        downloads = folder / "tmp"
        downloads.mkdir()
        packages = folder / "var/packages"
        packages.mkdir(parents=True)
        mount_lines = []
        for entry in (DEFAULT_MOUNTS if mounts is None else mounts):
            volume, mode = (entry, "rw") if isinstance(entry, str) else entry
            mount_lines.append(f"/dev/mapper/cachedev_0 {volume} btrfs {mode},relatime 0 0")
        (folder / "mounts").write_text("\n".join(mount_lines) + "\n")
        planted = {}
        for filename in plant or ():
            (downloads / filename).write_text("planted " + filename + "\n")
            planted[filename] = downloads / filename

        source = SOURCE
        # Point the recorded checksums at the stand-in genuine files.
        def rewrite(match):
            filename = match[2]
            if filename in drop_hashes:
                return ""
            return f'{match[1]}{filename})\n{match[1]}    echo "{sha256(genuine(filename))}" ;;\n'
        source = HASH_ENTRY.sub(rewrite, source)
        for old, new in source_edits:
            source = source.replace(old, new)
        replacements = {
            "/usr/syno/bin/": str(binary) + "/",
            "/proc/sys/kernel/syno_hw_version": str(folder / "model"),
            "/etc.defaults/": str(defaults) + "/",
            "/etc/": str(folder / "etc") + "/",
            "/var/packages/": str(folder / "var/packages") + "/",
            "/tmp/": str(downloads) + "/",
            "sleep 0.3": "sleep 0.01",
        }
        # Replace once against the source so fixture paths cannot be rewritten again.
        pattern = re.compile("|".join(re.escape(key) for key in replacements))
        source = pattern.sub(lambda match: replacements[match[0]], source)
        script = folder / "installer.sh"
        script.write_text(source)

        if lib:
            # The installer sources lib/ from its own folder; rewrite its DSM paths too.
            library = LIBRARY.read_text()
            for old, new in lib_edits:
                library = library.replace(old, new)
            lib_replacements = {
                "/usr/syno/bin/": str(binary) + "/",
                "/var/packages/": str(packages) + "/",
                "/proc/mounts": str(folder / "mounts"),
                # The stand-in target links point at /volumeN, which is not here.
                "readlink -f": "readlink",
                "sleep 1": "sleep 0.01",
            }
            pattern = re.compile("|".join(re.escape(key) for key in lib_replacements))
            library = pattern.sub(lambda match: lib_replacements[match[0]], library)
            (folder / "lib").mkdir()
            (folder / "lib/package_volume.sh").write_text(library)

        arguments = list(args) if args is not None else [f"--install={choice}", *extra_args]
        result = subprocess.run(
            ["bash", str(script), *arguments],
            env={**os.environ, "PATH": str(binary) + ":" + os.environ["PATH"],
                 "MOCK_STATE": str(state_path), "MOCK_LOG": str(log_path), "MOCK_ARCH": arch,
                 "MOCK_CURL": json.dumps(curl or {}), "MOCK_UNINSTALL": json.dumps(uninstall or {}),
                 "MOCK_WEBAPI": json.dumps(webapi or {}), "MOCK_PACKAGES": str(packages)},
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        operations = [json.loads(line) for line in log_path.read_text().splitlines()]
        backup = (defaults / "synopackageslimit.conf.bak").exists()
        left = sorted(path.name for path in downloads.iterdir() if path.name not in planted)
        planted_after = {name: path.read_text() for name, path in planted.items() if path.exists()}
        return Run(result, json.loads(state_path.read_text()), operations, backup, left, planted_after)
