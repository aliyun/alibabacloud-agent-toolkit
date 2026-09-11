from __future__ import annotations

import importlib.util
import io
import json
import struct
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate.py")
SPEC = importlib.util.spec_from_file_location("repo_validate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
repo_validate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repo_validate)


def png(width: int = 256, height: int = 256) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"


def jpeg(width: int = 256, height: int = 256) -> bytes:
    sof = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08" + struct.pack(">HH", height, width) + b"\x01\x01\x11\x00"
    return b"\xff\xd8" + sof + b"\xff\xd9"


def webp(width: int = 256, height: int = 256) -> bytes:
    payload = b"VP8X" + struct.pack("<I", 10) + b"\x00\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    return b"RIFF" + struct.pack("<I", len(payload) + 4) + b"WEBP" + payload


def webp_vp8(width: int = 256, height: int = 256) -> bytes:
    frame = b"\x00\x00\x00\x9d\x01\x2a" + struct.pack("<HH", width, height)
    chunk = b"VP8 " + struct.pack("<I", len(frame)) + frame
    return b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk


def webp_vp8l(width: int = 256, height: int = 256) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    frame = b"\x2f" + bits.to_bytes(4, "little")
    chunk = b"VP8L" + struct.pack("<I", len(frame)) + frame
    return b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk


def gif(width: int = 256, height: int = 256) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00"


def bmp(width: int = 256, height: int = 256) -> bytes:
    return b"BM" + b"\x00" * 12 + struct.pack("<Iii", 40, width, height) + b"\x00" * 12


def ico(width: int = 256, height: int = 256) -> bytes:
    encoded_width = 0 if width == 256 else width
    encoded_height = 0 if height == 256 else height
    entry = bytes((encoded_width, encoded_height, 0, 0)) + struct.pack("<HHII", 1, 32, 1, 22)
    return b"\x00\x00\x01\x00\x01\x00" + entry + b"\x00"


class PluginIconValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        repo_validate.errors.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.plugin_dir = Path(self.temp_dir.name) / "example-plugin"
        (self.plugin_dir / "assets").mkdir(parents=True)

    def validate(self) -> list[str]:
        validator = getattr(repo_validate, "validate_plugin_icon", None)
        self.assertIsNotNone(validator, "validate_plugin_icon must be implemented")
        with redirect_stderr(io.StringIO()):
            validator(self.plugin_dir)
        return list(repo_validate.errors)

    def write_icon(self, suffix: str, content: bytes) -> None:
        (self.plugin_dir / "assets" / f"icon{suffix}").write_bytes(content)

    def test_accepts_each_supported_raster_format(self) -> None:
        fixtures = {
            ".png": png(),
            ".jpg": jpeg(),
            ".jpeg": jpeg(),
            ".webp": webp(),
            ".gif": gif(),
            ".bmp": bmp(),
            ".ico": ico(),
        }
        for suffix, content in fixtures.items():
            with self.subTest(suffix=suffix):
                for path in (self.plugin_dir / "assets").iterdir():
                    path.unlink()
                repo_validate.errors.clear()
                self.write_icon(suffix, content)
                self.assertEqual([], self.validate())

    def test_accepts_square_svg(self) -> None:
        self.write_icon(".svg", b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"/>')
        self.assertEqual([], self.validate())

    def test_accepts_webp_bitstream_variants(self) -> None:
        for content in (webp_vp8(), webp_vp8l()):
            with self.subTest(signature=content[12:16]):
                for path in (self.plugin_dir / "assets").iterdir():
                    path.unlink()
                repo_validate.errors.clear()
                self.write_icon(".webp", content)
                self.assertEqual([], self.validate())

    def test_rejects_missing_icon(self) -> None:
        self.assertTrue(any("Missing plugin icon" in error for error in self.validate()))

    def test_rejects_unsupported_icon_extension(self) -> None:
        self.write_icon(".txt", b"not an image")
        errors = self.validate()
        self.assertTrue(any("Unsupported plugin icon extension" in error for error in errors))

    def test_rejects_multiple_supported_icons(self) -> None:
        self.write_icon(".png", png())
        self.write_icon(".gif", gif())
        self.assertTrue(any("Multiple plugin icons" in error for error in self.validate()))

    def test_rejects_empty_icon(self) -> None:
        self.write_icon(".png", b"")
        self.assertTrue(any("empty" in error for error in self.validate()))

    def test_rejects_extension_signature_mismatch(self) -> None:
        self.write_icon(".jpg", png())
        self.assertTrue(any("does not match" in error for error in self.validate()))

    def test_rejects_non_square_raster_icon(self) -> None:
        self.write_icon(".png", png(256, 128))
        self.assertTrue(any("square" in error for error in self.validate()))

    def test_rejects_png_that_is_not_256_pixels(self) -> None:
        self.write_icon(".png", png(512, 512))
        self.assertTrue(any("256x256" in error for error in self.validate()))

    def test_rejects_svg_without_square_dimensions(self) -> None:
        self.write_icon(".svg", b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 128"/>')
        self.assertTrue(any("square" in error for error in self.validate()))

    def test_placeholder_plugin_skips_icon_validation(self) -> None:
        with redirect_stdout(io.StringIO()):
            repo_validate.validate_plugin(self.plugin_dir)
        self.assertEqual([], repo_validate.errors)


class EcsManifestTests(unittest.TestCase):
    def test_manifest_versions_match(self) -> None:
        plugin_dir = repo_validate.REPO_ROOT / "plugins/alibabacloud-ecs-ops"
        paths = tuple(
            plugin_dir / manifest for manifest in repo_validate.PLUGIN_VERSION_MANIFESTS
        )
        versions = {
            json.loads(path.read_text(encoding="utf-8"))["version"]
            for path in paths
        }
        self.assertEqual({"0.0.8"}, versions)

    def test_marketplace_version_matches(self) -> None:
        marketplace = repo_validate.REPO_ROOT / ".claude-plugin/marketplace.json"
        entries = json.loads(marketplace.read_text(encoding="utf-8"))["plugins"]
        entry = next(e for e in entries if e["name"] == "alibabacloud-ecs-ops")
        self.assertEqual("0.0.8", entry["version"])

    def test_qoder_manifest_declares_hooks_and_mcp(self) -> None:
        path = repo_validate.REPO_ROOT / "plugins/alibabacloud-ecs-ops/.qoder-plugin/plugin.json"
        self.assertTrue(path.is_file())
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("alibabacloud-ecs-ops", manifest["name"])
        self.assertEqual("Alibaba Cloud ECS Ops", manifest["displayName"])
        self.assertEqual("./hooks/qoderwork-hooks.json", manifest["hooks"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])

    def test_codex_manifest_has_complete_interface(self) -> None:
        path = repo_validate.REPO_ROOT / "plugins/alibabacloud-ecs-ops/.codex-plugin/plugin.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("interface", manifest)
        interface = manifest["interface"]
        self.assertEqual("Alibaba Cloud ECS Ops", interface["displayName"])
        self.assertEqual("Alibaba Cloud", interface["developerName"])
        self.assertEqual("Cloud", interface["category"])
        self.assertTrue(interface["capabilities"])
        self.assertTrue(interface["defaultPrompt"])


class AgentPluginsManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        repo_validate.errors.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.plugin_dir = Path(self.temp_dir.name) / "example-plugin"
        (self.plugin_dir / "hooks" / "scripts").mkdir(parents=True)
        self.script = self.plugin_dir / "hooks/scripts/trace.sh"
        self.script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    def write(self, relative: str, payload: object) -> Path:
        path = self.plugin_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def errors_from(self, validator: str) -> list[str]:
        repo_validate.errors.clear()
        with redirect_stderr(io.StringIO()):
            getattr(repo_validate, validator)(self.plugin_dir)
        return list(repo_validate.errors)

    def manifest(self, **overrides: object) -> dict:
        base: dict = {
            "$schema": repo_validate.AGENT_PLUGINS_SCHEMA,
            "name": "example-plugin",
            "version": "1.0.0",
            "description": "Example plugin",
            "author": {"name": "Alibaba Cloud"},
        }
        base.update(overrides)
        return base

    def hooks(self, event: str = "PreToolUse", command: str | None = None) -> dict:
        return {
            "hooks": {
                event: [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": command
                                or 'bash "${PLUGIN_ROOT}/hooks/scripts/trace.sh"',
                                "timeout": 3,
                            }
                        ],
                    }
                ]
            }
        }

    def test_accepts_valid_manifest(self) -> None:
        self.write("plugin.json", self.manifest())
        self.assertEqual([], self.errors_from("validate_agent_plugins_manifest"))

    def test_rejects_wrong_schema(self) -> None:
        self.write("plugin.json", self.manifest(**{"$schema": "https://example.test/plugin.json"}))
        self.assertTrue(any("'$schema'" in e for e in self.errors_from("validate_agent_plugins_manifest")))

    def test_rejects_unknown_manifest_key(self) -> None:
        self.write("plugin.json", self.manifest(mcpServers="./.mcp.json"))
        self.assertTrue(any("Unknown key(s)" in e for e in self.errors_from("validate_agent_plugins_manifest")))

    def test_rejects_unknown_author_key(self) -> None:
        self.write("plugin.json", self.manifest(author={"handle": "Alibaba Cloud"}))
        self.assertTrue(any("'author' key" in e for e in self.errors_from("validate_agent_plugins_manifest")))

    def test_rejects_name_directory_mismatch(self) -> None:
        self.write("plugin.json", self.manifest(name="other-plugin"))
        self.assertTrue(any("does not match directory" in e for e in self.errors_from("validate_agent_plugins_manifest")))

    def test_rejects_invalid_name_pattern(self) -> None:
        (Path(self.temp_dir.name) / "Example_Plugin").mkdir()
        self.plugin_dir = Path(self.temp_dir.name) / "Example_Plugin"
        self.write("plugin.json", self.manifest(name="Example_Plugin"))
        self.assertTrue(any("not a valid Agent Plugins name" in e for e in self.errors_from("validate_agent_plugins_manifest")))

    def test_mcp_requires_explicit_type(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"command": "uvx"}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {"example-plugin": {"command": "uvx"}},
        })
        errors = self.errors_from("validate_agent_plugins_mcp")
        self.assertTrue(any("unsupported type 'None'" in e for e in errors))

    def test_mcp_rejects_http_transport(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"url": "https://example.test/mcp"}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {"example-plugin": {"type": "http", "url": "https://example.test/mcp"}},
        })
        errors = self.errors_from("validate_agent_plugins_mcp")
        self.assertTrue(any("unsupported type 'http'" in e for e in errors))

    def test_mcp_rejects_unknown_server_key(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"command": "uvx"}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {"example-plugin": {"type": "stdio", "command": "uvx", "url": "https://example.test"}},
        })
        self.assertTrue(any("unknown key(s) ['url']" in e for e in self.errors_from("validate_agent_plugins_mcp")))

    def test_mcp_rejects_reserved_env(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"command": "uvx"}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {
                "example-plugin": {
                    "type": "stdio",
                    "command": "uvx",
                    "env": {"PLUGIN_ROOT": "/tmp"},
                }
            },
        })
        self.assertTrue(any("reserved env" in e for e in self.errors_from("validate_agent_plugins_mcp")))

    def test_mcp_accepts_stdio_server_declared_in_dot_mcp_json(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"command": "uvx", "args": ["proxy"]}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {"example-plugin": {"type": "stdio", "command": "uvx", "args": ["proxy"]}},
        })
        self.assertEqual([], self.errors_from("validate_agent_plugins_mcp"))

    def test_mcp_detects_server_drift(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"command": "uvx"}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {"renamed": {"type": "stdio", "command": "uvx"}},
        })
        self.assertTrue(any("disagree on servers" in e for e in self.errors_from("validate_agent_plugins_mcp")))

    def test_mcp_detects_field_drift(self) -> None:
        self.write(".mcp.json", {"mcpServers": {"example-plugin": {"command": "uvx", "args": ["a"]}}})
        self.write("mcp.json", {
            "$schema": repo_validate.AGENT_PLUGINS_MCP_SCHEMA,
            "mcpServers": {"example-plugin": {"type": "stdio", "command": "uvx", "args": ["b"]}},
        })
        self.assertTrue(any("differs between mcp.json and .mcp.json" in e for e in self.errors_from("validate_agent_plugins_mcp")))

    def test_mcp_is_skipped_without_dot_mcp_json(self) -> None:
        self.assertEqual([], self.errors_from("validate_agent_plugins_mcp"))

    def test_hooks_accept_supported_event(self) -> None:
        self.write("com.github.copilot/hooks/hooks.json", self.hooks())
        self.assertEqual([], self.errors_from("validate_copilot_hooks"))

    def test_hooks_reject_unsupported_event(self) -> None:
        self.write("com.github.copilot/hooks/hooks.json", self.hooks(event="PostToolUseFailure"))
        self.assertTrue(any("not supported by VS Code" in e for e in self.errors_from("validate_copilot_hooks")))

    def test_hooks_reject_command_without_plugin_root(self) -> None:
        self.write("com.github.copilot/hooks/hooks.json", self.hooks(command="bash hooks/scripts/trace.sh"))
        self.assertTrue(any("must reference ${PLUGIN_ROOT}" in e for e in self.errors_from("validate_copilot_hooks")))

    def test_hooks_reject_missing_script(self) -> None:
        self.script.unlink()
        self.write("com.github.copilot/hooks/hooks.json", self.hooks())
        self.assertTrue(any("missing file" in e for e in self.errors_from("validate_copilot_hooks")))

    def test_missing_copilot_hooks_is_reported(self) -> None:
        self.write("hooks/hooks.json", self.hooks())
        self.assertTrue(any("does not read hooks/hooks.json" in e for e in self.errors_from("validate_copilot_hooks")))

    def test_version_consistency_detects_mismatch(self) -> None:
        self.write("plugin.json", self.manifest(version="1.0.0"))
        self.write(".claude-plugin/plugin.json", {"name": "example-plugin", "version": "1.0.1"})
        self.assertTrue(any("version mismatch" in e for e in self.errors_from("validate_version_consistency")))

    def test_version_consistency_accepts_agreement(self) -> None:
        self.write("plugin.json", self.manifest(version="1.0.0"))
        self.write(".claude-plugin/plugin.json", {"name": "example-plugin", "version": "1.0.0"})
        self.write("openclaw.plugin.json", {"name": "example-plugin", "version": "1.0.0"})
        self.assertEqual([], self.errors_from("validate_version_consistency"))


class RepoVsCodeSurfaceTests(unittest.TestCase):
    plugins = ("alibabacloud-core", "alibabacloud-spec-ops", "alibabacloud-ecs-ops")

    def test_each_plugin_ships_the_vs_code_surface(self) -> None:
        for name in self.plugins:
            with self.subTest(plugin=name):
                plugin_dir = repo_validate.REPO_ROOT / "plugins" / name
                manifest = json.loads((plugin_dir / "plugin.json").read_text(encoding="utf-8"))
                self.assertEqual(repo_validate.AGENT_PLUGINS_SCHEMA, manifest["$schema"])
                self.assertEqual(name, manifest["name"])
                self.assertTrue((plugin_dir / "mcp.json").is_file())
                self.assertTrue((plugin_dir / "com.github.copilot/hooks/hooks.json").is_file())

    def test_repo_passes_validation(self) -> None:
        repo_validate.errors.clear()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            for name in self.plugins:
                repo_validate.validate_plugin(repo_validate.REPO_ROOT / "plugins" / name)
        self.assertEqual([], repo_validate.errors)


if __name__ == "__main__":
    unittest.main()
