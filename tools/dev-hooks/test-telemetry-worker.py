#!/usr/bin/env python3
"""Tests for the bounded telemetry worker daemon.

Validates the fix for orphan uvx processes, unbounded concurrency,
@latest resolution overhead, and missing opt-out enforcement.

Run:  python3 tools/dev-hooks/test-telemetry-worker.py
"""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKER_PY = os.path.join(
    REPO_ROOT,
    "plugins", "alibabacloud-core", "hooks", "scripts", "lib",
    "telemetry_worker.py",
)


class _WorkerTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="telemetry-test-")
        self.env = os.environ.copy()
        self.env["ALIBABACLOUD_TELEMETRY_STATE_DIR"] = self.tmpdir
        self.env["ALIBABACLOUD_TELEMETRY_IDLE_TIMEOUT"] = "3"
        self.env["ALIBABACLOUD_TELEMETRY_POLL_INTERVAL"] = "0.2"
        self.env["ALIBABACLOUD_TELEMETRY_HARD_TIMEOUT"] = "5"
        self.env["ALIBABACLOUD_TELEMETRY_MAX_CONCURRENT"] = "2"
        self.env["ALIBABACLOUD_TELEMETRY_PROXY_VERSION"] = "0.1.21"
        self.env.pop("ALIBABACLOUD_TELEMETRY_DEBUG", None)
        self.env.pop("ALIBABACLOUD_TELEMETRY_UPLOADER", None)
        self.env.pop("CODEX_CLI", None)
        self.env.pop("COPILOT_CLI", None)
        self.env.pop("QODER_WORK", None)

    def tearDown(self):
        pid_path = os.path.join(self.tmpdir, "claude-code", "worker.pid")
        if os.path.exists(pid_path):
            try:
                with open(pid_path) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            except (OSError, ValueError):
                pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _enqueue(self, args=None, timeout=5):
        if args is None:
            args = ["--event-type", "tool_end", "--tool-name", "Bash"]
        code = textwrap.dedent(f"""\
            import sys, os
            sys.path.insert(0, {os.path.dirname(WORKER_PY)!r})
            from telemetry_worker import enqueue_and_start
            enqueue_and_start({args!r}, timeout={timeout})
        """)
        return subprocess.run(
            [sys.executable, "-c", code],
            env=self.env,
            capture_output=True,
            timeout=10,
        )

    def _wait_for_daemon(self, timeout=5):
        pid_path = os.path.join(self.tmpdir, "claude-code", "worker.pid")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if os.path.exists(pid_path):
                try:
                    with open(pid_path) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)
                    return pid
                except (OSError, ValueError):
                    pass
            time.sleep(0.2)
        return None

    def _cdir(self):
        return os.path.join(self.tmpdir, "claude-code")

    def _queue_dir(self):
        return os.path.join(self._cdir(), "upload-queue")


class TestEnqueue(_WorkerTestBase):

    def test_enqueue_creates_queue_file(self):
        result = self._enqueue()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        queue_dir = self._queue_dir()
        self.assertTrue(os.path.isdir(queue_dir))

    def test_enqueue_starts_daemon(self):
        self._enqueue()
        pid = self._wait_for_daemon()
        self.assertIsNotNone(pid, "daemon should start after enqueue")

    def test_daemon_is_single_instance(self):
        self._enqueue()
        pid1 = self._wait_for_daemon()
        self.assertIsNotNone(pid1)
        self._enqueue()
        time.sleep(0.5)
        pid_path = os.path.join(self._cdir(), "worker.pid")
        with open(pid_path) as f:
            pid2 = int(f.read().strip())
        self.assertEqual(pid1, pid2, "second enqueue should not start a new daemon")


class TestConcurrencyLimit(_WorkerTestBase):

    def test_concurrent_uploads_bounded(self):
        self.env["ALIBABACLOUD_TELEMETRY_MAX_CONCURRENT"] = "2"
        fake_uploader = os.path.join(self.tmpdir, "fake-uploader.sh")
        with open(fake_uploader, "w") as f:
            f.write("#!/bin/bash\nsleep 2\n")
        os.chmod(fake_uploader, 0o755)
        self.env["ALIBABACLOUD_TELEMETRY_UPLOADER"] = fake_uploader

        for _ in range(6):
            self._enqueue()
            time.sleep(0.05)

        self._wait_for_daemon(timeout=3)
        time.sleep(1)

        uploader_name = os.path.basename(fake_uploader)
        try:
            result = subprocess.run(
                ["pgrep", "-f", uploader_name],
                capture_output=True, text=True, timeout=5,
            )
            pids = [p for p in result.stdout.strip().split("\n") if p]
            self.assertLessEqual(
                len(pids), 2,
                f"expected at most 2 concurrent uploads, got {len(pids)}: {pids}",
            )
        except FileNotFoundError:
            self.skipTest("pgrep not available")

        for p in pids:
            try:
                os.kill(int(p), signal.SIGKILL)
            except (OSError, ValueError):
                pass


class TestHardTimeout(_WorkerTestBase):

    def test_upload_killed_after_timeout(self):
        self.env["ALIBABACLOUD_TELEMETRY_HARD_TIMEOUT"] = "2"
        fake_uploader = os.path.join(self.tmpdir, "slow-uploader.sh")
        with open(fake_uploader, "w") as f:
            f.write("#!/bin/bash\nsleep 60\n")
        os.chmod(fake_uploader, 0o755)
        self.env["ALIBABACLOUD_TELEMETRY_UPLOADER"] = fake_uploader

        self._enqueue(timeout=2)
        self._wait_for_daemon(timeout=3)
        time.sleep(4)

        uploader_name = os.path.basename(fake_uploader)
        try:
            result = subprocess.run(
                ["pgrep", "-f", uploader_name],
                capture_output=True, text=True, timeout=5,
            )
            pids = [p for p in result.stdout.strip().split("\n") if p]
            self.assertEqual(
                len(pids), 0,
                f"upload should be killed after timeout, but found: {pids}",
            )
        except FileNotFoundError:
            self.skipTest("pgrep not available")


class TestOptOut(_WorkerTestBase):

    def test_telemetry_false_no_upload(self):
        self.env["ALIBABACLOUD_TELEMETRY"] = "false"
        script = os.path.join(
            REPO_ROOT,
            "plugins", "alibabacloud-core", "hooks", "scripts",
            "post-tool-trace.sh",
        )
        payload = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "tool_output": "hi",
        })
        result = subprocess.run(
            ["bash", script],
            input=payload.encode(),
            capture_output=True,
            timeout=10,
            env=self.env,
        )
        self.assertEqual(result.returncode, 0)
        pid = self._wait_for_daemon(timeout=2)
        self.assertIsNone(pid, "daemon should not start when telemetry is disabled")

    def test_telemetry_false_no_queue_files(self):
        self.env["ALIBABACLOUD_TELEMETRY"] = "false"
        script = os.path.join(
            REPO_ROOT,
            "plugins", "alibabacloud-core", "hooks", "scripts",
            "post-tool-trace.sh",
        )
        payload = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "aliyun ecs DescribeInstances"},
            "tool_output": '{"Instances":{}}',
        })
        subprocess.run(
            ["bash", script],
            input=payload.encode(),
            capture_output=True,
            timeout=10,
            env=self.env,
        )
        queue_dir = self._queue_dir()
        if os.path.isdir(queue_dir):
            files = os.listdir(queue_dir)
            self.assertEqual(len(files), 0, f"no queue files when opted out, found: {files}")


class TestDaemonCleanup(_WorkerTestBase):

    def test_daemon_exits_on_idle_timeout(self):
        self.env["ALIBABACLOUD_TELEMETRY_IDLE_TIMEOUT"] = "2"
        fake_uploader = os.path.join(self.tmpdir, "instant-uploader.sh")
        with open(fake_uploader, "w") as f:
            f.write("#!/bin/bash\nexit 0\n")
        os.chmod(fake_uploader, 0o755)
        self.env["ALIBABACLOUD_TELEMETRY_UPLOADER"] = fake_uploader

        self._enqueue()
        pid = self._wait_for_daemon(timeout=3)
        self.assertIsNotNone(pid)

        time.sleep(5)
        try:
            os.kill(pid, 0)
            self.fail("daemon should have exited after idle timeout")
        except ProcessLookupError:
            pass

    def test_no_orphan_after_daemon_exit(self):
        self.env["ALIBABACLOUD_TELEMETRY_IDLE_TIMEOUT"] = "2"
        fake_uploader = os.path.join(self.tmpdir, "short-uploader.sh")
        with open(fake_uploader, "w") as f:
            f.write("#!/bin/bash\nsleep 0.5\nexit 0\n")
        os.chmod(fake_uploader, 0o755)
        self.env["ALIBABACLOUD_TELEMETRY_UPLOADER"] = fake_uploader

        for _ in range(5):
            self._enqueue()
            time.sleep(0.05)

        pid = self._wait_for_daemon(timeout=3)
        self.assertIsNotNone(pid)
        time.sleep(5)

        uploader_name = os.path.basename(fake_uploader)
        try:
            result = subprocess.run(
                ["pgrep", "-f", uploader_name],
                capture_output=True, text=True, timeout=5,
            )
            pids = [p for p in result.stdout.strip().split("\n") if p]
            self.assertEqual(
                len(pids), 0,
                f"no uploader processes should survive daemon exit, found: {pids}",
            )
        except FileNotFoundError:
            self.skipTest("pgrep not available")


class TestVersionPinning(_WorkerTestBase):

    def test_worker_uses_pinned_version(self):
        code = textwrap.dedent(f"""\
            import sys, os
            sys.path.insert(0, {os.path.dirname(WORKER_PY)!r})
            os.environ["ALIBABACLOUD_TELEMETRY_PROXY_VERSION"] = "0.1.21"
            os.environ.pop("ALIBABACLOUD_TELEMETRY_UPLOADER", None)
            from telemetry_worker import _uploader_cmd
            cmd = _uploader_cmd()
            assert "==0.1.21" in " ".join(cmd), f"expected pinned version, got: {{cmd}}"
            assert "@latest" not in " ".join(cmd), f"@latest found in: {{cmd}}"
            print("OK")
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=self.env,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"OK", result.stdout)


class TestStopHandlerNoPopen(_WorkerTestBase):

    def test_stop_handler_uses_enqueue(self):
        handler_path = os.path.join(
            REPO_ROOT,
            "plugins", "alibabacloud-core", "hooks", "scripts", "lib",
            "stop_handler.py",
        )
        with open(handler_path) as f:
            source = f.read()
        self.assertNotIn("start_new_session", source,
                         "stop_handler should not use start_new_session (creates orphans)")
        self.assertNotIn("@latest", source,
                         "stop_handler should not use @latest (causes UV cache bloat)")
        self.assertIn("enqueue_and_start", source,
                      "stop_handler should use bounded worker enqueue")


class TestShellScriptsNoFireAndForget(_WorkerTestBase):

    def test_post_tool_trace_no_disown(self):
        script = os.path.join(
            REPO_ROOT,
            "plugins", "alibabacloud-core", "hooks", "scripts",
            "post-tool-trace.sh",
        )
        with open(script) as f:
            source = f.read()
        self.assertNotIn("disown", source)
        self.assertNotIn("@latest", source)
        self.assertIn("telemetry_enqueue", source)

    def test_prompt_trace_no_disown(self):
        script = os.path.join(
            REPO_ROOT,
            "plugins", "alibabacloud-core", "hooks", "scripts",
            "prompt-trace.sh",
        )
        with open(script) as f:
            source = f.read()
        self.assertNotIn("disown", source)
        self.assertNotIn("@latest", source)
        self.assertIn("telemetry_enqueue", source)

    def test_stop_turn_increment_no_disown(self):
        script = os.path.join(
            REPO_ROOT,
            "plugins", "alibabacloud-core", "hooks", "scripts",
            "stop-turn-increment.sh",
        )
        with open(script) as f:
            source = f.read()
        self.assertNotIn("disown", source)
        self.assertNotIn("@latest", source)
        self.assertIn("telemetry_enqueue", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
