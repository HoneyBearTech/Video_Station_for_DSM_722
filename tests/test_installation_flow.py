"""Run the complete installer against an isolated simulated DSM filesystem."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]

# This executable only changes files beneath a per-test temporary directory.
MOCK_COMMAND = r'''#!/usr/bin/python3
import json
import os
from pathlib import Path
import re
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
state_path = Path(os.environ["MOCK_STATE"])
state = json.loads(state_path.read_text())
with open(os.environ["MOCK_LOG"], "a") as stream:
    stream.write(json.dumps([name, *args]) + "\n")

def save():
    state_path.write_text(json.dumps(state))

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
    if "-o" in args:
        if os.environ.get("MOCK_DOWNLOAD_FAIL") == "1":
            Path(args[args.index("-o") + 1]).write_text("partial package fixture")
            sys.exit(22)
        Path(args[args.index("-o") + 1]).write_text("complete package fixture")
    else:
        print('{"tag_name":"v1.4.22"}')
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
        filename = Path(target).name
        match = re.search(r"-(\d+\.\d+\.\d+-\d+)\.spk$", filename)
        if not match or not Path(target).is_file():
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


class InstallationFlowTests(unittest.TestCase):
    def run_installer(self, choice, installed=None, arch="x86_64", volume=None, volume_allowed=True, download_fail=False):
        with tempfile.TemporaryDirectory(prefix="installation-flow-") as directory:
            folder = Path(directory)
            binary = folder / "bin"
            binary.mkdir()
            command = binary / "mock-command"
            command.write_text(MOCK_COMMAND)
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
            source = (ROOT / "videostation_for_722.sh").read_text()
            replacements = {
                "/usr/syno/bin/": str(binary) + "/",
                "/proc/sys/kernel/syno_hw_version": str(folder / "model"),
                "/etc.defaults/": str(defaults) + "/",
                "/etc/": str(folder / "etc") + "/",
                "/var/packages/": str(folder / "var/packages") + "/",
                "/tmp/": str(folder / "downloads") + "/",
                "sleep 0.3": "sleep 0.01",
            }
            # Replace once against the source so fixture paths cannot be rewritten again.
            import re
            pattern = re.compile("|".join(re.escape(key) for key in replacements))
            source = pattern.sub(lambda match: replacements[match[0]], source)
            (folder / "downloads").mkdir()
            script = folder / "installer.sh"
            script.write_text(source)
            for name in ("scripts", "lib"):
                if (ROOT / name).is_dir():
                    shutil.copytree(ROOT / name, folder / name)
            args = ["bash", str(script), f"--install={choice}"]
            if volume:
                # Test the main installer's helper contract independently of the API helper.
                (folder / "lib").mkdir(exist_ok=True)
                (folder / "lib/package_volume.sh").write_text(
                    "volume_require_tools(){ return 0; }\n"
                    + "volume_check_target(){ return " + ("0" if volume_allowed else "1") + "; }\n"
                    + "volume_install_spk(){ "
                    + "printf '[\"targeted-install\",\"%s\",\"%s\"]\\n' \"$2\" \"$3\" >> \"$MOCK_LOG\"; "
                    + "synopkg install \"$1\"; }\n"
                )
                args.append(f"--volume={volume}")
            result = subprocess.run(
                args,
                env={**os.environ, "PATH": str(binary) + ":" + os.environ["PATH"],
                     "MOCK_STATE": str(state_path), "MOCK_LOG": str(log_path), "MOCK_ARCH": arch,
                     "MOCK_DOWNLOAD_FAIL": "1" if download_fail else "0"},
                capture_output=True, text=True, timeout=15,
            )
            operations = [json.loads(line) for line in log_path.read_text().splitlines()]
            backup = (defaults / "synopackageslimit.conf.bak")
            return result, json.loads(state_path.read_text()), operations, backup.exists()

    def test_fresh_install_choices_install_only_requested_packages(self):
        for choice, packages in (
            ("all", {"CodecPack", "VideoStation", "MediaServer"}),
            ("onlyamc", {"CodecPack"}),
            ("novs", {"CodecPack", "MediaServer"}),
            ("noms", {"CodecPack", "VideoStation"}),
        ):
            with self.subTest(choice=choice):
                result, state, operations, backup = self.run_installer(choice)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertEqual(set(state), packages)
                self.assertTrue(backup)
                for package in packages:
                    self.assertTrue(state[package]["running"])
                    self.assertRegex(state[package]["version"], r"^(30|20)\.")
                installs = [row for row in operations if row[:2] == ["synopkg", "install"]]
                self.assertEqual(len(installs), len(packages))
                self.assertTrue(all(len(row) == 3 for row in installs))

    def test_selected_volume_is_passed_to_targeted_installation(self):
        result, state, operations, _ = self.run_installer("onlyamc", volume="/volume2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        targeted = [row for row in operations if row[0] == "targeted-install"]
        self.assertEqual(targeted, [["targeted-install", "CodecPack", "/volume2"]])
        self.assertTrue(state["CodecPack"]["running"])

    def test_failed_volume_preflight_precedes_package_changes(self):
        result, state, operations, backup = self.run_installer(
            "all", volume="/volume2", volume_allowed=False
        )
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(state, {})
        self.assertFalse(backup)
        self.assertFalse(any(row[0] in ("synopkg", "synosetkeyvalue") for row in operations))

    def test_rerun_restarts_existing_packages_without_reinstalling(self):
        installed = {
            "CodecPack": {"version": "30.1.0-3005", "running": False},
            "VideoStation": {"version": "30.1.0-3153", "running": False},
            "MediaServer": {"version": "20.0.5-3152", "running": False},
        }
        result, state, operations, _ = self.run_installer("all", installed)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(all(package["running"] for package in state.values()))
        mutations = [row[1] for row in operations if row[0] == "synopkg"]
        self.assertNotIn("install", mutations)
        self.assertNotIn("uninstall", mutations)
        self.assertEqual(mutations.count("start"), 3)

    def test_download_failure_leaves_existing_packages_untouched(self):
        installed = {"CodecPack": {"version": "4.0.0-4025", "running": True}}
        result, state, operations, backup = self.run_installer(
            "onlyamc", installed, download_fail=True
        )
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertEqual(state, installed)
        self.assertFalse(backup)
        self.assertFalse(any(row[0] == "synosetkeyvalue" for row in operations))
        self.assertFalse(any(row[:2] == ["synopkg", "uninstall"] for row in operations))

    def test_newer_codec_package_is_replaced_before_installing(self):
        result, state, operations, _ = self.run_installer(
            "onlyamc", {"CodecPack": {"version": "4.0.0-4025", "running": True}}
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(state["CodecPack"]["version"], "30.1.0-3005")
        actions = [row[1] for row in operations if row[0] == "synopkg"]
        self.assertLess(actions.index("uninstall"), actions.index("install"))

    def test_unsupported_architecture_does_not_mutate_packages(self):
        result, state, operations, backup = self.run_installer("all", arch="unsupported")
        self.assertIn("Unsupported or unknown CPU", result.stdout)
        self.assertEqual(state, {})
        self.assertFalse(backup)
        self.assertFalse(any(row[0] in ("synopkg", "synosetkeyvalue") for row in operations))


if __name__ == "__main__":
    unittest.main()
