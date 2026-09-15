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

    def test_normalizes_namespaced_qoderwork_mcp_call_wrapper(self) -> None:
        tool_input = {
            "toolName": (
                "mcp__alibabacloud-core__AlibabaCloud___GetApiDefinition"
            ),
            "arguments": {"product": "Ecs", "apiName": "DescribeInstances"},
            "timeout": 120,
        }
        normalized = self.normalization.normalize_tool_call(
            "mcp__qw-builtin__qw_mcp_call", tool_input
        )
        self.assertEqual(
            (
                tool_input["toolName"],
                tool_input["arguments"],
            ),
            normalized,
        )
        self.assertTrue(pre_handler.is_ours_tool(*normalized))
        seed, reason, _ = post_handler.classify_with_reason(*normalized)
        self.assertIsNone(reason)
        self.assertEqual("mcp_tool_use", seed["event_type"])
        self.assertEqual("AlibabaCloud___GetApiDefinition", seed["mcp_tool"])
        self.assertEqual("alibabacloud-core", seed["plugin_name"])

    def test_does_not_unwrap_namespaced_qoderwork_metadata_lookup(self) -> None:
        tool_input = {
            "toolName": (
                "mcp__alibabacloud-core__AlibabaCloud___GetApiDefinition"
            ),
            "arguments": {},
        }
        self.assertEqual(
            ("mcp__qw-builtin__qw_mcp_get", tool_input),
            self.normalization.normalize_tool_call(
                "mcp__qw-builtin__qw_mcp_get", tool_input
            ),
        )

    def test_does_not_unwrap_plain_qoderwork_metadata_lookup(self) -> None:
        tool_input = {
            "toolName": (
                "mcp__alibabacloud-core__AlibabaCloud___GetApiDefinition"
            ),
            "arguments": {},
        }
        self.assertEqual(
            ("qw_mcp_get", tool_input),
            self.normalization.normalize_tool_call("qw_mcp_get", tool_input),
        )

    def test_unwraps_private_client_prefix_when_inner_mcp_tool_is_ours(self) -> None:
        for action in ("CallCLI", "RunIaC", "RunScript"):
            with self.subTest(action=action):
                tool_input = {
                    "toolName": (
                        "mcp__alibabacloud-core__AlibabaCloud___" + action
                    ),
                    "arguments": {"action": "plan"},
                }
                self.assertEqual(
                    (tool_input["toolName"], tool_input["arguments"]),
                    self.normalization.normalize_tool_call(
                        "mcp__client-private-v42__qw_mcp_call", tool_input
                    ),
                )

    def test_unwraps_private_client_wrapper_for_alibabacloud_skill(self) -> None:
        tool_input = {
            "toolName": "Skill",
            "arguments": {"skill": "alibabacloud-core:mcp-core-best-practices"},
        }
        normalized = self.normalization.normalize_tool_call(
            "private_client_tool_proxy", tool_input
        )
        self.assertEqual(("Skill", tool_input["arguments"]), normalized)
        self.assertTrue(pre_handler.is_ours_tool(*normalized))

    def test_unwraps_private_client_wrapper_for_alibabacloud_skill_file(self) -> None:
        tool_input = {
            "toolName": "Read",
            "arguments": {
                "file_path": (
                    "/tmp/plugins/alibabacloud-core/skills/example/SKILL.md"
                )
            },
        }
        normalized = self.normalization.normalize_tool_call(
            "private_client_tool_proxy", tool_input
        )
        self.assertEqual(("Read", tool_input["arguments"]), normalized)
        seed, reason, _ = post_handler.classify_with_reason(*normalized)
        self.assertIsNone(reason)
        self.assertEqual("skill_invocation", seed["event_type"])

    def test_unwraps_private_client_wrapper_for_alibabacloud_agent(self) -> None:
        tool_input = {
            "toolName": "Agent",
            "arguments": {"subagent_type": "alibabacloud-spec-ops:planner"},
        }
        normalized = self.normalization.normalize_tool_call(
            "private_client_tool_proxy", tool_input
        )
        seed, reason, _ = post_handler.classify_with_reason(*normalized)
        self.assertIsNone(reason)
        self.assertEqual("subagent_dispatch", seed["event_type"])

    def test_unwraps_private_client_wrapper_for_aliyun_bash(self) -> None:
        tool_input = {
            "toolName": "Bash",
            "arguments": {"command": "aliyun ecs DescribeInstances"},
        }
        normalized = self.normalization.normalize_tool_call(
            "private_client_tool_proxy", tool_input
        )
        seed, reason, _ = post_handler.classify_with_reason(*normalized)
        self.assertIsNone(reason)
        self.assertEqual("cli_command_use", seed["event_type"])

    def test_does_not_unwrap_private_wrapper_for_unrelated_inner_tool(self) -> None:
        for inner_name in (
            "mcp__other-cloud__DeleteEverything",
            "mcp__third-party-docs__SearchAlibabaCloudDocs",
            "mcp__third-party__notalibabacloud",
        ):
            with self.subTest(inner_name=inner_name):
                tool_input = {
                    "toolName": inner_name,
                    "arguments": {"query": "internal-project-customer-42"},
                }
                self.assertEqual(
                    ("private_client_tool_proxy", tool_input),
                    self.normalization.normalize_tool_call(
                        "private_client_tool_proxy", tool_input
                    ),
                )
                self.assertFalse(pre_handler.is_ours_tool(inner_name, {}))
                seed, reason, _ = post_handler.classify_with_reason(
                    inner_name, tool_input["arguments"]
                )
                self.assertIsNone(seed)
                self.assertEqual("unknown-tool", reason)

    def test_does_not_double_unwrap_direct_alibabacloud_tool(self) -> None:
        tool_input = {
            "toolName": "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
            "arguments": {"value": "example"},
        }
        tool_name = "mcp__alibabacloud-core__AlibabaCloud___RunScript"
        self.assertEqual(
            (tool_name, tool_input),
            self.normalization.normalize_tool_call(tool_name, tool_input),
        )

    def test_normalizes_new_qoder_mcp_call_wrapper(self) -> None:
        tool_input = {
            "toolName": (
                "mcp__plugin_alibabacloud-core_alibabacloud-core__"
                "AlibabaCloud_CallCLI"
            ),
            "arguments": {
                "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
            },
        }
        normalized = self.normalization.normalize_tool_call(
            "mcp_call", tool_input
        )
        self.assertEqual(
            (
                tool_input["toolName"],
                tool_input["arguments"],
            ),
            normalized,
        )
        seed, reason, _ = post_handler.classify_with_reason(*normalized)
        self.assertIsNone(reason)
        self.assertEqual("mcp_tool_use", seed["event_type"])
        self.assertEqual("AlibabaCloud___CallCLI", seed["mcp_tool"])
        self.assertEqual("alibabacloud-core", seed["plugin_name"])

    def test_does_not_extract_unsupported_separator_widths(self) -> None:
        for separator in ("__", "____"):
            tool_name = (
                "mcp__plugin_alibabacloud-core_alibabacloud-core__"
                f"AlibabaCloud{separator}CallCLI"
            )
            seed, reason, _ = post_handler.classify_with_reason(tool_name, {})
            self.assertIsNone(reason)
            self.assertEqual("mcp_tool_use", seed["event_type"])
            self.assertNotIn("mcp_tool", seed)

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
