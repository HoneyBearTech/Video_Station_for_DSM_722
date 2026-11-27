"""Run the installer against stand-in DSM commands in a throwaway folder.

The stand-ins (curl, synopkg, synogetkeyvalue, synosetkeyvalue, whoami and
uname) are put first on PATH, and the script's DSM paths are rewritten to
point inside a temporary folder, so nothing outside it is touched and no
network is used. Each stand-in call is appended to a JSON-lines log, and the
simulated package state is kept in a JSON file.

The script needs bash 4 or later, and runs as if it were root, so run the
tests in a throwaway container with no network, from the repository root:

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
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "videostation_for_722.sh"
SOURCE = SCRIPT.read_text()

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
        state.pop(target, None)
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
                or (row[0] == "synopkg" and row[1] in ("uninstall", "install", "start", "stop"))]


def run_installer(choice="all", installed=None, arch="x86_64", curl=None, plant=None,
                  drop_hashes=(), source_edits=()):
    """Run the whole installer with --install=<choice> and return a Run."""
    require_container()
    with tempfile.TemporaryDirectory(prefix="vs722-test-") as directory:
        folder = Path(directory)
        binary = folder / "bin"
        binary.mkdir()
        command = binary / "mock-command"
        command.write_text(MOCK_COMMAND.replace("@PYTHON@", sys.executable))
        command.chmod(0o755)
        for name in ("whoami", "uname", "synogetkeyvalue", "synosetkeyvalue", "curl", "synopkg"):
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

        result = subprocess.run(
            ["bash", str(script), f"--install={choice}"],
            env={**os.environ, "PATH": str(binary) + ":" + os.environ["PATH"],
                 "MOCK_STATE": str(state_path), "MOCK_LOG": str(log_path), "MOCK_ARCH": arch,
                 "MOCK_CURL": json.dumps(curl or {})},
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        operations = [json.loads(line) for line in log_path.read_text().splitlines()]
        backup = (defaults / "synopackageslimit.conf.bak").exists()
        left = sorted(path.name for path in downloads.iterdir() if path.name not in planted)
        planted_after = {name: path.read_text() for name, path in planted.items() if path.exists()}
        return Run(result, json.loads(state_path.read_text()), operations, backup, left, planted_after)
