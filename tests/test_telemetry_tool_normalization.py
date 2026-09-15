#!/usr/bin/env python3
"""Regression tests for shared telemetry tool-call normalization."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "plugins/alibabacloud-core/hooks/scripts/lib"
NORMALIZATION_PATH = LIB_DIR / "tool_normalization.py"
sys.path.insert(0, str(LIB_DIR))

import post_handler
import pre_handler
import prompt_handler
import sanitize
from state import SessionState


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
        for action in ("CallCLI", "runiac", "RuNsCrIpT"):
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

    def test_unwraps_private_client_wrapper_for_alibabacloud_skill_file_bash(self) -> None:
        tool_input = {
            "toolName": "Bash",
            "arguments": {
                "command": (
                    "sed -n '1,20p' "
                    "/tmp/plugins/alibabacloud-core/skills/example/SKILL.md"
                )
            },
        }
        normalized = self.normalization.normalize_tool_call(
            "private_client_tool_proxy", tool_input
        )
        self.assertEqual(("Bash", tool_input["arguments"]), normalized)
        self.assertTrue(pre_handler.is_ours_tool(*normalized))

    def test_does_not_unwrap_unknown_private_wrapper_for_agent(self) -> None:
        tool_input = {
            "toolName": "Agent",
            "arguments": {"subagent_type": "alibabacloud-spec-ops:planner"},
        }
        self.assertEqual(
            ("private_client_tool_proxy", tool_input),
            self.normalization.normalize_tool_call(
                "private_client_tool_proxy", tool_input
            ),
        )

    def test_does_not_unwrap_unknown_private_wrapper_for_aliyun_bash(self) -> None:
        tool_input = {
            "toolName": "Bash",
            "arguments": {"command": "aliyun ecs DescribeInstances"},
        }
        self.assertEqual(
            ("private_client_tool_proxy", tool_input),
            self.normalization.normalize_tool_call(
                "private_client_tool_proxy", tool_input
            ),
        )

    def test_does_not_unwrap_unknown_private_wrapper_for_other_owned_mcp_actions(self) -> None:
        for action in ("GetApiDefinition", "DeleteEverything", "RuNsCrIp"):
            with self.subTest(action=action):
                tool_input = {
                    "toolName": (
                        "mcp__alibabacloud-core__AlibabaCloud___" + action
                    ),
                    "arguments": {"query": "example"},
                }
                self.assertEqual(
                    ("private_client_tool_proxy", tool_input),
                    self.normalization.normalize_tool_call(
                        "private_client_tool_proxy", tool_input
                    ),
                )

    def test_does_not_unwrap_private_wrapper_for_unrelated_inner_tool(self) -> None:
        for inner_name in (
            "mcp__other-cloud__DeleteEverything",
            "mcp__third-party-docs__SearchAlibabaCloudDocs",
            "mcp__third-party__notalibabacloud",
            "mcp__third-party__AlibabaCloud_SearchDocs",
            "mcp__third-party__AlibabaCloud___SearchDocs",
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

    def test_does_not_unwrap_identifier_prefix_collisions(self) -> None:
        cases = (
            ("Skill", {"skill": "alibabaclouding-core:example"}),
            ("Agent", {"subagent_type": "alibabaclouding-spec-ops:planner"}),
        )
        for inner_name, arguments in cases:
            with self.subTest(inner_name=inner_name):
                outer = {
                    "toolName": inner_name,
                    "arguments": arguments,
                }
                self.assertEqual(
                    ("private_client_tool_proxy", outer),
                    self.normalization.normalize_tool_call(
                        "private_client_tool_proxy", outer
                    ),
                )
                seed, _, _ = post_handler.classify_with_reason(
                    inner_name, arguments
                )
                self.assertIsNone(seed)

    def test_does_not_unwrap_skill_path_segment_collisions(self) -> None:
        for plugin_segment in (
            "notalibabacloud",
            "search-alibabacloud-docs",
        ):
            with self.subTest(plugin_segment=plugin_segment):
                arguments = {
                    "file_path": (
                        f"/tmp/plugins/{plugin_segment}/skills/example/SKILL.md"
                    )
                }
                outer = {"toolName": "Read", "arguments": arguments}
                self.assertEqual(
                    ("private_client_tool_proxy", outer),
                    self.normalization.normalize_tool_call(
                        "private_client_tool_proxy", outer
                    ),
                )
                seed, _, _ = post_handler.classify_with_reason(
                    "Read", arguments
                )
                self.assertIsNone(seed)
                command = f"sed -n '1p' {arguments['file_path']}"
                self.assertFalse(
                    pre_handler.is_ours_tool("Bash", {"command": command})
                )

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

    def test_mixed_case_callcli_uses_cli_credential_sanitizer(self) -> None:
        flags = (
            "--access-key-id",
            "--access-key-secret",
            "--accesskeyid",
            "--accesskeysecret",
            "--secret",
            "--secret-key",
            "--password",
            "--passwd",
            "--sts-token",
            "--security-token",
        )
        tool_names = (
            "mcp__alibabacloud-core__alibabacloud___callcli",
            "mcp__AlibabaCloud-Core__AlibabaCloud_CaLlClI",
        )
        for tool_name in tool_names:
            for flag in flags:
                with self.subTest(tool_name=tool_name, flag=flag):
                    secret = "reviewersecretvalue"
                    seed, reason, _ = post_handler.classify_with_reason(
                        tool_name,
                        {
                            "command": (
                                "aliyun ecs DescribeInstances "
                                f"{flag} {secret}"
                            )
                        },
                    )
                    self.assertIsNone(reason)
                    self.assertNotIn(secret, seed["cli_command"])
                    self.assertEqual(seed["mcp_tool"], "AlibabaCloud___CallCLI")
                    self.assertTrue(
                        post_handler._is_callcli_mcp_tool(seed["mcp_tool"])
                    )

    def test_callcli_suffix_collisions_use_generic_sensitive_input_sanitizer(self) -> None:
        sensitive_values = (
            "Bearer reviewer-token-value",
            "-----BEGIN PRIVATE KEY-----reviewer-key-----END PRIVATE KEY-----",
            "A" * 64,
        )
        for action in ("NotCallCLI", "RecallCLI", "CallCLIExtra"):
            for sensitive in sensitive_values:
                with self.subTest(action=action, sensitive=sensitive[:12]):
                    seed, reason, _ = post_handler.classify_with_reason(
                        (
                            "mcp__alibabacloud-core__AlibabaCloud___"
                            + action
                        ),
                        {"command": sensitive},
                    )
                    self.assertIsNone(reason)
                    self.assertFalse(
                        post_handler._is_callcli_mcp_tool(seed["mcp_tool"])
                    )
                    self.assertNotIn(sensitive, seed["cli_command"])

    def test_slash_skill_rejects_identifier_prefix_collision(self) -> None:
        self.assertIsNone(
            prompt_handler._classify_prompt(
                "/alibabaclouding-core:foreign-skill do something"
            )
        )

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

    def test_aliyun_sanitizer_redacts_quoted_multiword_credentials(self) -> None:
        secrets = ("reviewerHorse", "reviewerBattery", "reviewerStaple")
        cases = (
            (
                "aliyun ecs DescribeInstances --password   "
                '"reviewerHorse reviewerBattery reviewerStaple"'
            ),
            (
                "aliyun ecs DescribeInstances --access-key-secret "
                "'reviewerHorse reviewerBattery reviewerStaple'"
            ),
            (
                "aliyun ecs DescribeInstances "
                '--password="reviewerHorse reviewerBattery reviewerStaple"'
            ),
            (
                'AK="reviewerHorse reviewerBattery reviewerStaple" '
                "aliyun ecs DescribeInstances"
            ),
        )
        for command in cases:
            with self.subTest(command=command):
                sanitized = sanitize.sanitize_aliyun_cli(command)
                for secret in secrets:
                    self.assertNotIn(secret, sanitized)

                seed, reason, _ = post_handler.classify_with_reason(
                    "mcp__alibabacloud-core__AlibabaCloud___CallCLI",
                    {"command": command},
                )
                self.assertIsNone(reason)
                for secret in secrets:
                    self.assertNotIn(secret, seed["cli_command"])

    def test_aliyun_sanitizer_fails_closed_on_unclosed_quote(self) -> None:
        command = 'aliyun ecs DescribeInstances --password "reviewerSecret'
        self.assertEqual("", sanitize.sanitize_aliyun_cli(command))

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


class TelemetryRegressionTests(unittest.TestCase):
    def test_string_mcp_error_response_is_reported_as_failure(self) -> None:
        status, error_class = post_handler.detect_status({
            "tool_response": json.dumps({
                "code": -32603,
                "message": "Call mcp tools error",
                "data": {"detail": "CLI Command execution failed"},
            })
        })

        self.assertEqual("failure", status)
        self.assertEqual("MCPError:-32603", error_class)

    def test_string_mcp_success_response_remains_success(self) -> None:
        status, error_class = post_handler.detect_status({
            "tool_response": json.dumps({
                "code": 0,
                "data": {"requestId": "test-request-id"},
            })
        })

        self.assertEqual("success", status)
        self.assertEqual("", error_class)

    def test_first_tracked_tool_synthesizes_missing_prompt_span(self) -> None:
        payload = {
            "session_id": "new-qoder-without-prompt-hook",
            "tool_use_id": "tool-use-1",
            "tool_name": "mcp_call",
            "tool_input": {
                "toolName": (
                    "mcp__plugin_alibabacloud-core_alibabacloud-core__"
                    "AlibabaCloud_CallCLI"
                ),
                "arguments": {"command": "aliyun ecs DescribeRegions"},
            },
        }
        fake_stdin = mock.Mock()
        fake_stdin.buffer = io.BytesIO(json.dumps(payload).encode())

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {
                "ALIBABACLOUD_TELEMETRY_STATE_DIR": tmp,
                "ALIBABACLOUD_TRACE": "false",
                "QODER_PRODUCT_ID": "qoder",
            },
            clear=True,
        ), mock.patch.object(pre_handler.sys, "stdin", fake_stdin):
            self.assertEqual(0, pre_handler.main())
            with SessionState("qoder", payload["session_id"]) as st:
                self.assertTrue(st.data.get("turn_has_trace"))
                self.assertTrue(st.data.get("prompt_span_id"))
                self.assertIsInstance(st.data.get("pending_prompt_ts"), int)
                self.assertEqual(
                    st.data["prompt_span_id"],
                    st.data["turn_spans"][0]["parent_span_id"],
                )

    def test_slash_skill_keeps_remote_turn_state_when_local_trace_is_off(self) -> None:
        payload = {
            "session_id": "slash-skill-with-local-trace-off",
            "prompt": "/alibabacloud-core:mcp-core-best-practices help",
        }
        fake_stdin = mock.Mock()
        fake_stdin.buffer = io.BytesIO(json.dumps(payload).encode())

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {
                "ALIBABACLOUD_TELEMETRY_STATE_DIR": tmp,
                "ALIBABACLOUD_TRACE": "false",
            },
            clear=True,
        ), mock.patch.object(
            prompt_handler.sys, "stdin", fake_stdin
        ), mock.patch.object(prompt_handler.sys, "stdout", io.StringIO()):
            self.assertEqual(0, prompt_handler.main())
            with SessionState("claude-code", payload["session_id"]) as st:
                self.assertTrue(st.data.get("turn_has_trace"))
                self.assertTrue(st.data.get("prompt_span_id"))
                self.assertIsInstance(st.data.get("pending_prompt_ts"), int)
                self.assertNotIn("pending_prompt", st.data)


if __name__ == "__main__":
    unittest.main()
