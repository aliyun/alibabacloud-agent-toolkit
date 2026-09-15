#!/usr/bin/env python3
"""Regression tests for shared telemetry tool-call normalization."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "plugins/alibabacloud-core/hooks/scripts/lib"
NORMALIZATION_PATH = LIB_DIR / "tool_normalization.py"
sys.path.insert(0, str(LIB_DIR))

import post_handler
import pre_handler


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


if __name__ == "__main__":
    unittest.main()
