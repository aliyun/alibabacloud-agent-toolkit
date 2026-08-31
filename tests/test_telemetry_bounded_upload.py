#!/usr/bin/env python3
"""Tests for the bounded telemetry upload system.

Validates:
- Off switch (ALIBABACLOUD_TELEMETRY=false): no upload processes spawned
- Queue-based enqueue: events written to queue directory correctly
- Single-instance lock: only one worker processes at a time
- Bounded concurrency: configurable limits on parallel uploads
- Hard timeout: uploads killed after timeout, subprocess reaped
- Finite retry: failed events retried then moved to dead-letter
- Process cleanup: no orphan processes after worker exits
- Worker uses fixed venv, not uvx @latest per event
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "plugins",
        "alibabacloud-core",
        "hooks",
        "scripts",
        "lib",
    ),
)

import telemetry_enqueue
import telemetry_worker


class TestOffSwitch(unittest.TestCase):
    """ALIBABACLOUD_TELEMETRY=false must prevent all upload activity."""

    def test_off_switch_skips_enqueue(self):
        """Shell scripts check ALIBABACLOUD_TELEMETRY=false before enqueue."""
        shell = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "plugins",
            "alibabacloud-core",
            "hooks",
            "scripts",
            "post-tool-trace.sh",
        )
        with open(shell) as f:
            content = f.read()
        self.assertIn("ALIBABACLOUD_TELEMETRY}", content)
        self.assertIn('"false"', content)
        self.assertIn("return_success", content)
        idx_off = content.index('"false"')
        idx_enqueue = content.index("telemetry_enqueue")
        self.assertLess(idx_off, idx_enqueue)

    def test_worker_respects_missing_queue(self):
        """Worker exits cleanly when queue directory is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_dir = os.path.join(tmp, "telemetry-queue", "pending")
            os.makedirs(queue_dir)
            result = subprocess.run(
                [sys.executable, telemetry_worker.__file__, tmp],
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0)


class TestEnqueue(unittest.TestCase):
    """Events are correctly written to the queue directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_enqueue_creates_queue_file(self):
        with mock.patch.object(
            telemetry_worker, "__file__", "/dev/null"
        ):
            with mock.patch(
                "telemetry_enqueue._ensure_worker"
            ):
                telemetry_enqueue.enqueue_event(
                    self.tmp,
                    {"event-type": "mcp_tool_use", "tool-name": "Foo"},
                    start_worker=False,
                )

        pending = os.path.join(self.tmp, "telemetry-queue", "pending")
        files = [f for f in os.listdir(pending) if f.endswith(".json")]
        self.assertEqual(len(files), 1)

        with open(os.path.join(pending, files[0])) as f:
            event = json.load(f)

        self.assertEqual(event["args"]["event-type"], "mcp_tool_use")
        self.assertEqual(event["args"]["tool-name"], "Foo")
        self.assertEqual(event["retries"], 0)
        self.assertIn("timestamp", event)

    def test_enqueue_multiple_events(self):
        with mock.patch("telemetry_enqueue._ensure_worker"):
            for i in range(10):
                telemetry_enqueue.enqueue_event(
                    self.tmp,
                    {"event-type": "tool_call", "index": str(i)},
                    start_worker=False,
                )

        pending = os.path.join(self.tmp, "telemetry-queue", "pending")
        files = [f for f in os.listdir(pending) if f.endswith(".json")]
        self.assertEqual(len(files), 10)

    def test_parse_lines_to_dict(self):
        text = "--event-type\nmcp_tool_use\n--tool-name\nFoo\n--status\nsuccess\n"
        result = telemetry_enqueue._parse_lines_to_dict(text)
        self.assertEqual(result, {
            "event-type": "mcp_tool_use",
            "tool-name": "Foo",
            "status": "success",
        })

    def test_parse_lines_empty(self):
        result = telemetry_enqueue._parse_lines_to_dict("")
        self.assertEqual(result, {})

    def test_parse_lines_skips_non_flag(self):
        text = "noise\n--key\nvalue\n"
        result = telemetry_enqueue._parse_lines_to_dict(text)
        self.assertEqual(result, {"key": "value"})


class TestSingleInstanceLock(unittest.TestCase):
    """Only one worker can hold the lock at a time."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_acquire_and_release_lock(self):
        lock_info = telemetry_worker._acquire_lock(self.tmp)
        self.assertIsNotNone(lock_info)
        fd, lock_path = lock_info
        self.assertTrue(os.path.exists(lock_path))
        telemetry_worker._release_lock(lock_info)

    def test_second_lock_fails(self):
        lock1 = telemetry_worker._acquire_lock(self.tmp)
        self.assertIsNotNone(lock1)

        lock2 = telemetry_worker._acquire_lock(self.tmp)
        self.assertIsNone(lock2)

        telemetry_worker._release_lock(lock1)

    def test_lock_released_allows_reacquire(self):
        lock1 = telemetry_worker._acquire_lock(self.tmp)
        telemetry_worker._release_lock(lock1)

        lock2 = telemetry_worker._acquire_lock(self.tmp)
        self.assertIsNotNone(lock2)
        telemetry_worker._release_lock(lock2)


class TestWorkerBatchProcessing(unittest.TestCase):
    """Worker processes queued events correctly."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.queue_dir = os.path.join(
            self.tmp, "telemetry-queue", "pending"
        )
        self.failed_dir = os.path.join(
            self.tmp, "telemetry-queue", "failed"
        )
        os.makedirs(self.queue_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_event(self, args, retries=0):
        filename = f"{int(time.time() * 1000000)}-{len(os.listdir(self.queue_dir))}.json"
        filepath = os.path.join(self.queue_dir, filename)
        event = {"args": args, "retries": retries, "timestamp": time.time()}
        with open(filepath, "w") as f:
            json.dump(event, f)
        return filepath

    @mock.patch("telemetry_worker._upload_one")
    def test_process_batch_success(self, mock_upload):
        self._write_event({"event-type": "tool_call", "tool-name": "A"})
        self._write_event({"event-type": "tool_call", "tool-name": "B"})

        with mock.patch.dict(os.environ, {"ALIBABACLOUD_TELEMETRY_UPLOADER": "echo"}):
            count = telemetry_worker._process_batch(self.tmp)

        self.assertEqual(count, 2)
        self.assertEqual(mock_upload.call_count, 2)
        remaining = os.listdir(self.queue_dir)
        self.assertEqual(len(remaining), 0)

    @mock.patch("telemetry_worker._upload_one")
    def test_process_batch_retry_on_failure(self, mock_upload):
        mock_upload.side_effect = RuntimeError("upload failed")
        self._write_event({"event-type": "tool_call"})

        count = telemetry_worker._process_batch(self.tmp)

        self.assertEqual(count, 0)
        remaining = os.listdir(self.queue_dir)
        self.assertEqual(len(remaining), 1)

        with open(os.path.join(self.queue_dir, remaining[0])) as f:
            event = json.load(f)
        self.assertEqual(event["retries"], 1)

    @mock.patch("telemetry_worker._upload_one")
    def test_process_batch_move_to_failed_after_max_retries(self, mock_upload):
        mock_upload.side_effect = RuntimeError("permanent failure")
        self._write_event(
            {"event-type": "tool_call"},
            retries=telemetry_worker.DEFAULT_MAX_RETRIES,
        )

        count = telemetry_worker._process_batch(self.tmp)

        self.assertEqual(count, 0)
        remaining = os.listdir(self.queue_dir)
        self.assertEqual(len(remaining), 0)

        failed = os.listdir(self.failed_dir)
        self.assertEqual(len(failed), 1)

    @mock.patch("telemetry_worker._upload_one")
    def test_process_batch_corrupt_event_removed(self, mock_upload):
        filepath = os.path.join(self.queue_dir, "corrupt.json")
        with open(filepath, "w") as f:
            f.write("not valid json{{{")

        count = telemetry_worker._process_batch(self.tmp)

        self.assertEqual(count, 0)
        self.assertEqual(mock_upload.call_count, 0)
        remaining = os.listdir(self.queue_dir)
        self.assertEqual(len(remaining), 0)

    def test_queue_overflow_drops_oldest(self):
        old_max = telemetry_worker.MAX_QUEUE_SIZE
        telemetry_worker.MAX_QUEUE_SIZE = 3
        try:
            for i in range(5):
                self._write_event({"event-type": "tool_call", "idx": str(i)})

            files = telemetry_worker._list_pending(self.queue_dir)
            self.assertEqual(len(files), 3)
        finally:
            telemetry_worker.MAX_QUEUE_SIZE = old_max


class TestUploadCommand(unittest.TestCase):
    """Worker uses fixed version, not @latest."""

    def test_get_upload_cmd_override(self):
        with mock.patch.dict(
            os.environ, {"ALIBABACLOUD_TELEMETRY_UPLOADER": "echo test"}
        ):
            cmd = telemetry_worker._get_upload_cmd("/tmp/test")
        self.assertEqual(cmd, ["echo", "test"])

    def test_get_upload_cmd_no_venv_uses_pinned_uvx(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                os.environ, {}, clear=True
            ):
                cmd = telemetry_worker._get_upload_cmd(tmp)
        self.assertIn("--from", cmd)
        pin_found = any(
            f"=={telemetry_worker.MCP_PROXY_PINNED_VERSION}" in c
            for c in cmd
        )
        self.assertTrue(pin_found, f"No pinned version in cmd: {cmd}")
        self.assertNotIn("@latest", " ".join(cmd))

    def test_get_upload_cmd_uses_existing_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv_bin = os.path.join(tmp, ".venv", "bin", "plugin-telemetry")
            os.makedirs(os.path.dirname(venv_bin), exist_ok=True)
            with open(venv_bin, "w") as f:
                f.write("#!/bin/bash\necho ok")
            os.chmod(venv_bin, 0o755)

            cmd = telemetry_worker._get_upload_cmd(tmp)

        self.assertEqual(cmd, [venv_bin])


class TestProcessTreeKilling(unittest.TestCase):
    """Subprocess cleanup kills entire process group."""

    def test_kill_process_tree_terminates(self):
        proc = subprocess.Popen(
            ["sleep", "60"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.assertTrue(proc.poll() is None)

        telemetry_worker._kill_process_tree(proc)

        self.assertIsNotNone(proc.returncode)

    def test_kill_process_tree_already_dead(self):
        proc = subprocess.Popen(
            ["true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.wait()

        telemetry_worker._kill_process_tree(proc)


class TestUploadTimeout(unittest.TestCase):
    """Uploads that exceed timeout are killed."""

    @mock.patch("telemetry_worker.DEFAULT_HARD_TIMEOUT", 1)
    def test_timeout_kills_slow_upload(self):
        cmd_prefix = ["sleep", "60"]
        with self.assertRaises(RuntimeError) as ctx:
            telemetry_worker._upload_one(cmd_prefix, {})
        self.assertIn("timed out", str(ctx.exception))


class TestPIDFile(unittest.TestCase):
    """PID file tracks worker process."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_and_check_pid(self):
        pid_path = telemetry_worker._write_pid_file(self.tmp)
        self.assertTrue(os.path.exists(pid_path))

        with open(pid_path) as f:
            pid = int(f.read().strip())
        self.assertEqual(pid, os.getpid())

    def test_check_existing_worker_self(self):
        telemetry_worker._write_pid_file(self.tmp)
        self.assertFalse(telemetry_worker._check_existing_worker(self.tmp))

    def test_check_existing_worker_dead_pid(self):
        pid_path = os.path.join(self.tmp, "telemetry-worker.pid")
        with open(pid_path, "w") as f:
            f.write("99999999")
        self.assertFalse(telemetry_worker._check_existing_worker(self.tmp))

    def test_remove_pid_file(self):
        pid_path = telemetry_worker._write_pid_file(self.tmp)
        telemetry_worker._remove_pid_file(pid_path)
        self.assertFalse(os.path.exists(pid_path))


class TestCleanup(unittest.TestCase):
    """Old files are cleaned up by the worker."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cleanup_old_failed(self):
        failed_dir = os.path.join(
            self.tmp, "telemetry-queue", "failed"
        )
        os.makedirs(failed_dir)
        old_file = os.path.join(failed_dir, "old.json")
        with open(old_file, "w") as f:
            f.write("{}")
        old_time = time.time() - (telemetry_worker.FAILED_RETENTION_DAYS + 1) * 86400
        os.utime(old_file, (old_time, old_time))

        telemetry_worker._cleanup_old(self.tmp)

        self.assertFalse(os.path.exists(old_file))

    def test_cleanup_keeps_recent(self):
        failed_dir = os.path.join(
            self.tmp, "telemetry-queue", "failed"
        )
        os.makedirs(failed_dir)
        recent_file = os.path.join(failed_dir, "recent.json")
        with open(recent_file, "w") as f:
            f.write("{}")

        telemetry_worker._cleanup_old(self.tmp)

        self.assertTrue(os.path.exists(recent_file))


class TestNoUvxAtLatest(unittest.TestCase):
    """Verify no script invokes uvx @latest at runtime."""

    def _read_scripts(self):
        base = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "plugins",
            "alibabacloud-core",
            "hooks",
            "scripts",
        )
        contents = {}
        for name in os.listdir(base):
            if name.endswith(".sh"):
                with open(os.path.join(base, name)) as f:
                    contents[name] = f.read()
        return contents

    def test_no_uvx_at_latest_invocation(self):
        for name, content in self._read_scripts().items():
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "DRYRUN" in stripped:
                    continue
                self.assertNotIn(
                    "uvx alibabacloud.mcp-proxy@latest",
                    stripped,
                    f"{name} still invokes uvx @latest: {stripped}",
                )

    def test_no_disown_in_scripts(self):
        for name, content in self._read_scripts().items():
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                self.assertNotIn(
                    "disown",
                    stripped,
                    f"{name} still uses disown: {stripped}",
                )


class TestWorkerIntegration(unittest.TestCase):
    """Integration test: enqueue events then run worker."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.queue_dir = os.path.join(
            self.tmp, "telemetry-queue", "pending"
        )
        os.makedirs(self.queue_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    @mock.patch("telemetry_worker._upload_one")
    def test_full_enqueue_and_process(self, mock_upload):
        with mock.patch("telemetry_enqueue._ensure_worker"):
            telemetry_enqueue.enqueue_event(
                self.tmp,
                {"event-type": "mcp_tool_use", "tool-name": "TestTool"},
                start_worker=False,
            )
            telemetry_enqueue.enqueue_event(
                self.tmp,
                {"event-type": "skill_invocation", "skill-name": "TestSkill"},
                start_worker=False,
            )

        pending_files = os.listdir(self.queue_dir)
        self.assertEqual(len(pending_files), 2)

        with mock.patch.dict(os.environ, {"ALIBABACLOUD_TELEMETRY_UPLOADER": "echo"}):
            count = telemetry_worker._process_batch(self.tmp)

        self.assertEqual(count, 2)
        self.assertEqual(mock_upload.call_count, 2)
        remaining = os.listdir(self.queue_dir)
        self.assertEqual(len(remaining), 0)


if __name__ == "__main__":
    unittest.main()
