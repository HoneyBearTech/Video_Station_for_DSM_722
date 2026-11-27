"""Check the options, and how packages are downloaded and verified, using stand-in DSM commands."""

import re
import subprocess
import unittest

from harness import (ALL_FILES, SCRIPT, SOURCE, recorded_hashes, require_container, run_installer,
                     sha256, tampered)

CODECPACK = "CodecPack-x86_64-3.1.0-3005.spk"

# SHA-256 of every package file, downloaded with the certificate check on from
# global.synologydownload.com. The x86_64 files were also downloaded from
# global.download.synology.com and matched.
EXPECTED = {
    "CodecPack-armada37xx-3.1.0-3005.spk": "5db7166d7186004e72eb8bc2d650a8dd8a17760afe141c9dc3aedec13bf0119b",
    "CodecPack-armada38x-3.1.0-3005.spk": "496a6276aa7bf79fcdca238d6078bf890b25384ff445b357165b8766111b5717",
    "CodecPack-armv7-3.1.0-3005.spk": "e38bb5dc81b7ac4551162c42ae2e3f2cf64b767624669bf65ca0dd53dbb9a185",
    "CodecPack-monaco-3.1.0-3005.spk": "b6917fadbcc5f8c26a1a6cd694ffe9928fcaba0890df3dad9827a27ad5169e90",
    "CodecPack-rtd1296-3.1.0-3005.spk": "6c46f434c02f0a56071844ec67fd91051179f543a18457d6b7e22bee9c13a743",
    "CodecPack-rtd1619b-3.1.0-3005.spk": "d50b70dc1d89c607cd545d5ab70b6d047355cf13aa628823ef63079b3b54d44d",
    "CodecPack-x86_64-3.1.0-3005.spk": "c4dcb4ab66cdd83cba7dcb909658bb239feab0325bfa794e3925c87e8656b85a",
    "VideoStation-armada37xx-3.1.0-3153.spk": "cc5070f3d6794ec6740301e7cc8698cd100d49d008ac634d37aeaf77912ab977",
    "VideoStation-armada38x-3.1.0-3153.spk": "e93727ea8495753017dc635ed352b40a1dec14995eda9cf7d7bd045c9357928f",
    "VideoStation-armv7-3.1.0-3153.spk": "5b4cfc4bd43b0c4f896a38f850f09d4673ae49e9d72eeea0180865d9a7e28230",
    "VideoStation-monaco-3.1.0-3153.spk": "8c1dd917b28c9184ef5bcecf6087e24d48ea65fd0ad457f37f9e03ae95236963",
    "VideoStation-rtd1296-3.1.0-3153.spk": "4f94403b959c1697ea1b21b5decff4777201ada72370dd31c45ecbadcdf00d4d",
    "VideoStation-rtd1619b-3.1.0-3153.spk": "d38267b4cdae6f2e69ba45a76aa9554cfbd5b503264783c68284f060f80325fd",
    "VideoStation-x86_64-3.1.0-3153.spk": "e9b1a4935e255aac649953fa6b8a10ebcb3114970552dcf00b9ff93d62065715",
    "MediaServer-armada37xx-2.0.5-3152.spk": "17e11f8146a62712861cb1c8df9a223a5eee02fe7ea08cd86899ba2d3f4366a8",
    "MediaServer-armada38x-2.0.5-3152.spk": "3d90c6157b7e01bb2c46901f35224a8d7530bf28b69db2e48c0daf070b6cda53",
    "MediaServer-armv7-2.0.5-3152.spk": "87da07b1d33b56c2186b682a1dbb313d4f4889fae39947c34276fce951ba379b",
    "MediaServer-monaco-2.0.5-3152.spk": "5e8aa508b5ae772bc30356e8e39b86e4b215b4b67fa2898b4b7d63f37b9259b1",
    "MediaServer-rtd1296-2.0.5-3152.spk": "fa82ac4d020ffd7b79d793191bdda102b3866434c6879ce47a69d29c17f4364a",
    "MediaServer-rtd1619b-2.0.5-3152.spk": "62c467ddc566f8c5afee6ba2be05ff029cc9a09c1926c51aa9a6eab355e51564",
    "MediaServer-x86_64-2.0.5-3152.spk": "38e77b230f339e78721e7bdb7543ed56c48ff84564665220dcd62baa5fb32e8e",
}


def string_args(row):
    return [arg for arg in row if isinstance(arg, str)]


class RecordedChecksumTests(unittest.TestCase):
    def test_every_downloadable_file_has_one_checksum(self):
        hashes = recorded_hashes()
        self.assertEqual(sorted(hashes), sorted(ALL_FILES))
        self.assertEqual(len(re.findall(r'^ +\S+\.spk\)$', SOURCE, re.MULTILINE)), 21)

    def test_every_checksum_matches_the_downloaded_file(self):
        self.assertEqual(sorted(EXPECTED), sorted(ALL_FILES))
        hashes = recorded_hashes()
        for filename, value in EXPECTED.items():
            with self.subTest(filename=filename):
                self.assertEqual(hashes.get(filename), value)

    def test_source_has_no_insecure_curl_and_no_self_update(self):
        self.assertNotRegex(SOURCE, r"curl\s+-[A-Za-z]*k")
        self.assertNotIn("--insecure", SOURCE)
        self.assertNotIn("api.github.com", SOURCE)
        self.assertNotRegex(SOURCE, r"(?m)^\s*exec\b")


class DownloadTests(unittest.TestCase):
    def assert_nas_unchanged(self, run, installed=None):
        self.assertEqual(run.returncode, 3, run.output)
        self.assertEqual(run.state, installed or {})
        self.assertFalse(run.backup)
        self.assertFalse(any(row[0] == "synosetkeyvalue" for row in run.operations))
        self.assertFalse(any(row[0] == "synopkg" and row[1] in ("uninstall", "install")
                             for row in run.operations))
        self.assertEqual(run.downloads_left, [], "private folder was not removed")

    def test_curl_is_https_only_and_checks_certificates(self):
        run = run_installer("all")
        self.assertEqual(run.returncode, 0, run.output)
        self.assertEqual(len(run.curl_calls()), 3)
        for row in run.curl_calls():
            args = string_args(row)
            with self.subTest(call=args):
                self.assertEqual(args[1], "-q", "-q must come first so .curlrc is ignored")
                self.assertNotIn("--insecure", args)
                self.assertFalse(any(re.fullmatch(r"-[A-Za-z]*k[A-Za-z]*", arg) for arg in args))
                self.assertEqual(args[args.index("--proto") + 1], "=https")
                self.assertEqual(args[args.index("--proto-redir") + 1], "=https")
                self.assertIn("-f", "".join(arg for arg in args if re.fullmatch(r"-[A-Za-z]+", arg)))
                url = [arg for arg in args if "://" in arg][0]
                self.assertTrue(url.startswith("https://"))

    def test_wrong_checksum_on_every_server_is_refused(self):
        run = run_installer("onlyamc", curl={"*": "wrong"})
        self.assert_nas_unchanged(run)
        self.assertEqual(run.downloaded_files(), [CODECPACK] * 3)
        self.assertIn("SHA-256 checksum check failed for " + CODECPACK, run.output)
        self.assertIn("Expected: " + sha256("genuine " + CODECPACK + "\n"), run.output)
        self.assertIn("Actual:   " + sha256(tampered(CODECPACK)), run.output)

    def test_missing_checksum_is_refused(self):
        run = run_installer("onlyamc", drop_hashes=(CODECPACK,))
        self.assert_nas_unchanged(run)
        self.assertIn("No SHA-256 checksum is recorded for " + CODECPACK, run.output)

    def test_failed_server_falls_back_to_the_next(self):
        run = run_installer("onlyamc", curl={"global.synologydownload.com": "fail"})
        self.assertEqual(run.returncode, 0, run.output)
        self.assertEqual(run.downloaded_files(), [CODECPACK] * 2)
        self.assertIn("curl exit code 22", run.output)
        self.assertEqual(run.state["CodecPack"]["version"], "30.1.0-3005")

    def test_all_servers_failing_exits_3_without_changes(self):
        installed = {"CodecPack": {"version": "4.0.0-4025", "running": True}}
        run = run_installer("all", installed, curl={"*": "fail"})
        self.assert_nas_unchanged(run, installed)
        self.assertIn("Failed to download " + CODECPACK, run.output)
        self.assertIn("Nothing was changed on the NAS", run.output)

    def test_certificate_failure_explains_what_to_check(self):
        run = run_installer("onlyamc", curl={"*": "cert"})
        self.assert_nas_unchanged(run)
        self.assertIn("Certificate check failed", run.output)
        self.assertIn("date and time", run.output)
        self.assertIn("update DSM", run.output)
        self.assertIn("Nothing was changed on the NAS", run.output)

    def test_certificate_failure_then_good_server_does_not_say_nothing_changed(self):
        run = run_installer("onlyamc", curl={"global.synologydownload.com": "cert"})
        self.assertEqual(run.returncode, 0, run.output)
        self.assertEqual(run.downloaded_files(), [CODECPACK] * 2)
        self.assertIn("Certificate check failed for global.synologydownload.com", run.output)
        self.assertNotIn("Nothing was changed", run.output)
        self.assertEqual(run.state["CodecPack"]["version"], "30.1.0-3005")

    def test_private_folder_failure_stops_before_any_change(self):
        run = run_installer("all", plant=[CODECPACK], source_edits=(
            ("mktemp -d /tmp/vs722.XXXXXX", "mktemp -d /tmp/missing-folder/vs722.XXXXXX"),))
        self.assertEqual(run.returncode, 1, run.output)
        self.assertIn("Failed to create the private download folder", run.output)
        self.assertIn("Nothing was changed on the NAS", run.output)
        self.assertEqual(run.curl_calls(), [])
        self.assertFalse(run.backup)
        self.assertFalse(any(row[0] in ("synopkg", "synosetkeyvalue") for row in run.operations))
        # The exit trap must not delete anything else in /tmp.
        self.assertIn(CODECPACK, run.planted)

    def test_partial_downloads_are_deleted_before_the_next_try(self):
        run = run_installer("all", curl={"*": "fail"})
        self.assertEqual(run.returncode, 3, run.output)
        self.assertFalse(any(row[-1]["preexisting"] for row in run.curl_calls()))

    def test_missing_sha256sum_fails_closed(self):
        run = run_installer("onlyamc", source_edits=(("command -v sha256sum",
                                                      "command -v sha256sum-not-installed"),))
        self.assert_nas_unchanged(run)
        self.assertEqual(run.curl_calls(), [])
        self.assertIn("sha256sum not found", run.output)

    def test_planted_package_in_tmp_is_ignored(self):
        planted = [CODECPACK, "VideoStation-x86_64-3.1.0-3153.spk", "MediaServer-x86_64-2.0.5-3152.spk"]
        with self.subTest(downloads="fail"):
            run = run_installer("all", curl={"*": "fail"}, plant=planted)
            self.assert_nas_unchanged(run)
        with self.subTest(downloads="ok"):
            run = run_installer("all", plant=planted)
            self.assertEqual(run.returncode, 0, run.output)
            self.assertEqual(sorted(run.downloaded_files()), sorted(planted))
            installs = [row[2] for row in run.operations if row[:2] == ["synopkg", "install"]]
            self.assertEqual(len(installs), 3)
            for path in installs:
                self.assertRegex(path, r"/tmp/vs722\.[^/]+/[^/]+\.spk$")
            # The stand-in installer only accepts genuine files from the private folder.
            self.assertEqual(set(run.state), {"CodecPack", "VideoStation", "MediaServer"})

    def test_private_folder_is_removed_on_exit(self):
        for curl in ({}, {"*": "fail"}):
            with self.subTest(curl=curl):
                run = run_installer("all", curl=curl)
                self.assertEqual(run.downloads_left, [])
                self.assertTrue(any("/tmp/vs722." in row[row.index("-o") + 1]
                                    for row in run.curl_calls()))


class CommandLineTests(unittest.TestCase):
    """Ported from PR #3: a mistyped option must never run the installer."""

    def parse(self, *args, show):
        """Run only the option parser, then print the given shell expression."""
        require_container()
        parser = SOURCE.split("# Check script is running as root", 1)[0]
        return subprocess.run(["bash", "-c", parser + "\nprintf '%s' " + show, str(SCRIPT), *args],
                              capture_output=True, text=True, timeout=10)

    def test_bad_or_extra_options_exit_2_before_anything_runs(self):
        for args in (("--unknown",), ("--install",), ("--install=bad",), ("--install=",),
                     ("--volume",), ("--volume=",), ("--volume=/volume0",), ("--volume=/tmp",),
                     ("--volume=/volume2/../volume1",), ("--volume=/volumeUSB1",),
                     ("--volume=volume2",), ("--install=all", "extra"), ("-l",), ("--log",),
                     ("-d",), ("--debug",), ("--autoupdate=3",)):
            with self.subTest(args=args):
                run = run_installer(args=args)
                self.assertEqual(run.returncode, 2, run.output)
                self.assertIn("Usage:", run.output)
                # Not even the root check ran.
                self.assertEqual(run.operations, [])

    def test_help_and_version_exit_0_before_anything_runs(self):
        for flag, expected in (("--help", "Usage:"), ("-h", "--volume=/volumeN"),
                               ("--version", "Video_Station_for_DSM_722 v1.4.22-hbt.2"),
                               ("-v", "Video_Station_for_DSM_722")):
            with self.subTest(flag=flag):
                run = run_installer(args=(flag,))
                self.assertEqual(run.returncode, 0, run.output)
                self.assertIn(expected, run.output)
                self.assertEqual(run.operations, [])

    def test_trace_option_works(self):
        for flag in ("-t", "--trace"):
            with self.subTest(flag=flag):
                run = run_installer("onlyamc", extra_args=(flag,))
                self.assertEqual(run.returncode, 0, run.output)
                self.assertIn("package_install called from main", run.output)
        run = run_installer("onlyamc")
        self.assertNotIn("called from", run.output)

    def test_install_choices_set_the_expected_package_flags(self):
        cases = {"all": "yes||", "novs": "yes|yes|", "noms": "yes||yes", "onlyamc": "yes|yes|yes"}
        for choice, expected in cases.items():
            with self.subTest(choice=choice):
                result = self.parse(f"--install={choice}", show='"$auto|$no_vs|$no_ms"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_volume_value_is_kept_as_given(self):
        for args in (("--volume=/volume2",), ("--volume", "/volume12"), ("--install=all", "--volume=/volume3")):
            with self.subTest(args=args):
                result = self.parse(*args, show='"$install_volume"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, args[-1].rsplit("=", 1)[-1])

    def test_no_op_options_are_gone(self):
        for name in ("autoupdate", "debug=yes", "log=yes", "delay="):
            with self.subTest(name=name):
                self.assertNotIn(name, SOURCE)


if __name__ == "__main__":
    unittest.main()
