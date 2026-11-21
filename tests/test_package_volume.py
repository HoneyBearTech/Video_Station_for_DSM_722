"""Check explicit-volume API requests and failure behavior without DSM services."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "lib" / "package_volume.sh"
SETTINGS = {"success": True, "data": {"volume_list": [{"mount_point": "/volume2"}]}}
CHECK = {
    "success": True,
    "data": {"is_occupied": False, "volume_list": [{"mount_point": "/volume2"}]},
}
INSTALL = {"success": True, "data": {"packageName": "Advanced Media Extensions"}}

MOCKS = r'''
source "$LIBRARY"
volume_require_tools(){ :; }
volume_is_mounted(){ [[ $MOUNTED == yes ]]; }
volume_webapi(){
    printf '%s\t' "$@" >> "$CALLS"
    printf '\n' >> "$CALLS"
    [[ $PROCESS_STATUS == 0 ]] || return "$PROCESS_STATUS"
    case "$*" in
        *method=check*) printf '%s\n' "$CHECK_REPLY" ;;
        *method=install*) printf '%s\n' "$INSTALL_REPLY" ;;
        *) printf '%s\n' "$SETTINGS_REPLY" ;;
    esac
}
volume_package_status(){ return "$PACKAGE_STATUS"; }
volume_package_target(){ printf '%s\n' "$PACKAGE_TARGET"; }
sleep(){ :; }
'''


class VolumeTests(unittest.TestCase):
    def run_helper(self, command=None, **overrides):
        with tempfile.TemporaryDirectory(prefix="volume-test-") as directory:
            folder = Path(directory)
            package = folder / 'sample " package.spk'
            package.write_text("package")
            calls = folder / "calls"
            values = {
                "LIBRARY": str(LIBRARY),
                "SPK": str(package),
                "CALLS": str(calls),
                "MOUNTED": "yes",
                "PROCESS_STATUS": "0",
                "PACKAGE_STATUS": "0",
                "PACKAGE_TARGET": "/volume2/@appstore/CodecPack",
                "SETTINGS_REPLY": json.dumps(SETTINGS),
                "CHECK_REPLY": json.dumps(CHECK),
                "INSTALL_REPLY": json.dumps(INSTALL),
            }
            values.update(overrides)
            result = subprocess.run(
                ["bash", "-c", MOCKS + "\n" + (
                    command or 'volume_install_spk "$SPK" CodecPack /volume2'
                )],
                env={**os.environ, **values},
                capture_output=True, text=True, timeout=5,
            )
            arguments = [line.rstrip("\t").split("\t")
                         for line in calls.read_text().splitlines()] if calls.exists() else []
            return result, arguments, str(package)

    def test_install_uses_explicit_volume_and_original_local_file(self):
        result, calls, package = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 3)
        self.assertIn("method=get", calls[0])
        self.assertIn("method=check", calls[1])
        self.assertIn("method=install", calls[2])
        fields = dict(argument.split("=", 1) for argument in calls[2])
        self.assertEqual(json.loads(fields["volume_path"]), "/volume2")
        self.assertEqual(json.loads(fields["path"]), package)
        self.assertEqual(fields["check_codesign"], "true")
        self.assertEqual(fields["force"], "false")
        self.assertEqual(json.loads(fields["extra_values"]), "{}")
        self.assertNotIn("method=set", " ".join(" ".join(call) for call in calls))

    def test_known_command_banner_is_accepted(self):
        result, calls, _ = self.run_helper(
            INSTALL_REPLY='[Line 206] Exec WebAPI: api=SYNO.Core.Package.Installation\n' +
                          json.dumps(INSTALL)
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 3)

    def test_invalid_or_unmounted_volumes_do_not_reach_api(self):
        for target in ("/volume0", "/volume2/../volume1", "/volumeUSB1", "volume2"):
            with self.subTest(target=target):
                result, calls, _ = self.run_helper(
                    command='volume_check_target "$REQUESTED"', REQUESTED=target
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
        result, calls, _ = self.run_helper(MOUNTED="no")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_unlisted_volume_blocks_installation(self):
        reply = {"success": True, "data": {"volume_list": [{"mount_point": "/volume1"}]}}
        result, calls, _ = self.run_helper(SETTINGS_REPLY=json.dumps(reply))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_precheck_rejection_blocks_installation(self):
        for data in ({"is_occupied": True, "volume_list": CHECK["data"]["volume_list"]},
                     {"is_occupied": False, "volume_list": []}, {}):
            with self.subTest(data=data):
                result, calls, _ = self.run_helper(
                    CHECK_REPLY=json.dumps({"success": True, "data": data})
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(calls), 2)

    def test_failed_or_malformed_replies_block_installation(self):
        replies = (
            "not JSON", json.dumps({"success": False, "error": {"code": 120}}),
            json.dumps({"success": "true", "data": {}}),
            json.dumps(SETTINGS) + "\n" + json.dumps(SETTINGS),
            "unexpected diagnostic\n" + json.dumps(SETTINGS),
            json.dumps({"success": True, "data": {"has_fail": True}}),
            json.dumps({"success": True, "data": {}, "error": {"code": 120}}),
            json.dumps({"success": True, "data": {"success": False}}),
            json.dumps({"success": True, "data": {"result": [{"success": False}]}}),
            json.dumps({"success": True, "data": {"result": [{"error": {"code": 263}}]}}),
        )
        for reply in replies:
            with self.subTest(reply=reply):
                result, calls, _ = self.run_helper(SETTINGS_REPLY=reply)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(calls), 1)

    def test_nonzero_command_exit_is_an_error_even_with_success_json(self):
        result, calls, _ = self.run_helper(PROCESS_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_install_api_failure_is_not_success(self):
        result, calls, _ = self.run_helper(
            INSTALL_REPLY=json.dumps({"success": False, "error": {"code": 263}})
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 3)

    def test_task_acceptance_response_is_not_a_completed_install(self):
        for data in ({"taskid": "pending"}, {"packageName": "CodecPack", "task_id": "pending"},
                     {"packageName": "CodecPack", "finished": False}, {},
                     {"packageName": True}):
            with self.subTest(data=data):
                result, calls, _ = self.run_helper(
                    INSTALL_REPLY=json.dumps({"success": True, "data": data})
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("completed installation", result.stderr)
                self.assertEqual(len(calls), 3)

    def test_api_acceptance_is_not_installation_confirmation(self):
        for status, target in (("255", "/volume2/@appstore/CodecPack"),
                               ("150", "/volume2/@appstore/CodecPack"),
                               ("0", "/volume1/@appstore/CodecPack"), ("0", "")):
            with self.subTest(status=status, target=target):
                result, calls, _ = self.run_helper(
                    PACKAGE_STATUS=status, PACKAGE_TARGET=target
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not confirmed", result.stderr)
                self.assertEqual(len(calls), 3)

    def test_stopped_and_starting_packages_can_be_confirmed(self):
        for status in ("17", "55"):
            with self.subTest(status=status):
                result, _, _ = self.run_helper(PACKAGE_STATUS=status)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_package_or_invalid_id_never_calls_api(self):
        for command in ('volume_install_spk /missing/file.spk CodecPack /volume2',
                        'volume_install_spk "$SPK" ../CodecPack /volume2',
                        ': > "$SPK"; volume_install_spk "$SPK" CodecPack /volume2'):
            with self.subTest(command=command):
                result, calls, _ = self.run_helper(command=command)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
