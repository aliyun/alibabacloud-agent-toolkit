#!/usr/bin/env python3
"""Regression tests for shared telemetry tool-call normalization."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "plugins/alibabacloud-core/hooks/scripts/lib"
NORMALIZATION_PATH = LIB_DIR / "tool_normalization.py"
sys.path.insert(0, str(LIB_DIR))

import post_handler
import pre_handler
import sanitize


def load_normalization(testcase: unittest.TestCase):
    if not NORMALIZATION_PATH.is_file():
        testcase.fail(f"missing shared normalizer: {NORMALIZATION_PATH}")
    spec = importlib.util.spec_from_file_location(
        "tool_normalization_under_test", NORMALIZATION_PATH
    )
    testcase.assertIsNotNone(spec)
    testcase.assertIsNotNone(spec.loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ToolNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.normalization = load_normalization(self)

    def assert_unchanged(self, command: str) -> None:
        tool_input = {"command": command}
        self.assertEqual(
            ("Bash", tool_input),
            self.normalization.normalize_tool_call("Bash", tool_input),
        )

    def test_normalizes_mcpx_callcli_json_argument(self) -> None:
        command = (
            "cd /tmp/plugin && uv run --python 3.11 scripts/mcpx.py "
            "call CallCLI '{\"command\":\"aliyun ecs DescribeInstances "
            "--RegionId cn-hangzhou\"}' 2>&1 | tail -30"
        )
        self.assertEqual(
            (
                "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
                {
                    "command": (
                        "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
                    )
                },
            ),
            self.normalization.normalize_tool_call("Bash", {"command": command}),
        )

    def test_normalizes_options_before_call(self) -> None:
        command = (
            "uv run scripts/mcpx.py --timeout 420 call CallCLI "
            "'{\"command\":\"aliyun sls list-project --region cn-shanghai\"}'"
        )
        normalized = self.normalization.normalize_tool_call(
            "Bash", {"command": command}
        )
        self.assertEqual(
            "mcp__alibabacloud-core__AlibabaCloud___CallCLI", normalized[0]
        )
        self.assertEqual(
            "aliyun sls list-project --region cn-shanghai",
            normalized[1]["command"],
        )

    def test_normalizes_supported_python_launchers(self) -> None:
        payload = "'{\"command\":\"aliyun ecs DescribeInstances\"}'"
        for launcher in ("python3 -u", "/usr/bin/env python3"):
            with self.subTest(launcher=launcher):
                normalized = self.normalization.normalize_tool_call(
                    "Bash",
                    {
                        "command": (
                            f"{launcher} scripts/mcpx.py call CallCLI {payload}"
                        )
                    },
                )
                self.assertEqual(
                    "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
                    normalized[0],
                )

    def test_normalizes_multiline_shell_invocation(self) -> None:
        suffix = (
            "uv run scripts/mcpx.py call CallCLI "
            "'{\"command\":\"aliyun ecs DescribeInstances\"}'"
        )
        for prefix in ("cd /tmp\n", "cd /tmp\n\n", "cd /tmp;\n", "cd /tmp # comment\n"):
            with self.subTest(prefix=prefix):
                normalized = self.normalization.normalize_tool_call(
                    "Bash", {"command": prefix + suffix}
                )
                self.assertEqual(
                    "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
                    normalized[0],
                )
                self.assertEqual(
                    "aliyun ecs DescribeInstances", normalized[1]["command"]
                )

    def test_normalizes_json_piped_to_stdin(self) -> None:
        command = (
            "echo '{\"command\":\"aliyun oss ListBuckets "
            "--region cn-beijing\"}' | uv run scripts/mcpx.py call CallCLI -"
        )
        normalized = self.normalization.normalize_tool_call(
            "Bash", {"command": command}
        )
        self.assertEqual(
            "mcp__alibabacloud-core__AlibabaCloud___CallCLI", normalized[0]
        )
        self.assertEqual(
            "aliyun oss ListBuckets --region cn-beijing",
            normalized[1]["command"],
        )

    def test_preserves_qoder_mcp_wrapper_behavior(self) -> None:
        tool_input = {
            "toolName": "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
            "arguments": {"command": "aliyun ecs DescribeRegions"},
        }
        self.assertEqual(
            (
                "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
                {"command": "aliyun ecs DescribeRegions"},
            ),
            self.normalization.normalize_tool_call("qw_mcp_call", tool_input),
        )

    def test_rejects_text_that_only_mentions_required_words(self) -> None:
        for command in (
            "echo mcpx.py call CallCLI aliyun",
            "python scripts/mcpx.py schema CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "python scripts/not-mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "python scripts/mcpx.py call CallCLI '{not-json}'",
            "python scripts/mcpx.py call CallCLI '{\"command\":\"echo aliyun ecs DescribeInstances\"}'",
            "python scripts/mcpx.py doctor && echo call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "echo ok # scripts/mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "uv run scripts/mcpx.py call CallCLI - | echo '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "uv run scripts/mcpx.py '{\"command\":\"aliyun ecs DescribeInstances\"}' call CallCLI",
            "echo scripts/mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "cat <<'EOF'\nscripts/mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'\nEOF",
            "python scripts/mcpx.py schema call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "scripts/mcpx.py unrelated call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "scripts/mcpx.py call CallCLI unrelated '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "python -h scripts/mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "python -V scripts/mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
            "python -W scripts/mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
        ):
            with self.subTest(command=command):
                self.assert_unchanged(command)

    def test_non_string_bash_command_is_unchanged(self) -> None:
        tool_input = {"command": ["scripts/mcpx.py", "call", "CallCLI"]}
        self.assertEqual(
            ("Bash", tool_input),
            self.normalization.normalize_tool_call("Bash", tool_input),
        )

    def test_pre_and_post_use_same_normalized_shape(self) -> None:
        outer = {
            "command": (
                "uv run scripts/mcpx.py call CallCLI "
                "'{\"command\":\"aliyun ecs DescribeInstances "
                "--access-key-secret not-a-real-secret --RegionId cn-hangzhou\"}'"
            )
        }
        pre_name, pre_input = pre_handler.normalize_tool_call("Bash", outer)
        post_name, post_input = post_handler.normalize_tool_call("Bash", outer)
        self.assertEqual((pre_name, pre_input), (post_name, post_input))
        self.assertTrue(pre_handler.is_ours_tool(pre_name, pre_input))

        seed, reason, _ = post_handler.classify_with_reason(post_name, post_input)
        self.assertIsNone(reason)
        self.assertEqual("mcp_tool_use", seed["event_type"])
        self.assertEqual("AlibabaCloud___CallCLI", seed["mcp_tool"])
        self.assertEqual("alibabacloud-core", seed.get("plugin_name"))
        self.assertEqual(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            seed["cli_command"],
        )

    def test_wrapped_callcli_redacts_credential_environment_variables(self) -> None:
        for variable in (
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            "ALIBABA_CLOUD_SECURITY_TOKEN",
            "AK",
            "SK",
            "PK",
            "KEY",
        ):
            secret = "plainsecretvalue"
            command = (
                "uv run scripts/mcpx.py call CallCLI "
                f"'{{\"command\":\"{variable}={secret} aliyun ecs "
                "DescribeInstances\"}'"
            )
            name, tool_input = post_handler.normalize_tool_call(
                "Bash", {"command": command}
            )
            seed, reason, _ = post_handler.classify_with_reason(name, tool_input)
            self.assertIsNone(reason)
            self.assertNotIn(secret, seed["cli_command"])
            self.assertNotIn(variable, seed["cli_command"])

    def test_direct_aliyun_sanitizer_redacts_credential_environment_variables(self) -> None:
        secret = "plainsecretvalue"
        command = (
            f"ALIBABA_CLOUD_ACCESS_KEY_SECRET={secret} "
            "aliyun ecs DescribeInstances"
        )
        sanitized = sanitize.sanitize_aliyun_cli(command)
        self.assertNotIn(secret, sanitized)
        self.assertNotIn("ALIBABA_CLOUD_ACCESS_KEY_SECRET", sanitized)
        self.assertEqual("aliyun ecs DescribeInstances", sanitized)

    def test_compound_aliyun_command_redacts_short_credential_environment(self) -> None:
        secret = "plainsecretvalue"
        for variable in ("AK", "SK", "PK", "KEY"):
            with self.subTest(variable=variable):
                command = (
                    f"{variable}={secret}; aliyun ecs DescribeInstances "
                    f"--access-key-secret \"${variable}\""
                )
                sanitized = sanitize.sanitize_aliyun_cli(command)
                self.assertNotIn(secret, sanitized)
                self.assertNotIn(f"{variable}=", sanitized)

    def test_wrapped_compound_command_redacts_short_credential_environment(self) -> None:
        secret = "plainsecretvalue"
        outer = {
            "command": (
                "uv run scripts/mcpx.py call CallCLI "
                f"'{{\"command\":\"AK={secret}; aliyun ecs DescribeInstances "
                "--access-key-secret \\\"$AK\\\"\"}'"
            )
        }
        name, tool_input = post_handler.normalize_tool_call("Bash", outer)
        seed, reason, _ = post_handler.classify_with_reason(name, tool_input)
        self.assertIsNone(reason)
        self.assertNotIn(secret, seed["cli_command"])
        self.assertNotIn("AK=", seed["cli_command"])

    def test_agent_pid_uses_one_process_snapshot(self) -> None:
        process_table = (
            "100 50 /usr/bin/python3\n"
            "50 20 /Applications/QoderWork\n"
            "20 1 /sbin/launchd\n"
        )
        with (
            mock.patch("os.getpid", return_value=100),
            mock.patch("subprocess.check_output", return_value=process_table) as check,
        ):
            self.assertEqual(50, post_handler._find_agent_pid())
        check.assert_called_once()


if __name__ == "__main__":
    unittest.main()
