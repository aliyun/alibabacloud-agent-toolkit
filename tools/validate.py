#!/usr/bin/env python3
"""Validate manifests, skill frontmatter, and MCP configs.

Stdlib-only. Exit 0 on success, non-zero on failure.

Usage:
    python3 tools/validate.py              # validate everything
    python3 tools/validate.py --plugin X   # validate one plugin
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KEBAB_RE = re.compile(r"^[a-z][a-z0-9]+(-[a-z0-9]+)*$")
ICON_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico"}

# Agent Plugins 1.0 — the format VS Code auto-detects from a root plugin.json.
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_PLUGINS_MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
# Per-transport shape of an Agent Plugins MCP server; every variant is closed.
AGENT_PLUGINS_MCP_SERVERS = {
    "stdio": ({"type", "command", "args", "env", "cwd"}, "command"),
    "streamable-http": ({"type", "url", "headers"}, "url"),
    "sse": ({"type", "url", "headers"}, "url"),
}
# ${PLUGIN_ROOT} / ${PLUGIN_DATA} are injected by the host, not by the plugin.
AGENT_PLUGINS_RESERVED_ENV = {"PLUGIN_ROOT", "PLUGIN_DATA"}
AGENT_PLUGINS_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
AGENT_PLUGINS_MANIFEST_KEYS = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}
AGENT_PLUGINS_AUTHOR_KEYS = {"name", "email", "url"}
PLUGIN_ROOT_TOKEN = "${PLUGIN_ROOT}"
PLUGIN_ROOT_REF_RE = re.compile(r"\$\{PLUGIN_ROOT\}/([^\s\"']+)")
# Hook lifecycle events VS Code dispatches to plugin hooks.
VSCODE_HOOK_EVENTS = {
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PreCompact", "SubagentStart", "SubagentStop", "Stop",
}
# Every per-plugin manifest that carries a version and must stay in agreement.
PLUGIN_VERSION_MANIFESTS = (
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".qoder-plugin/plugin.json",
    "openclaw.plugin.json",
)

errors: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)
    print(f"  ERROR: {msg}", file=sys.stderr)


def rel(path: Path) -> Path:
    """Repo-relative path for messages, tolerating paths outside the repo."""
    return path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path


def validate_json(path: Path, required_keys: list[str]) -> dict | None:
    """Validate a JSON file exists, parses, and has required keys."""
    if not path.exists():
        error(f"Missing file: {rel(path)}")
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        error(f"Invalid JSON in {rel(path)}: {e}")
        return None
    for key in required_keys:
        if key not in data:
            error(f"Missing key '{key}' in {rel(path)}")
    return data


def validate_skill_frontmatter(skill_md: Path) -> None:
    """Validate SKILL.md has valid YAML frontmatter with name and description."""
    text = skill_md.read_text()
    if not text.startswith("---\n"):
        error(f"Missing YAML frontmatter in {skill_md.relative_to(REPO_ROOT)}")
        return

    end = text.find("\n---\n", 4)
    if end == -1:
        error(f"Unterminated frontmatter in {skill_md.relative_to(REPO_ROOT)}")
        return

    frontmatter = text[4:end]
    # Simple key: value parsing (stdlib-only, no yaml import)
    # Handles multi-line YAML values (lines starting with spaces are continuations)
    fm = {}
    current_key = None
    for line in frontmatter.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            value = value.strip().strip('"').strip("'")
            # Handle YAML block scalar indicators (> or |)
            if value in (">", "|", ">-", "|-"):
                value = ""
            fm[key.strip()] = value
            current_key = key.strip()
        elif current_key and line.startswith("  "):
            # Continuation line — append to current key
            fm[current_key] = (fm[current_key] + " " + line.strip()).strip()

    name = fm.get("name")
    desc = fm.get("description")

    if not name:
        error(f"Missing 'name' in frontmatter: {skill_md.relative_to(REPO_ROOT)}")
    elif not KEBAB_RE.match(name):
        error(f"Name '{name}' is not kebab-case in {skill_md.relative_to(REPO_ROOT)}")
    elif len(name) > 64:
        error(f"Name exceeds 64 chars in {skill_md.relative_to(REPO_ROOT)}")
    else:
        expected_dir = skill_md.parent.name
        if name != expected_dir:
            error(f"Name '{name}' does not match directory '{expected_dir}' in {skill_md.relative_to(REPO_ROOT)}")

    if not desc:
        error(f"Missing 'description' in frontmatter: {skill_md.relative_to(REPO_ROOT)}")
    elif len(desc) < 20:
        error(f"Description too short (<20 chars) in {skill_md.relative_to(REPO_ROOT)}")


def validate_marketplace(path: Path, label: str) -> None:
    """Validate a marketplace manifest and check plugin source paths."""
    print(f"Validating {label} marketplace: {path.relative_to(REPO_ROOT)}")
    data = validate_json(path, ["name", "plugins"])
    if data is None:
        return
    for plugin in data.get("plugins", []):
        if "name" not in plugin:
            error(f"Plugin missing 'name' in {path.relative_to(REPO_ROOT)}")
            continue
        # Resolve source path (relative to repo root, not manifest location)
        if isinstance(plugin.get("source"), dict):
            source = plugin["source"].get("path", "")
        else:
            source = plugin.get("source", "")
        if source:
            resolved = (REPO_ROOT / source).resolve()
            if not resolved.is_dir():
                error(f"Plugin source '{source}' does not exist for '{plugin['name']}'")


def _svg_dimension(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(?:px)?\s*", value)
    return float(match.group(1)) if match else None


def _svg_size(data: bytes) -> tuple[float, float]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("invalid SVG XML") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("missing SVG root element")

    view_box = root.get("viewBox")
    if view_box:
        parts = view_box.replace(",", " ").split()
        if len(parts) != 4:
            raise ValueError("invalid SVG viewBox")
        try:
            width, height = float(parts[2]), float(parts[3])
        except ValueError as exc:
            raise ValueError("invalid SVG viewBox") from exc
        if width <= 0 or height <= 0:
            raise ValueError("invalid SVG viewBox")
        return width, height

    width = _svg_dimension(root.get("width"))
    height = _svg_dimension(root.get("height"))
    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("SVG requires a viewBox or numeric width and height")
    return width, height


def _jpeg_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("missing JPEG signature")
    position = 2
    sof_markers = {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        segment_length = struct.unpack_from(">H", data, position)[0]
        if segment_length < 2 or position + segment_length > len(data):
            break
        if marker in sof_markers and segment_length >= 7:
            height, width = struct.unpack_from(">HH", data, position + 3)
            return width, height
        position += segment_length
    raise ValueError("missing JPEG dimensions")


def _webp_size(data: bytes) -> tuple[int, int]:
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("missing WebP signature")
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError("unsupported WebP header")


def _raster_size(extension: str, data: bytes) -> tuple[int, int]:
    if extension == ".png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError("missing PNG signature or IHDR")
        return struct.unpack_from(">II", data, 16)
    if extension in {".jpg", ".jpeg"}:
        return _jpeg_size(data)
    if extension == ".webp":
        return _webp_size(data)
    if extension == ".gif":
        if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
            raise ValueError("missing GIF signature")
        return struct.unpack_from("<HH", data, 6)
    if extension == ".bmp":
        if len(data) < 26 or data[:2] != b"BM":
            raise ValueError("missing BMP signature")
        width, height = struct.unpack_from("<ii", data, 18)
        return abs(width), abs(height)
    if extension == ".ico":
        if len(data) < 22 or data[:4] != b"\x00\x00\x01\x00":
            raise ValueError("missing ICO signature")
        count = struct.unpack_from("<H", data, 4)[0]
        if count < 1:
            raise ValueError("ICO contains no images")
        width = data[6] or 256
        height = data[7] or 256
        return width, height
    raise ValueError("unsupported raster format")


def validate_plugin_icon(plugin_dir: Path) -> None:
    """Validate the convention-discovered assets/icon.* for a real plugin."""
    assets_dir = plugin_dir / "assets"
    candidates = sorted(assets_dir.glob("icon.*")) if assets_dir.is_dir() else []
    unsupported = [path for path in candidates if path.suffix not in ICON_EXTENSIONS]
    for path in unsupported:
        error(
            f"Unsupported plugin icon extension '{path.suffix}' in "
            f"{path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
        )

    supported = [
        path for path in candidates
        if path.suffix in ICON_EXTENSIONS and path.is_file()
    ]
    if not supported:
        error(f"Missing plugin icon: {plugin_dir.name}/assets/icon.*")
        return
    if len(supported) > 1:
        error(f"Multiple plugin icons found in {plugin_dir.name}/assets")
        return

    icon_path = supported[0]
    try:
        data = icon_path.read_bytes()
    except OSError as exc:
        error(f"Unable to read plugin icon {icon_path}: {exc}")
        return
    if not data:
        error(f"Plugin icon is empty: {icon_path}")
        return

    try:
        if icon_path.suffix == ".svg":
            width, height = _svg_size(data)
        else:
            width, height = _raster_size(icon_path.suffix, data)
    except ValueError as exc:
        error(f"Plugin icon content does not match {icon_path.suffix}: {icon_path} ({exc})")
        return

    if width != height:
        error(f"Plugin icon must be square: {icon_path} is {width}x{height}")
    if icon_path.suffix == ".png" and (width, height) != (256, 256):
        error(f"PNG plugin icon must be 256x256: {icon_path} is {width}x{height}")


def validate_agent_plugins_manifest(plugin_dir: Path) -> dict | None:
    """Validate the root Agent Plugins 1.0 manifest that VS Code auto-detects."""
    path = plugin_dir / "plugin.json"
    data = validate_json(path, ["$schema", "name", "version"])
    if data is None:
        return None
    if data.get("$schema") != AGENT_PLUGINS_SCHEMA:
        error(f"'$schema' must be {AGENT_PLUGINS_SCHEMA} in {rel(path)}")
    unknown = sorted(set(data) - AGENT_PLUGINS_MANIFEST_KEYS)
    if unknown:
        error(f"Unknown key(s) {unknown} in {rel(path)}")
    author = data.get("author")
    if author is not None:
        if not isinstance(author, dict):
            error(f"'author' must be an object in {rel(path)}")
        else:
            unknown_author = sorted(set(author) - AGENT_PLUGINS_AUTHOR_KEYS)
            if unknown_author:
                error(f"Unknown 'author' key(s) {unknown_author} in {rel(path)}")
    name = data.get("name")
    if isinstance(name, str):
        if len(name) > 64:
            error(f"Plugin name exceeds 64 chars in {rel(path)}")
        elif not AGENT_PLUGINS_NAME_RE.match(name):
            error(f"Plugin name '{name}' is not a valid Agent Plugins name in {rel(path)}")
        elif name != plugin_dir.name:
            error(f"Plugin name '{name}' does not match directory '{plugin_dir.name}' in {rel(path)}")
    return data


def validate_agent_plugins_mcp(plugin_dir: Path) -> None:
    """Validate root mcp.json and keep it in agreement with the .mcp.json it mirrors."""
    legacy_path = plugin_dir / ".mcp.json"
    if not legacy_path.exists():
        return
    path = plugin_dir / "mcp.json"
    data = validate_json(path, ["$schema", "mcpServers"])
    if data is None:
        return
    if data.get("$schema") != AGENT_PLUGINS_MCP_SCHEMA:
        error(f"'$schema' must be {AGENT_PLUGINS_MCP_SCHEMA} in {rel(path)}")
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        error(f"'mcpServers' must be an object in {rel(path)}")
        return
    for srv_name, srv in servers.items():
        if not isinstance(srv, dict):
            error(f"MCP server '{srv_name}' must be an object in {rel(path)}")
            continue
        srv_type = srv.get("type")
        if srv_type not in AGENT_PLUGINS_MCP_SERVERS:
            supported = sorted(AGENT_PLUGINS_MCP_SERVERS)
            error(f"MCP server '{srv_name}' has unsupported type '{srv_type}'; expected one of {supported} in {rel(path)}")
            continue
        allowed, required_key = AGENT_PLUGINS_MCP_SERVERS[srv_type]
        if not srv.get(required_key):
            error(f"MCP server '{srv_name}' is {srv_type} but missing '{required_key}' in {rel(path)}")
        unknown = sorted(set(srv) - allowed)
        if unknown:
            error(f"MCP server '{srv_name}' has unknown key(s) {unknown} in {rel(path)}")
        reserved = sorted(AGENT_PLUGINS_RESERVED_ENV & set(srv.get("env") or {}))
        if reserved:
            error(f"MCP server '{srv_name}' must not set reserved env {reserved} in {rel(path)}")

    try:
        legacy_servers = json.loads(legacy_path.read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, json.JSONDecodeError):
        return  # already reported by the .mcp.json check
    if not isinstance(legacy_servers, dict):
        return
    if set(legacy_servers) != set(servers):
        drifted = sorted(set(legacy_servers) ^ set(servers))
        error(f"mcp.json and .mcp.json disagree on servers {drifted} in {plugin_dir.name}")
    for srv_name in sorted(set(legacy_servers) & set(servers)):
        expected = dict(legacy_servers[srv_name]) if isinstance(legacy_servers[srv_name], dict) else {}
        expected.setdefault("type", "stdio")
        if expected != servers.get(srv_name):
            error(f"MCP server '{srv_name}' differs between mcp.json and .mcp.json in {plugin_dir.name}")


def _hook_commands(hooks: dict) -> list[str]:
    """Flatten a hooks object into its decoded command strings."""
    commands: list[str] = []
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    commands.append(hook["command"])
    return commands


def validate_copilot_hooks(plugin_dir: Path) -> None:
    """Validate the VS Code hook manifest under com.github.copilot/."""
    path = plugin_dir / "com.github.copilot" / "hooks" / "hooks.json"
    if not path.exists():
        if (plugin_dir / "hooks" / "hooks.json").exists():
            error(
                "Agent Plugins 1.0 does not read hooks/hooks.json; "
                f"add {rel(plugin_dir / 'com.github.copilot' / 'hooks' / 'hooks.json')}"
            )
        return
    data = validate_json(path, ["hooks"])
    if data is None:
        return
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        error(f"'hooks' must be an object in {rel(path)}")
        return
    for event in sorted(hooks):
        if event not in VSCODE_HOOK_EVENTS:
            error(f"Hook event '{event}' is not supported by VS Code in {rel(path)}")
    for command in _hook_commands(hooks):
        if PLUGIN_ROOT_TOKEN not in command:
            error(f"Hook command must reference {PLUGIN_ROOT_TOKEN} in {rel(path)}: {command}")
        for ref in PLUGIN_ROOT_REF_RE.findall(command):
            if not (plugin_dir / ref).is_file():
                error(f"Hook command references missing file '{ref}' in {rel(path)}")


def validate_version_consistency(plugin_dir: Path) -> None:
    """Every client manifest and the root marketplace entry must agree on version."""
    versions: dict[str, str] = {}
    for manifest in PLUGIN_VERSION_MANIFESTS:
        path = plugin_dir / manifest
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # already reported by validate_json
        if isinstance(data.get("version"), str):
            versions[manifest] = data["version"]
    if len(set(versions.values())) > 1:
        error(f"Plugin version mismatch in {plugin_dir.name}: {versions}")

    marketplace = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    if not versions or not marketplace.is_file():
        return
    try:
        entries = json.loads(marketplace.read_text(encoding="utf-8")).get("plugins", [])
    except json.JSONDecodeError:
        return
    for entry in entries:
        if entry.get("name") == plugin_dir.name and entry.get("version") not in set(versions.values()):
            error(
                f"Marketplace version '{entry.get('version')}' for '{plugin_dir.name}' "
                f"does not match plugin manifests {sorted(set(versions.values()))}"
            )


def validate_plugin(plugin_dir: Path) -> None:
    """Validate a single plugin's manifests and skills."""
    name = plugin_dir.name
    claude_manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    codex_manifest = plugin_dir / ".codex-plugin" / "plugin.json"

    # Allow placeholder plugin directories during repository bootstrap.
    if not claude_manifest.exists() and not codex_manifest.exists():
        print(f"Skipping placeholder plugin directory: {name}")
        return

    print(f"Validating plugin: {name}")

    validate_plugin_icon(plugin_dir)

    # Claude Code manifest
    validate_json(claude_manifest, ["name"])

    # Codex manifest
    validate_json(
        codex_manifest,
        ["name", "version", "description", "author", "interface"],
    )

    # MCP config
    mcp_path = plugin_dir / ".mcp.json"
    if mcp_path.exists():
        data = validate_json(mcp_path, ["mcpServers"])
        if data:
            for srv_name, srv in data.get("mcpServers", {}).items():
                srv_type = srv.get("type", "stdio")
                if srv_type == "stdio" and "command" not in srv:
                    error(f"MCP server '{srv_name}' is stdio but missing 'command'")
                elif srv_type == "http" and "url" not in srv:
                    error(f"MCP server '{srv_name}' is http but missing 'url'")

    # Agent Plugins 1.0 manifest — the format VS Code auto-detects
    if validate_agent_plugins_manifest(plugin_dir) is not None:
        validate_agent_plugins_mcp(plugin_dir)
        validate_copilot_hooks(plugin_dir)

    # Version agreement across every client manifest and the marketplace
    validate_version_consistency(plugin_dir)

    # Skills in this plugin
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_dir.is_dir() and skill_md.exists():
                validate_skill_frontmatter(skill_md)


def validate_top_level_skills() -> None:
    """Validate all skills in the top-level skills/ directory (recursive)."""
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        print(f"Validating skill: {skill_dir.relative_to(REPO_ROOT)}")
        validate_skill_frontmatter(skill_md)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate repo manifests and skills")
    parser.add_argument("--plugin", help="Validate only this plugin")
    args = parser.parse_args()

    plugins_dir = REPO_ROOT / "plugins"

    if args.plugin:
        plugin_dir = plugins_dir / args.plugin
        if not plugin_dir.is_dir():
            print(f"Plugin not found: {args.plugin}", file=sys.stderr)
            sys.exit(1)
        validate_plugin(plugin_dir)
    else:
        # Marketplace manifests
        validate_marketplace(
            REPO_ROOT / ".claude-plugin" / "marketplace.json", "Claude Code"
        )
        validate_marketplace(
            REPO_ROOT / ".agents" / "plugins" / "marketplace.json", "Codex"
        )

        # All plugins
        if plugins_dir.is_dir():
            for plugin_dir in sorted(plugins_dir.iterdir()):
                if plugin_dir.is_dir():
                    validate_plugin(plugin_dir)

        # Top-level skills
        validate_top_level_skills()

    if errors:
        print(f"\nValidation failed with {len(errors)} error(s).", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nAll validations passed.")


if __name__ == "__main__":
    main()
