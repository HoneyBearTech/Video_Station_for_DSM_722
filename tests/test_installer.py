"""Check how packages are downloaded and verified, using stand-in DSM commands."""

import re
import unittest

from harness import ALL_FILES, SOURCE, recorded_hashes, run_installer, sha256, tampered

CODECPACK = "CodecPack-x86_64-3.1.0-3005.spk"

# SHA-256 of the x86_64 files, downloaded with the certificate check on from
# both global.synologydownload.com and global.download.synology.com.
X86_64 = {
    "CodecPack-x86_64-3.1.0-3005.spk":
        "c4dcb4ab66cdd83cba7dcb909658bb239feab0325bfa794e3925c87e8656b85a",
    "VideoStation-x86_64-3.1.0-3153.spk":
        "e9b1a4935e255aac649953fa6b8a10ebcb3114970552dcf00b9ff93d62065715",
    "MediaServer-x86_64-2.0.5-3152.spk":
        "38e77b230f339e78721e7bdb7543ed56c48ff84564665220dcd62baa5fb32e8e",
}


def string_args(row):
    return [arg for arg in row if isinstance(arg, str)]


class RecordedChecksumTests(unittest.TestCase):
    def test_every_downloadable_file_has_one_checksum(self):
        hashes = recorded_hashes()
        self.assertEqual(sorted(hashes), sorted(ALL_FILES))
        self.assertEqual(len(re.findall(r'^ +\S+\.spk\)$', SOURCE, re.MULTILINE)), 21)

    def test_x86_64_checksums_match_cross_checked_values(self):
        hashes = recorded_hashes()
        for filename, value in X86_64.items():
            with self.subTest(filename=filename):
                self.assertEqual(hashes[filename], value)

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


if __name__ == "__main__":
    unittest.main()
