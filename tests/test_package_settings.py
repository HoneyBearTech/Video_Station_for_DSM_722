"""Check the read-only preference inspector against isolated filesystem fixtures."""

from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspect-package-settings.sh"


class PackageSettingsTests(unittest.TestCase):
    def run_inspector(self, root, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), "--root", str(root), *args],
            capture_output=True, text=True, timeout=5,
        )

    def test_known_settings_are_read_from_both_files(self):
        with tempfile.TemporaryDirectory(prefix="package settings ") as directory:
            root = Path(directory)
            for folder, value in (("etc", "/volume2"), ("etc.defaults", "")):
                (root / folder).mkdir()
                (root / folder / "synoinfo.conf").write_text(
                    f'pkg_def_intall_vol="{value}"\n'
                    'package_update_channel="stable"\n'
                    'enable_pkg_autoupdate_all="yes"\n'
                    'upgrade_pkg_dsm_notification="no"\n'
                )
            result = self.run_inspector(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pkg_def_intall_vol=/volume2", result.stdout)
            self.assertIn("pkg_def_intall_vol=[no default volume]", result.stdout)
            self.assertEqual(result.stdout.count("package_update_channel=stable"), 2)
            self.assertEqual(result.stdout.count("enable_pkg_autoupdate_all=yes"), 2)
            self.assertEqual(result.stdout.count("upgrade_pkg_dsm_notification=no"), 2)

    def test_unknown_values_and_unrelated_settings_are_suppressed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "etc").mkdir()
            marker = root / "unexpected-write"
            config = root / "etc" / "synoinfo.conf"
            contents = (
                'unrelated_private_value="fixture-private-value"\n'
                f'pkg_def_intall_vol="$(touch {marker})"\n'
                'package_update_channel="unexpected-channel"\n'
                'pkg_autoupdate_all="arbitrary-value"\n'
            )
            config.write_text(contents)
            result = self.run_inspector(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("fixture-private-value", result.stdout)
            self.assertNotIn("unexpected-channel", result.stdout)
            self.assertNotIn("arbitrary-value", result.stdout)
            self.assertNotIn("touch", result.stdout)
            self.assertEqual(result.stdout.count("[unrecognized]"), 3)
            self.assertFalse(marker.exists())
            self.assertEqual(config.read_text(), contents)

    def test_missing_files_and_keys_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "etc").mkdir()
            (root / "etc" / "synoinfo.conf").write_text("# no preferences\n")
            result = self.run_inspector(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("[not set]"), 7)
            self.assertEqual(result.stdout.count("[unavailable]"), 7)

    def test_values_with_whitespace_and_unquoted_booleans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "etc").mkdir()
            (root / "etc" / "synoinfo.conf").write_text(
                '  pkg_def_intall_vol = "/volume12"  \n'
                'pkg_autoupdate_all = no  \n'
                'package_update_channel="stable" trailing-text\n'
            )
            result = self.run_inspector(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pkg_def_intall_vol=/volume12", result.stdout)
            self.assertIn("pkg_autoupdate_all=no", result.stdout)
            self.assertIn("package_update_channel=[unrecognized]", result.stdout)

    def test_invalid_options_do_not_inspect_live_configuration(self):
        for args in (("--root",), ("--root", "/does-not-exist"), ("--unknown",)):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["bash", str(SCRIPT), *args],
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("pkg_def_intall_vol=", result.stdout)


if __name__ == "__main__":
    unittest.main()
