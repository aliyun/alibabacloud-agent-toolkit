#!/usr/bin/env python3
"""Check DomainCLI locally; install once only after actual user setup authorization.

Uses Python 3 standard library, curl and bash. No cloud business commands, login,
credential inspection, profile changes or package-manager fallback are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

INSTALL_URL = "https://aliyuncli.alicdn.com/cli-ext/domain-cli/install.sh"
INSTALL_SHA256 = "f9d710935c6765299b5be05b7257b28aa20403bccaa0165ae5e5fc93927532c5"
MIN_PARENT = (3, 5, 1)
MIN_EXTENSION = (0, 9, 8)


class SetupError(Exception):
    pass


def run_local(args, deadline, cap, env=None):
    """Enforce a terminating POSIX process-group deadline, not a yield interval."""
    remaining = min(cap, deadline - time.monotonic())
    if remaining <= 0:
        raise SetupError("dependency setup deadline exceeded")
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, env=env, start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                # The group can exit between the timeout and signal delivery.
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                # Do not wait indefinitely for a descendant retaining a pipe.
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                process.stdout.close()
                process.stderr.close()
            raise SetupError("dependency command timed out") from None
        if process.returncode != 0:
            # Installer/auth diagnostics may contain private data: never echo them.
            raise SetupError("dependency command exited unsuccessfully")
        return output


def parse_version(output):
    versions = set(re.findall(r"(?<![\w.])(\d+)\.(\d+)\.(\d+)(?![\w.+-])", output))
    if len(versions) != 1:
        raise SetupError("missing or ambiguous stable semantic version")
    return tuple(map(int, versions.pop()))


def extension_version(output):
    """A generated-product/error payload is not the extension version response."""
    if re.search(r"invalid api|unknown action|unknown command|openapi|\berror\b", output, re.I):
        raise SetupError("DomainCLI version returned a product or error payload")
    text = output.strip()
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict) or any(key.lower() in {"code", "message", "requestid", "error", "data"} for key in data):
            raise SetupError("DomainCLI version returned a product or error payload")
        text = data.get("version", data.get("Version", ""))
        if not isinstance(text, str):
            raise SetupError("DomainCLI version must be a string")
    else:
        # Official text responses may append an abbreviated or full commit hash.
        match = re.fullmatch(
            r"(?:DomainCLI|domain-cli|aliyun-cli-domain|aliyun domain)(?:\s+version)?\s*[:=]?\s*"
            r"(v?(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))"
            r"(?:[ \t]+\([0-9a-f]{7,40}\))?", text, flags=re.I)
        if match:
            text = match.group(1)
    if not re.fullmatch(r"v?(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", text):
        raise SetupError("unrecognized DomainCLI stable version response")
    return parse_version(text.removeprefix("v"))


def check_versions(cli, attribution, deadline, env=None):
    if not cli:
        return None, None
    # An old parent CLI need not understand DomainCLI or its attribution flags.
    try:
        parent = parse_version(run_local([cli, "version"], deadline, 10, env))
    except (SetupError, OSError):
        return None, None
    if parent < MIN_PARENT:
        return parent, None
    try:
        extension = extension_version(run_local(
            [cli, "domain", "version", "--user-agent", attribution, "--cli-ai-mode"],
            deadline, 10, env))
    except (SetupError, OSError, ValueError):
        extension = None
    return parent, extension


def compatible(versions):
    parent, extension = versions
    return bool(parent and extension and parent >= MIN_PARENT and extension >= MIN_EXTENSION)


def initialize(attribution, authorized=False):
    deadline = time.monotonic() + 300
    cli = shutil.which("aliyun")
    cli = str(Path(cli).resolve()) if cli else None
    versions = check_versions(cli, attribution, min(deadline, time.monotonic() + 20))
    if compatible(versions):
        return {"status": "ready", "installed": False, "cli_path": cli,
                "versions": [".".join(map(str, item)) for item in versions]}
    observed = [".".join(map(str, item)) if item else None for item in versions]
    if not authorized:
        return {"status": "awaiting_setup_authorization", "installed": False,
                "versions": observed, "write_effect": "none"}
    if not shutil.which("curl") or not shutil.which("bash"):
        raise SetupError("curl and bash are required; do not install alternate dependencies")
    # Keep the approved install separate from the selected cloud config/profile.
    setup_dir = Path(tempfile.mkdtemp(prefix="domaincli-setup-"))
    installer = setup_dir / "install.sh"
    run_local(["curl", "--proto", "=https", "--proto-redir", "=https",
               "--fail", "--silent", "--show-error", "--location", "--max-redirs", "3",
               "--max-filesize", "1048576", "--max-time", "60", "--output",
               str(installer), INSTALL_URL], deadline, 60)
    if hashlib.sha256(installer.read_bytes()).hexdigest() != INSTALL_SHA256:
        raise SetupError("official installer changed; maintainer review required before execution")
    install_bin = setup_dir / "bin"
    install_bin.mkdir(mode=0o700)
    # Inherit the existing environment without inspecting/logging credential values.
    env = os.environ.copy()
    env.update(ALIYUN_INSTALL_DIR=str(install_bin), DOMAIN_ALIAS="0",
               PATH=str(install_bin) + os.pathsep + os.environ.get("PATH", ""))
    # Vendor check keeps any already compatible parent CLI; this cannot downgrade it.
    run_local(["bash", str(installer), "-y", "-V", "3.5.1"], deadline, 240, env)
    # This authorized setup boundary is the only binary re-resolution exception.
    cli = shutil.which("aliyun", path=env["PATH"])
    cli = str(Path(cli).resolve()) if cli else None
    versions = check_versions(cli, attribution, min(deadline, time.monotonic() + 20), env)
    if not compatible(versions):
        raise SetupError("post-setup versions must be Alibaba Cloud CLI >=3.5.1 and DomainCLI >=0.9.8")
    return {"status": "ready", "installed": True, "cli_path": cli,
            "path_prefix": str(install_bin),
            "versions": [".".join(map(str, item)) for item in versions]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", required=True, help="Current Skill session attribution")
    parser.add_argument("--authorized-setup", action="store_true",
                        help="Only when the actual user explicitly authorized this sandbox setup")
    args = parser.parse_args()
    try:
        manifest = json.loads((Path(__file__).resolve().parents[1] / "references/manifest.json").read_text())
        if (not isinstance(manifest, dict) or not isinstance(manifest.get("name"), str)
                or not re.fullmatch(r"alibabacloud-domain-[a-z]+", manifest["name"])
                or not isinstance(manifest.get("version"), str)
                or not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", manifest["version"])):
            raise SetupError("missing or invalid Skill identity manifest")
        expected = (r"AlibabaCloud-Agent-Skills/" + re.escape(manifest["name"]) +
                    r"/[0-9a-f]{32} skill-version/" + re.escape(manifest["version"]))
        if not re.fullmatch(expected, args.user_agent):
            raise SetupError("attribution does not match the current Skill manifest")
        result = initialize(args.user_agent, args.authorized_setup)
    except SetupError as error:
        result = {"status": "blocked_runtime", "write_effect": "none", "reason": str(error),
                  "next_step": "Maintainer: resolve the observed dependency failure; do not retry setup automatically"}
    except (OSError, ValueError, KeyError):
        # Keep the failure actionable without exposing captured environment output.
        result = {"status": "blocked_runtime", "write_effect": "none",
                  "next_step": "Maintainer: verify the reviewed installer and both minimum versions; do not retry setup automatically"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
