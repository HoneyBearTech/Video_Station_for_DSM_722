"""Exercise command parsing and download failures without invoking DSM services."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "videostation_for_722.sh"
SOURCE = SCRIPT.read_text()


class CommandLineTests(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=5
        )

    def test_help_and_version_do_not_need_dsm(self):
        for flag, expected in (("--help", "Usage:"), ("--version", "Video_Station_for_DSM_722")):
            with self.subTest(flag=flag):
                result = self.run_script(flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)
                self.assertEqual(result.stderr, "")

    def test_invalid_arguments_stop_before_dsm_access(self):
        for args in (("--unknown",), ("--install",), ("--install=bad",), ("--volume",), ("--volume=",),
                     ("--volume=/volume0",), ("--volume=/tmp",), ("extra",)):
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Usage:", result.stdout)
                self.assertNotIn("/usr/syno", result.stderr)

    def test_volume_option_is_retained_for_restart(self):
        parser = SOURCE.split("# Check script is running as root", 1)[0]
        result = subprocess.run(
            ["bash", "-c", parser + '\nprintf "%s" "$install_volume"',
             str(SCRIPT), "--volume=/volume2"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "/volume2")

    def test_trace_options_are_recognized(self):
        for flag in ("-t", "--trace"):
            with self.subTest(flag=flag):
                result = self.run_script(flag, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")

    def test_install_choices_are_recognized(self):
        for choice in ("all", "novs", "noms", "onlyamc"):
            with self.subTest(choice=choice):
                result = self.run_script(f"--install={choice}", "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")

    def test_install_choices_set_the_expected_package_flags(self):
        parser = SOURCE.split("# Check script is running as root", 1)[0]
        cases = {
            "all": "yes||",
            "novs": "yes|yes|",
            "noms": "yes||yes",
            "onlyamc": "yes|yes|yes",
        }
        for choice, expected in cases.items():
            with self.subTest(choice=choice):
                result = subprocess.run(
                    ["bash", "-c", parser +
                     '\nprintf "%s|%s|%s" "$auto" "$no_vs" "$no_ms"',
                     str(SCRIPT), f"--install={choice}"],
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_original_arguments_remain_available_for_restart(self):
        parser = SOURCE.split("# Check script is running as root", 1)[0]
        result = subprocess.run(
            ["bash", "-c", parser + '\nprintf "%s\\n" "${args[@]}"',
             str(SCRIPT), "--install=onlyamc", "--trace"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["--install=onlyamc", "--trace"])


class DownloadTests(unittest.TestCase):
    def run_download(self, mode, cached=None):
        with tempfile.TemporaryDirectory(prefix="installer-test-") as directory:
            folder = Path(directory)
            package = folder / "example.spk"
            if cached is not None:
                package.write_text(cached)
            # Only the download function is loaded; all DSM operations are excluded.
            function = SOURCE.split("download_pkg(){", 1)[1].split("\n}\n", 1)[0]
            function = "download_pkg(){" + function.replace("/tmp/", directory + "/") + "\n}"
            mocks = r'''
synogetkeyvalue(){ echo enu; }
readlink(){ return 1; }
ding(){ :; }
curl(){
    count=$((count + 1))
    local output="${@: -1}"
    if [[ -e "$PACKAGE" ]]; then
        [[ ! -s "$PACKAGE" ]] || exit 90
    fi
    case "$MODE" in
        fail) printf partial > "$output"; return 22 ;;
        empty) : > "$output"; return 0 ;;
        fallback)
            if [[ $count == 1 ]]; then
                printf partial > "$output"
                return 22
            fi
            ;;
    esac
    printf complete > "$output"
}
count=0
'''
            result = subprocess.run(
                ["bash", "-c", mocks + function + '\ndownload_pkg Example 1 example.spk\necho "attempts=$count"'],
                env={**os.environ, "MODE": mode, "PACKAGE": str(package)},
                capture_output=True, text=True, timeout=5,
            )
            contents = package.read_text() if package.exists() else None
            partials = list(folder.glob("example.spk.*"))
            return result, contents, partials

    def test_success_publishes_complete_download(self):
        result, contents, partials = self.run_download("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("attempts=1", result.stdout)
        self.assertEqual(contents, "complete")
        self.assertEqual(partials, [])

    def test_failed_mirror_does_not_publish_partial_file(self):
        result, contents, partials = self.run_download("fallback")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("attempts=2", result.stdout)
        self.assertEqual(contents, "complete")
        self.assertEqual(partials, [])

    def test_all_failed_or_empty_mirrors_are_errors(self):
        for mode in ("fail", "empty"):
            with self.subTest(mode=mode):
                result, contents, partials = self.run_download(mode)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(result.stdout.count("Downloading"), 3)
                self.assertIn("Failed to download", result.stderr)
                self.assertIsNone(contents)
                self.assertEqual(partials, [])

    def test_nonempty_cached_package_is_reused(self):
        result, contents, partials = self.run_download("fail", cached="existing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("attempts=0", result.stdout)
        self.assertEqual(contents, "existing")
        self.assertEqual(partials, [])

    def test_empty_cached_package_is_replaced(self):
        result, contents, partials = self.run_download("success", cached="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(contents, "complete")
        self.assertEqual(partials, [])


if __name__ == "__main__":
    unittest.main()
