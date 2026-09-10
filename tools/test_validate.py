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
        paths = (
            plugin_dir / ".claude-plugin/plugin.json",
            plugin_dir / ".codex-plugin/plugin.json",
            plugin_dir / ".qoder-plugin/plugin.json",
        )
        versions = {
            json.loads(path.read_text(encoding="utf-8"))["version"]
            for path in paths
        }
        self.assertEqual({"0.0.7"}, versions)

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


if __name__ == "__main__":
    unittest.main()
