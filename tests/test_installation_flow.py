"""Run the complete installer against stand-in DSM commands."""

import json
import re
import unittest

from harness import needs_jq, run_installer

OLD_VERSIONS = {
    "CodecPack": {"version": "4.0.0-4025", "running": True},
    "VideoStation": {"version": "30.1.1-3168", "running": True},
    "MediaServer": {"version": "20.1.0-3304", "running": True},
}

CHOICES = {
    "all": {"CodecPack", "VideoStation", "MediaServer"},
    "novs": {"CodecPack", "MediaServer"},
    "noms": {"CodecPack", "VideoStation"},
    "onlyamc": {"CodecPack"},
}

TARGET = {"CodecPack": "30.1.0-3005", "VideoStation": "30.1.0-3153", "MediaServer": "20.0.5-3152"}

AME_V4_OTHERS_CURRENT = {
    "CodecPack": {"version": "4.0.0-4025", "running": True},
    "VideoStation": {"version": "30.1.0-3153", "running": True},
    "MediaServer": {"version": "20.0.5-3152", "running": True},
}


class UninstallSideEffectTests(unittest.TestCase):
    def installs(self, run):
        return [row[2].rsplit("/", 1)[1].split("-", 1)[0] for row in run.operations
                if row[:2] == ["synopkg", "install"]]

    def test_ame_v4_removal_that_also_removes_current_packages_reinstalls_them(self):
        cascade = {"CodecPack": {"also": ["VideoStation", "MediaServer"]}}
        for choice, packages in CHOICES.items():
            with self.subTest(choice=choice):
                run = run_installer(choice, AME_V4_OTHERS_CURRENT, uninstall=cascade)
                self.assertEqual(run.returncode, 0, run.output)
                # Every selected package was fetched and checked before any change.
                self.assertEqual({name.split("-", 1)[0] for name in run.downloaded_files()}, packages)
                curls = [index for index, row in enumerate(run.operations) if row[0] == "curl"]
                self.assertLess(max(curls), min(run.mutations()))
                self.assertEqual(sorted(self.installs(run)), sorted(packages))
                self.assertEqual({name: value["version"] for name, value in run.state.items()},
                                 {name: TARGET[name] for name in packages})
                self.assertNotIn("already installed", run.output)

    def test_ame_v4_removal_leaves_current_packages_alone(self):
        run = run_installer("all", AME_V4_OTHERS_CURRENT)
        self.assertEqual(run.returncode, 0, run.output)
        self.assertEqual(sorted(run.downloaded_files()), sorted([
            "CodecPack-x86_64-3.1.0-3005.spk", "VideoStation-x86_64-3.1.0-3153.spk",
            "MediaServer-x86_64-2.0.5-3152.spk"]))
        self.assertEqual(self.installs(run), ["CodecPack"])
        self.assertEqual([row[2] for row in run.operations if row[:2] == ["synopkg", "uninstall"]],
                         ["CodecPack"])
        self.assertIn("Video Station 30.1.0-3153 already installed", run.output)
        self.assertIn("Media Server 20.0.5-3152 already installed", run.output)
        self.assertEqual({name: value["version"] for name, value in run.state.items()}, TARGET)

    def test_uninstall_that_leaves_the_package_stops_before_installing(self):
        cases = (
            ("VideoStation", "Video Station 30.1.1-3168", "all"),
            ("MediaServer", "Media Server 20.1.0-3304", "all"),
            ("CodecPack", "Advanced Media Extensions 4.0.0-4025", "onlyamc"),
        )
        for package, label, choice in cases:
            with self.subTest(package=package):
                run = run_installer(choice, OLD_VERSIONS, uninstall={package: {"stuck": True}})
                self.assertEqual(run.returncode, 1, run.output)
                self.assertIn(f"Uninstalling {label} didn't work", run.output)
                self.assertEqual(self.installs(run), [])
                self.assertEqual(run.state[package], OLD_VERSIONS[package])
                self.assertEqual(run.downloads_left, [])

    def test_package_file_not_downloaded_stops_before_installing(self):
        # Removing the wrong Video Station also takes an older Advanced Media
        # Extensions with it, which was not planned for, so its file is missing.
        installed = {
            "CodecPack": {"version": "30.0.0-3001", "running": True},
            "VideoStation": {"version": "30.1.1-3168", "running": True},
        }
        run = run_installer("noms", installed, uninstall={"VideoStation": {"also": ["CodecPack"]}})
        self.assertEqual(run.returncode, 1, run.output)
        self.assertIn("CodecPack-x86_64-3.1.0-3005.spk was not downloaded", run.output)
        self.assertEqual(self.installs(run), [])


class InstallationFlowTests(unittest.TestCase):
    def test_fresh_install_choices_install_only_requested_packages(self):
        for choice, packages in CHOICES.items():
            with self.subTest(choice=choice):
                run = run_installer(choice)
                self.assertEqual(run.returncode, 0, run.output)
                self.assertEqual(set(run.state), packages)
                self.assertTrue(run.backup)
                self.assertEqual({name.split("-", 1)[0] for name in run.downloaded_files()}, packages)
                for package in packages:
                    self.assertTrue(run.state[package]["running"])
                    self.assertRegex(run.state[package]["version"], r"^(30|20)\.")
                installs = [row for row in run.operations if row[:2] == ["synopkg", "install"]]
                self.assertEqual(len(installs), len(packages))

    def test_every_download_comes_before_the_first_change(self):
        for installed in ({}, OLD_VERSIONS):
            for choice, packages in CHOICES.items():
                with self.subTest(choice=choice, installed=bool(installed)):
                    run = run_installer(choice, installed)
                    self.assertEqual(run.returncode, 0, run.output)
                    curls = [index for index, row in enumerate(run.operations) if row[0] == "curl"]
                    changes = run.mutations()
                    self.assertEqual(len(curls), len(packages))
                    self.assertTrue(changes)
                    self.assertLess(max(curls), min(changes))
                    first = run.operations[min(changes)]
                    self.assertEqual(first[0], "synosetkeyvalue")

    def test_wrong_versions_are_replaced_and_unselected_packages_left_alone(self):
        for choice, packages in CHOICES.items():
            with self.subTest(choice=choice):
                run = run_installer(choice, OLD_VERSIONS)
                self.assertEqual(run.returncode, 0, run.output)
                expected = {"CodecPack": "30.1.0-3005", "VideoStation": "30.1.0-3153",
                            "MediaServer": "20.0.5-3152"}
                for package, old in OLD_VERSIONS.items():
                    want = expected[package] if package in packages else old["version"]
                    self.assertEqual(run.state[package]["version"], want)
                uninstalled = {row[2] for row in run.operations if row[:2] == ["synopkg", "uninstall"]}
                self.assertEqual(uninstalled, packages)
                actions = [row[1] for row in run.operations if row[0] == "synopkg"]
                self.assertLess(actions.index("uninstall"), actions.index("install"))

    def test_rerun_restarts_existing_packages_without_downloading(self):
        installed = {
            "CodecPack": {"version": "30.1.0-3005", "running": False},
            "VideoStation": {"version": "30.1.0-3153", "running": False},
            "MediaServer": {"version": "20.0.5-3152", "running": False},
        }
        run = run_installer("all", installed)
        self.assertEqual(run.returncode, 0, run.output)
        self.assertEqual(run.curl_calls(), [])
        self.assertTrue(all(package["running"] for package in run.state.values()))
        actions = [row[1] for row in run.operations if row[0] == "synopkg"]
        self.assertNotIn("install", actions)
        self.assertNotIn("uninstall", actions)
        self.assertEqual(actions.count("start"), 3)

    def test_never_contacts_github_and_never_restarts_itself(self):
        run = run_installer("all")
        self.assertEqual(run.returncode, 0, run.output)
        for row in run.curl_calls():
            self.assertFalse(any("github" in arg for arg in row if isinstance(arg, str)), row)
        # A restarted script would check again that it runs as root.
        self.assertEqual([row for row in run.operations if row[0] == "whoami"], [["whoami"]])
        self.assertNotIn("newer version", run.output)

    def test_unsupported_architecture_does_not_change_anything(self):
        run = run_installer("all", arch="unsupported")
        self.assertIn("Unsupported or unknown CPU", run.output)
        self.assertEqual(run.state, {})
        self.assertFalse(run.backup)
        self.assertFalse(any(row[0] in ("synopkg", "synosetkeyvalue", "curl") for row in run.operations))


PRIVATE_SPK = re.compile(r"/tmp/vs722\.[^/]+/(CodecPack|VideoStation|MediaServer)-x86_64-[0-9.-]+\.spk$")


def installed_package(call):
    """Package ID of a web API install call, from its file name."""
    return json.loads(call["path"]).rsplit("/", 1)[1].split("-", 1)[0]


class VolumeInstallTests(unittest.TestCase):
    """--volume=/volumeN, with the real lib/package_volume.sh and a stand-in synowebapi."""

    def assert_nothing_changed(self, run, installed=None):
        self.assertEqual(run.returncode, 2, run.output)
        self.assertIn("Nothing was changed on the NAS.", run.output)
        self.assertEqual(run.curl_calls(), [])
        self.assertEqual(run.mutations(), [])
        self.assertFalse(run.backup)
        self.assertEqual(run.state, installed or {})
        self.assertEqual(run.downloads_left, [])

    @needs_jq
    def test_selected_volume_gets_the_checked_file_from_the_private_folder(self):
        run = run_installer("onlyamc", extra_args=("--volume=/volume2",))
        self.assertEqual(run.returncode, 0, run.output)
        installs = run.webapi_calls("install")
        self.assertEqual(len(installs), 1)
        self.assertEqual(json.loads(installs[0]["volume_path"]), "/volume2")
        self.assertRegex(json.loads(installs[0]["path"]), PRIVATE_SPK)
        self.assertEqual(installs[0]["check_codesign"], "true")
        self.assertEqual(installs[0]["force"], "false")
        # DSM's own installer is not used, and Package Center's default is never set.
        self.assertFalse(any(row[:2] == ["synopkg", "install"] for row in run.operations))
        self.assertEqual([call["method"] for call in run.webapi_calls()],
                         ["get", "check", "get", "check", "install"])
        self.assertEqual(run.state["CodecPack"], {"version": "30.1.0-3005", "running": True})
        self.assertIn("Installing Advanced Media Extensions on /volume2", run.output)

    @needs_jq
    def test_every_package_is_checked_before_downloading(self):
        run = run_installer("all", extra_args=("--volume=/volume2",))
        self.assertEqual(run.returncode, 0, run.output)
        checks = [index for index, row in enumerate(run.operations)
                  if row[0] == "synowebapi" and "method=check" in row]
        curls = [index for index, row in enumerate(run.operations) if row[0] == "curl"]
        self.assertEqual(len(curls), 3)
        self.assertEqual(len(checks), 6)
        self.assertLess(checks[2], min(curls))
        self.assertLess(max(curls), min(run.mutations()))
        self.assertEqual(sorted(installed_package(call) for call in run.webapi_calls("install")),
                         ["CodecPack", "MediaServer", "VideoStation"])
        self.assertEqual([json.loads(call["id"]) for call in run.webapi_calls("check")],
                         ["CodecPack", "VideoStation", "MediaServer"] * 2)
        for call in run.webapi_calls("install"):
            self.assertRegex(json.loads(call["path"]), PRIVATE_SPK)
        self.assertEqual(set(run.state), {"CodecPack", "VideoStation", "MediaServer"})

    @needs_jq
    def test_bad_volume_stops_before_any_download_or_change(self):
        cases = {
            "not mounted": {"mounts": ["/volume1"]},
            "read-only": {"mounts": [("/volume2", "ro")]},
            "not listed by Package Center": {"webapi": {"volumes": ["/volume1"]}},
            "DSM refuses the package": {"webapi": {"refuse_check": ["VideoStation"]}},
        }
        for name, options in cases.items():
            with self.subTest(case=name):
                run = run_installer("all", OLD_VERSIONS if name == "read-only" else None,
                                    extra_args=("--volume=/volume2",), **options)
                self.assert_nothing_changed(run, OLD_VERSIONS if name == "read-only" else None)

    def test_missing_tools_or_lib_stop_before_any_download_or_change(self):
        cases = {
            "no jq": ({"lib_edits": (("command -v jq", "command -v jq-not-installed"),)}, "requires jq"),
            "no lib folder": ({"lib": False}, "lib/package_volume.sh"),
        }
        for name, (options, message) in cases.items():
            with self.subTest(case=name):
                run = run_installer("all", OLD_VERSIONS, extra_args=("--volume=/volume2",), **options)
                self.assert_nothing_changed(run, OLD_VERSIONS)
                self.assertIn(message, run.output)

    @needs_jq
    def test_installed_package_dsm_cannot_check_is_noted_not_failed(self):
        run = run_installer("onlyamc", {"CodecPack": {"version": "4.0.0-4025", "running": True}},
                            extra_args=("--volume=/volume2",))
        self.assertEqual(run.returncode, 0, run.output)
        self.assertIn("DSM could not check Advanced Media Extensions for /volume2 while it is installed",
                      run.output)
        self.assertEqual(run.state["CodecPack"]["version"], "30.1.0-3005")

    @needs_jq
    def test_late_install_failure_says_what_was_removed_and_how_to_rerun(self):
        run = run_installer("all", OLD_VERSIONS, extra_args=("--volume=/volume2",),
                            webapi={"fail_install": ["VideoStation"]})
        self.assertNotEqual(run.returncode, 0, run.output)
        self.assertEqual(run.returncode, 1, run.output)
        self.assertIn("Video Station could not be installed on /volume2", run.output)
        self.assertIn("This run removed these packages and they are not installed now:", run.output)
        self.assertIn("  - Video Station 30.1.1-3168", run.output)
        self.assertIn("  - Media Server 20.1.0-3304", run.output)
        self.assertNotIn("  - Advanced Media Extensions", run.output)
        self.assertIn("run the script again without --volume", run.output)
        rerun = run.output.split("without --volume:\n", 1)[1].splitlines()[0]
        self.assertRegex(rerun, r"^  sudo bash /\S+/installer\.sh --install=all$")
        self.assertNotIn("VideoStation", run.state)
        self.assertEqual(run.downloads_left, [])

    @needs_jq
    def test_late_install_failure_with_nothing_removed_says_so(self):
        run = run_installer("onlyamc", extra_args=("--volume=/volume2",),
                            webapi={"fail_install": ["CodecPack"]})
        self.assertEqual(run.returncode, 1, run.output)
        self.assertIn("This run did not remove any package.", run.output)
        self.assertIn("Advanced Media Extensions is not installed.", run.output)

    @needs_jq
    def test_packages_already_right_stay_where_they_are(self):
        installed = {"CodecPack": {"version": "30.1.0-3005", "running": True},
                     "VideoStation": {"version": "30.1.0-3153", "running": True}}
        run = run_installer("all", installed, extra_args=("--volume=/volume2",))
        self.assertEqual(run.returncode, 0, run.output)
        self.assertEqual([installed_package(call) for call in run.webapi_calls("install")], ["MediaServer"])
        self.assertFalse(any(row[:2] == ["synopkg", "uninstall"] for row in run.operations))

    def test_normal_run_without_volume_is_unchanged(self):
        for lib in (True, False):
            with self.subTest(lib=lib):
                run = run_installer("all", OLD_VERSIONS, lib=lib)
                self.assertEqual(run.returncode, 0, run.output)
                self.assertEqual([row for row in run.operations if row[0] == "synowebapi"], [])
                installs = [row for row in run.operations if row[:2] == ["synopkg", "install"]]
                self.assertEqual(len(installs), 3)
                for row in installs:
                    self.assertEqual(len(row), 3, "synopkg install gets only the package file")
                    self.assertRegex(row[2], PRIVATE_SPK)
                self.assertNotIn(" on /volume", run.output)
                self.assertNotIn("volume", run.output.lower())


if __name__ == "__main__":
    unittest.main()
