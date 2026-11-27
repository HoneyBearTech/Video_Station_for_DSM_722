"""Run the complete installer against stand-in DSM commands."""

import unittest

from harness import run_installer

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


if __name__ == "__main__":
    unittest.main()
