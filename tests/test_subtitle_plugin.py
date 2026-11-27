"""Execute the optional subtitle adapter with a mocked service and filesystem.

The PHP tests need a PHP command line interpreter and are skipped without one.
The setup script tests run only inside a container, like the installer tests.
For full coverage, run from the repository root:

  printf 'FROM python:3.13-slim\\nRUN apt-get update -qq && apt-get install -y -qq --no-install-recommends jq php-cli php-curl\\n' \\
      | docker build -q -t vs722-test -
  docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/w:ro" -w /w \\
      vs722-test python3 -m unittest discover -s tests -v
"""

import grp
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from harness import require_container


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "subtitle_plugins/opensubtitles_rest/subtitle.php"
PHP = os.environ.get("PHP_BINARY") or shutil.which("php")


@unittest.skipUnless(PHP, "PHP is not installed, so the subtitle plugin tests cannot run; "
                          "install php-cli or set PHP_BINARY")
class SubtitleAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="subtitle-adapter-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.video = self.folder / "Film.mkv"
        self.video.write_bytes(bytes(131072))

    def php(self, code):
        result = subprocess.run(
            [PHP, "-n", "-r", "require " + json.dumps(str(PLUGIN)) + ";" + code],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def invoke(self, code, responses, login=None):
        replies = [[200, json.dumps(login or {"token": "session-token", "base_url": "vip-api.opensubtitles.com"}), {}]] + responses
        script = "$replies=json_decode(" + json.dumps(json.dumps(replies)) + ",true);$calls=array();"
        script += '''$transport=function($url,$method,$headers,$body) use (&$replies,&$calls) {
            $calls[]=array($url,$method,$headers,$body);
            if (!$replies) { throw new RuntimeException('Unexpected service request'); }
            return array_shift($replies);
        };
        $client=new SubtitleRestClient('application-key',$transport);
        try {
            $client->login('account-name','account-password');
        '''
        script += code + ";echo json_encode(array('result'=>$result,'calls'=>$calls));"
        script += "} catch (Throwable $error) {echo json_encode(array('error'=>$error->getMessage(),'calls'=>$calls));}"
        return self.php(script)

    def search_code(self):
        return "$result=$client->search(" + "json_decode(" + json.dumps(json.dumps({"path": str(self.video), "lang": "eng", "limit": 2})) + ",true))"

    def test_php_syntax(self):
        result = subprocess.run([PHP, "-n", "-l", str(PLUGIN)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_search_returns_file_ids_with_legacy_shape(self):
        payload = {"data": [{"id": "group-id", "attributes": {"language": "en", "release": "Film", "files": [
            {"file_id": 123, "file_name": "Film.srt"}, {"file_id": 456, "file_name": "Film.other.srt"}]}}]}
        output = self.invoke(self.search_code(), [[200, json.dumps(payload), {}]])
        self.assertEqual(output["result"]["total"], 2)
        self.assertEqual(output["result"]["items"][0]["id"], "rest-en-123")
        self.assertEqual(output["result"]["items"][0]["language_id"], "eng")
        self.assertIn("vip-api.opensubtitles.com", output["calls"][1][0])
        self.assertIn("Authorization: Bearer session-token", output["calls"][1][2])
        self.assertEqual(json.loads(output["calls"][0][3]), {"username": "account-name", "password": "account-password"})

    def test_hash_only_search_preserves_the_original_command_contract(self):
        options = {"hash": "1234567890abcdef", "size": 900000, "lang": "eng"}
        payload = {"data": [{"attributes": {"language": "en", "files": [{"file_id": 123}]}}]}
        code = "$result=$client->search(json_decode(" + json.dumps(json.dumps(options)) + ",true))"
        output = self.invoke(code, [[200, json.dumps(payload), {}]])
        self.assertEqual(output["result"]["total"], 1)
        self.assertFalse(output["result"]["items"][0]["downloaded"])
        self.assertEqual(output["result"]["items"][0]["subtitle_id"], "")
        self.assertNotIn("query=", output["calls"][1][0])

    def test_large_file_identifiers_are_rejected(self):
        output = self.invoke("$result=$client->download(" + json.dumps(str(self.video)) + ",'rest-en-2147483648')", [])
        self.assertEqual(output["error"], "Subtitle file identifier is out of range")

    def test_sidecar_names_keep_legacy_language_suffixes(self):
        for identifier, language in (("rest-en-123", "eng"), ("rest-pt-br-123", "pob"), ("rest-fr-123", "fre")):
            with self.subTest(identifier=identifier):
                destination = self.php("echo json_encode(SubtitleRestClient::subtitlePath(" +
                    json.dumps(str(self.video)) + "," + json.dumps(identifier) + "));")
                self.assertEqual(Path(destination).name, f"Film.rest-123.{language}.srt")

    def test_movie_hash_matches_reference_sum(self):
        data = bytes(range(256)) * 1024
        self.video.write_bytes(data)
        expected = (len(data) + sum(struct.unpack("<8192Q", data[:65536])) + sum(struct.unpack("<8192Q", data[-65536:]))) & ((1 << 64) - 1)
        result = self.php("echo json_encode(SubtitleRestClient::movieHash(" + json.dumps(str(self.video)) + "));")
        self.assertEqual(result, f"{expected:016x}")

    def test_download_is_atomic_and_file_host_receives_no_credentials(self):
        link = "https://www.opensubtitles.com/download/temporary-token"
        code = "$first=$client->download(" + json.dumps(str(self.video)) + ",'rest-en-123');"
        code += "$result=$client->download(" + json.dumps(str(self.video)) + ",'rest-en-123')"
        output = self.invoke(code, [[200, json.dumps({"link": link, "remaining": 0}), {}], [200, "1\n00:00:01,000 --> 00:00:02,000\nHello\n", {}]])
        destination = self.folder / "Film.rest-123.eng.srt"
        self.assertEqual(output["result"], {"id": str(destination)})
        self.assertIn("Hello", destination.read_text())
        self.assertEqual(len(output["calls"]), 3)
        self.assertEqual(json.loads(output["calls"][1][3]), {"file_id": 123, "sub_format": "srt"})
        self.assertEqual(output["calls"][2][2], ["User-Agent: VideoStation-Subtitle-REST v1.0"])
        self.assertEqual(list(self.folder.glob(".subtitle-*")), [])

    def test_quota_error_does_not_write_a_subtitle_or_echo_service_body(self):
        output = self.invoke("$result=$client->download(" + json.dumps(str(self.video)) + ",'rest-en-123')", [[406, "private account details", {}]])
        self.assertEqual(output["error"], "Subtitle service returned HTTP 406")
        self.assertEqual(list(self.folder.glob("*.srt")), [])

    def test_untrusted_login_host_and_redirect_are_rejected(self):
        output = self.invoke(self.search_code(), [], {"token": "session-token", "base_url": "example.com"})
        self.assertEqual(output["error"], "Untrusted service URL")
        output = self.invoke(self.search_code(), [[302, "", {"location": "https://example.com/leak"}]])
        self.assertEqual(output["error"], "Untrusted service URL")
        self.assertEqual(len(output["calls"]), 2)

    def test_traversal_and_symlink_destinations_are_rejected(self):
        output = self.invoke("$result=$client->download(" + json.dumps(str(self.video)) + ",'../../outside')", [])
        self.assertEqual(output["error"], "Invalid subtitle selection")
        outside = self.folder / "outside"
        outside.write_text("preserve")
        (self.folder / "Film.rest-123.eng.srt").symlink_to(outside)
        output = self.invoke("$result=$client->download(" + json.dumps(str(self.video)) + ",'rest-en-123')", [])
        self.assertEqual(output["error"], "Subtitle destination is unsafe")
        self.assertEqual(outside.read_text(), "preserve")

    def test_empty_download_leaves_no_file(self):
        output = self.invoke("$result=$client->download(" + json.dumps(str(self.video)) + ",'rest-en-123')", [
            [200, json.dumps({"link": "https://www.opensubtitles.com/download/file"}), {}], [200, "", {}]])
        self.assertEqual(output["error"], "Subtitle download is empty")
        self.assertEqual(list(self.folder.glob("*.srt")), [])

    def test_invalid_action_stops_before_key_or_network_access(self):
        result = subprocess.run([PHP, "-n", str(PLUGIN), "--action=invalid"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Use --action=", result.stderr)
        self.assertNotIn("API key", result.stderr)

    def test_world_readable_key_is_rejected_before_network_access(self):
        key = self.folder / "key"
        key.write_text("private-key")
        key.chmod(0o644)
        result = subprocess.run([PHP, "-n", str(PLUGIN), "--action=search"],
            env={**os.environ, "SUBTITLE_REST_KEY_FILE": str(key)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("private-key", result.stderr + result.stdout)
        self.assertIn("unsafe permissions", result.stderr)


class SubtitleInstallerTests(unittest.TestCase):
    def setUp(self):
        require_container()
        temporary = tempfile.TemporaryDirectory(prefix="subtitle-install-")
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        scripts = folder / "scripts"
        scripts.mkdir()
        (folder / "subtitle_plugins").symlink_to(ROOT / "subtitle_plugins", target_is_directory=True)
        bindir = folder / "bin"
        bindir.mkdir()
        # The fixture copy mocks the root requirement, ownership and package status only.
        source = (ROOT / "scripts/install-subtitle-plugin.sh").read_text()
        source = source.replace('if [[ $EUID != 0 ]]; then', 'if false; then')
        installer = scripts / "install.sh"
        installer.write_text(source.replace("/usr/syno/bin/synopkg", str(bindir / "synopkg")))
        mocks = {
            "chown": "exit 0\n",
            "synopkg": 'exit "${SUBTITLE_TEST_STATUS:-17}"\n',
            # Can be told to fail publishing the adapter, or putting the backup back.
            "mv": 'if [ "${SUBTITLE_FAIL_PUBLISH:-0}" = 1 ]; then\n'
                  '  case "$1" in */.subtitle-rest.*) exit 1;; esac\nfi\n'
                  'if [ "${SUBTITLE_FAIL_RESTORE:-0}" = 1 ]; then\n'
                  '  case "$1" in */syno_opensubtitles.original) exit 1;; esac\nfi\n'
                  'exec /bin/mv "$@"\n',
        }
        for name, body in mocks.items():
            (bindir / name).write_text("#!/bin/sh\n" + body)
            (bindir / name).chmod(0o755)
        package = folder / "package"
        self.original = package / "target/subtitle_plugins/syno_opensubtitles"
        self.original.mkdir(parents=True)
        (self.original / "original-marker").write_text("original")
        (package / "INFO").write_text('version="30.1.0-3153"\n')
        key = folder / "key"
        key.write_text("application-key\n")
        self.state = package / "target/.subtitle-plugin-backups"
        self.backup = self.state / "syno_opensubtitles.original"
        self.env = {**os.environ, "PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
        base = ["bash", str(installer), f"--package-root={package}"]
        self.install = base + [f"--api-key-file={key}", "--reader-group=" + grp.getgrgid(os.getgid()).gr_name]
        self.restore = base + ["--restore"]

    def run_setup(self, command, status=0, **extra):
        result = subprocess.run(command, env={**self.env, **extra}, capture_output=True, text=True)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result

    def replace_plugin_as_an_update_does(self):
        shutil.rmtree(self.original)
        self.original.mkdir()
        (self.original / "updated-marker").write_text("updated")

    def set_aside(self, kind):
        return list(self.state.glob(f"syno_opensubtitles.{kind}.*"))

    def test_fixture_install_restore_and_reinstall_protection(self):
        # Running and unknown service states stop before any plugin rename.
        for status in ("0", "55", "99"):
            self.run_setup(self.install, 1, SUBTITLE_TEST_STATUS=status)
            self.assertTrue((self.original / "original-marker").exists())
        # Publishing failure rolls the original directory back and removes private staging.
        self.run_setup(self.install, 1, SUBTITLE_FAIL_PUBLISH="1")
        self.assertTrue((self.original / "original-marker").exists())
        self.assertEqual(list(self.state.iterdir()), [])
        self.run_setup(self.install)
        self.assertTrue((self.original / ".rest-adapter").exists())
        self.assertEqual(list(self.original.parent.iterdir()), [self.original])
        self.assertTrue((self.backup / "original-marker").exists())
        self.assertEqual((self.original / "api-key").stat().st_mode & 0o777, 0o640)
        self.run_setup(self.install, 1)
        self.run_setup(self.restore)
        self.assertEqual((self.original / "original-marker").read_text(), "original")
        self.assertFalse((self.original / "api-key").exists())
        # Recover an interruption between renaming the original and publishing the adapter.
        self.original.rename(self.backup)
        self.run_setup(self.restore)
        self.assertTrue((self.original / "original-marker").exists())

    def test_failed_restore_puts_the_adapter_back(self):
        self.run_setup(self.install)
        self.run_setup(self.restore, 1, SUBTITLE_FAIL_RESTORE="1")
        self.assertTrue((self.original / ".rest-adapter").exists())
        self.assertTrue((self.original / "api-key").exists())
        self.assertTrue((self.backup / "original-marker").exists())
        self.assertEqual(list(self.state.iterdir()), [self.backup])

    def test_restore_after_an_update_replaced_the_adapter(self):
        self.run_setup(self.install)
        self.replace_plugin_as_an_update_does()
        # A failure leaves the updated plugin and the backup where they were.
        self.run_setup(self.restore, 1, SUBTITLE_FAIL_RESTORE="1")
        self.assertTrue((self.original / "updated-marker").exists())
        self.assertTrue((self.backup / "original-marker").exists())
        self.assertEqual(list(self.state.iterdir()), [self.backup])
        result = self.run_setup(self.restore)
        self.assertTrue((self.original / "original-marker").exists())
        self.assertFalse(self.backup.exists())
        [replaced] = self.set_aside("replaced")
        self.assertTrue((replaced / "updated-marker").exists())
        self.assertIn(str(replaced), result.stdout)

    def test_reinstall_after_an_update_replaced_the_adapter(self):
        self.run_setup(self.install)
        self.replace_plugin_as_an_update_does()
        # A failure leaves the updated plugin and the earlier backup where they were.
        self.run_setup(self.install, 1, SUBTITLE_FAIL_PUBLISH="1")
        self.assertTrue((self.original / "updated-marker").exists())
        self.assertTrue((self.backup / "original-marker").exists())
        self.assertEqual(list(self.state.iterdir()), [self.backup])
        result = self.run_setup(self.install)
        self.assertTrue((self.original / ".rest-adapter").exists())
        self.assertTrue((self.backup / "updated-marker").exists())
        [previous] = self.set_aside("previous")
        self.assertTrue((previous / "original-marker").exists())
        self.assertIn(str(previous), result.stdout)
        # The adapter is installed again, so a further install is refused.
        self.run_setup(self.install, 1)
        # --restore brings back the plugin the update installed.
        self.run_setup(self.restore)
        self.assertTrue((self.original / "updated-marker").exists())
        self.assertTrue((previous / "original-marker").exists())


if __name__ == "__main__":
    unittest.main()
