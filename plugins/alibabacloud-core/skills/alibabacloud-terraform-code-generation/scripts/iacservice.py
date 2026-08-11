#!/usr/bin/env python3
"""Call IaCService APIs through Alibaba Cloud OpenAPI SDK or CLI.

This wrapper gives the skill a concrete, auditable IaCService call path when a
platform OpenAPI tool is not available. It never reads, accepts, or prints
AK/SK values; authentication is delegated to the Alibaba Cloud SDK credential
chain or, when CLI transport is selected, to the user's existing `aliyun` CLI
configuration, environment, or role-based credential chain.

Examples:
    scripts/iacservice.py ListTerraformProviderVersions
    scripts/iacservice.py ListProducts --provider-version 1.282.0
    scripts/iacservice.py ListResourceTypes --provider-version 1.282.0 --product OSS
    scripts/iacservice.py GetResourceType --provider-version 1.282.0 --resource-type alicloud_oss_bucket
    scripts/iacservice.py ValidateModule --body-file validate-module-body.json
    scripts/iacservice.py ValidateModule --module-dir ./generated-module
    scripts/iacservice.py ListProducts --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

POP_VERSION = "2021-08-06"
DEFAULT_ENDPOINT = "iac.cn-zhangjiakou.aliyuncs.com"
REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "references" / "alicloud-providers.md"
MODULE_FILE_SUFFIXES = {".tf", ".tfvars"}
MODULE_FILE_NAMES = {"terraform.tf.json", "terraform.tfvars.json"}

SUPPORTED_APIS = {
    "ListTerraformProviderVersions",
    "ListProducts",
    "ListResourceTypes",
    "GetResourceType",
    "ValidateModule",
}

PAGINATED_APIS = {
    "ListTerraformProviderVersions": "versions",
    "ListProducts": "products",
    "ListResourceTypes": "resourceTypes",
}

API_SPECS = {
    "ListTerraformProviderVersions": {
        "action": "ListTerraformProviderVersions",
        "cli": "list-terraform-provider-versions",
        "method": "GET",
        "path": "/version/terraform/provider",
        "body_type": "json",
        "req_body_type": "json",
    },
    "ListProducts": {
        "action": "ListProducts",
        "cli": "list-products",
        "method": "GET",
        "path": "/products",
        "body_type": "json",
        "req_body_type": "json",
    },
    "ListResourceTypes": {
        "action": "ListResourceTypes",
        "cli": "list-resource-types",
        "method": "GET",
        "path": "/resourceTypes",
        "body_type": "json",
        "req_body_type": "json",
    },
    "GetResourceType": {
        "action": "GetResourceType",
        "cli": "get-resource-type",
        "method": "GET",
        "path": "/resourceType/{resourceType}",
        "body_type": "json",
        "req_body_type": "json",
    },
    "ValidateModule": {
        "action": "ValidateModule",
        "cli": "validate-module",
        "method": "POST",
        "path": "/module/validation",
        "body_type": "json",
        "req_body_type": "json",
    },
}

QUERY_KEY_MAP = {
    "ProviderVersion": "terraformProviderVersion",
    "Product": "product",
    "ResourceType": "resourceType",
    "MaxResults": "maxResults",
    "NextToken": "nextToken",
    "Keyword": "keyword",
    "Sort": "sort",
    "Status": "status",
    "Subcategory": "subcategory",
    "SupportTerraformer": "supportTerraformer",
    "AcceptLanguage": "acceptLanguage",
    "FilterReadOnly": "filterReadOnly",
    "Usage": "usage",
}

CLI_FLAG_MAP = {
    "terraformProviderVersion": "--terraform-provider-version",
    "product": "--product",
    "resourceType": "--resource-type",
    "maxResults": "--max-results",
    "nextToken": "--next-token",
    "keyword": "--keyword",
    "sort": "--sort",
    "status": "--status",
    "subcategory": "--subcategory",
    "supportTerraformer": "--support-terraformer",
    "acceptLanguage": "--accept-language",
    "filterReadOnly": "--filter-read-only",
    "usage": "--usage",
}


def compact_response(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        parsed_lines = []
        for line in lines:
            try:
                parsed_lines.append(json.loads(line))
            except json.JSONDecodeError:
                parsed_lines = []
                break
        if parsed_lines:
            return parsed_lines
        return text


def response_status_ok(response: Any) -> bool:
    if isinstance(response, list):
        return all(response_status_ok(item) for item in response)
    if not isinstance(response, dict):
        return True
    payload = response.get("body") if isinstance(response.get("body"), dict) else response
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    status = data.get("status")
    if isinstance(status, str) and status.lower() in {"errored", "error", "failed"}:
        return False
    success = data.get("success")
    if success is False:
        return False
    return True


def evidence_command(command: list[str]) -> list[str]:
    if "--body" in command:
        command = command[: command.index("--body")]
    return command


def compact_sdk_response(response: Any) -> Any:
    if hasattr(response, "to_map"):
        return response.to_map()
    if isinstance(response, dict):
        return response
    return response


def catalog_entry(resource_type: str) -> dict[str, str] | None:
    if not CATALOG_PATH.exists():
        return None
    pattern = re.compile(
        rf"^\| (?P<kind>[^|]+) \| `{re.escape(resource_type)}` \| "
        rf"(?P<status>[^|]*) \| \[doc\]\((?P<doc>[^)]+)\) \|$",
        re.MULTILINE,
    )
    match = pattern.search(CATALOG_PATH.read_text(encoding="utf-8"))
    if not match:
        return None
    return {key: value.strip() for key, value in match.groupdict().items()}


def module_files(module_dir: Path) -> list[Path]:
    if not module_dir.is_dir():
        raise SystemExit(f"--module-dir is not a directory: {module_dir}")
    files: list[Path] = []
    for path in sorted(module_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(module_dir)
        if any(part.startswith(".terraform") for part in rel.parts):
            continue
        if path.name in MODULE_FILE_NAMES or path.suffix in MODULE_FILE_SUFFIXES:
            files.append(path)
    if not files:
        raise SystemExit(f"--module-dir contains no Terraform module files: {module_dir}")
    return files


def build_validate_module_body(args: argparse.Namespace) -> dict[str, Any]:
    module_dir = Path(args.module_dir).expanduser().resolve()
    code_map: dict[str, str] = {}
    code_parts: list[str] = []
    for path in module_files(module_dir):
        rel = path.relative_to(module_dir).as_posix()
        content = path.read_text(encoding="utf-8")
        code_map[rel] = content
        code_parts.append(f"# {rel}\n{content.rstrip()}\n")

    digest = hashlib.sha256()
    for rel in sorted(code_map):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(code_map[rel].encode("utf-8"))
        digest.update(b"\0")

    return {
        "clientToken": args.client_token or digest.hexdigest()[:64],
        "code": "\n".join(code_parts).rstrip() + "\n",
        **({} if args.omit_source else {"source": args.source}),
        **({} if args.omit_source_path else {"sourcePath": args.source_path or str(module_dir)}),
        "codeMap": code_map,
    }


def build_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {}
    explicit_bodies = [bool(args.body_file), bool(args.body_json), bool(args.module_dir)]
    if sum(explicit_bodies) > 1:
        raise SystemExit("use only one of --body-file, --body-json, or --module-dir")
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as f:
            body = json.load(f)
    if args.body_json:
        body = json.loads(args.body_json)
    if args.module_dir:
        if args.api != "ValidateModule":
            raise SystemExit("--module-dir is only supported for ValidateModule")
        body = build_validate_module_body(args)
    if not isinstance(body, dict):
        raise SystemExit("request body must be a JSON object")
    if args.provider_version:
        body["ProviderVersion"] = args.provider_version
    if args.product:
        body["Product"] = args.product
    if args.resource_type:
        body["ResourceType"] = args.resource_type
    if args.max_results:
        body["MaxResults"] = args.max_results
    if args.next_token:
        body["NextToken"] = args.next_token
    for item in args.param or []:
        if "=" not in item:
            raise SystemExit(f"--param must be KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        body[key] = value
    return body


def normalize_query(body: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for key, value in body.items():
        query[QUERY_KEY_MAP.get(key, key)] = value
    return query


def sdk_available() -> bool:
    try:
        import alibabacloud_credentials.client  # noqa: F401
        import alibabacloud_credentials.models  # noqa: F401
        import alibabacloud_tea_openapi.client  # noqa: F401
        import alibabacloud_tea_openapi.models  # noqa: F401
    except Exception:
        return False
    return True


def sdk_call(args: argparse.Namespace, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from alibabacloud_credentials.client import Client as CredentialClient
    from alibabacloud_tea_openapi.client import Client as OpenApiClient
    from alibabacloud_tea_openapi.models import Config, OpenApiRequest, Params
    from alibabacloud_tea_util.models import RuntimeOptions

    spec = API_SPECS[args.api]
    endpoint = args.endpoint or os.environ.get("IACSERVICE_ENDPOINT") or DEFAULT_ENDPOINT
    credential = CredentialClient()
    client = OpenApiClient(Config(
        credential=credential,
        endpoint=endpoint,
        protocol="https",
        user_agent=args.user_agent,
    ))
    query = normalize_query(body)
    request_body: Any = None
    path = spec["path"]
    if args.api == "GetResourceType":
        resource_type = query.pop("resourceType", None)
        if not resource_type:
            raise SystemExit("GetResourceType requires --resource-type")
        path = path.replace("{resourceType}", str(resource_type))
    elif args.api == "ValidateModule":
        request_body = body
        query = {}

    params = Params(
        action=spec["action"],
        version=POP_VERSION,
        protocol="HTTPS",
        pathname=path,
        method=spec["method"],
        auth_type="AK",
        style="ROA",
        body_type=spec["body_type"],
        req_body_type=spec["req_body_type"],
    )
    request = OpenApiRequest(query=query or None, body=request_body)
    runtime = RuntimeOptions(read_timeout=120000, connect_timeout=10000)
    response = compact_sdk_response(client.call_api(params, request, runtime))
    result = {
        "ok": response_status_ok(response),
        "api": args.api,
        "transport": "sdk",
        "endpoint": endpoint,
        "method": spec["method"],
        "path": path,
        "body_keys": sorted(body.keys()),
        "response": response,
    }
    return (0 if result["ok"] else 1), result


def call_once(args: argparse.Namespace, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if args.transport in ("auto", "sdk") and sdk_available():
        try:
            return sdk_call(args, body)
        except Exception as exc:
            if args.transport == "sdk":
                result = {
                    "ok": False,
                    "api": args.api,
                    "transport": "sdk",
                    "endpoint": args.endpoint or os.environ.get("IACSERVICE_ENDPOINT") or DEFAULT_ENDPOINT,
                    "body_keys": sorted(body.keys()),
                    "error": f"{type(exc).__name__}: {str(exc)[-2000:]}",
                }
                return 1, result
            sdk_error = f"{type(exc).__name__}: {str(exc)[-500:]}"
        else:
            sdk_error = ""

    try:
        code, result = cli_call(args, body)
    except FileNotFoundError as exc:
        result = {
            "ok": False,
            "api": args.api,
            "transport": "cli",
            "body_keys": sorted(body.keys()),
            "error": str(exc),
        }
        return 127, result
    if args.transport == "auto" and "sdk_error" in locals() and sdk_error:
        result["sdk_error"] = sdk_error
    return code, result


def response_body(result: dict[str, Any]) -> dict[str, Any]:
    response = result.get("response")
    if isinstance(response, dict):
        body = response.get("body")
        if isinstance(body, dict):
            return body
        return response
    return {}


def paginated_call(args: argparse.Namespace, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if args.api not in PAGINATED_APIS:
        raise SystemExit("--all-pages is only supported for list APIs")
    if args.next_token:
        raise SystemExit("use either --all-pages or --next-token, not both")

    item_key = PAGINATED_APIS[args.api]
    merged_items: list[Any] = []
    request_ids: list[str] = []
    page_count = 0
    next_token = ""
    last_result: dict[str, Any] | None = None

    while True:
        page_body = dict(body)
        if next_token:
            page_body["NextToken"] = next_token
        code, result = call_once(args, page_body)
        last_result = result
        if code != 0 or not result.get("ok"):
            return code, result
        page_count += 1
        body_payload = response_body(result)
        items = body_payload.get(item_key)
        if isinstance(items, list):
            merged_items.extend(items)
        request_id = body_payload.get("requestId")
        if request_id:
            request_ids.append(request_id)
        next_token = body_payload.get("nextToken") or ""
        if not next_token:
            break

    assert last_result is not None
    body_payload = response_body(last_result)
    body_payload = {key: value for key, value in body_payload.items() if key != item_key}
    body_payload[item_key] = merged_items
    body_payload["pageCount"] = page_count
    body_payload["requestIds"] = request_ids
    body_payload["totalFetched"] = len(merged_items)
    body_payload.pop("nextToken", None)
    result = {
        "ok": True,
        "api": args.api,
        "transport": last_result.get("transport"),
        "endpoint": last_result.get("endpoint"),
        "body_keys": sorted(body.keys()),
        "all_pages": True,
        "response": {"body": body_payload},
    }
    return 0, result


def cli_command(args: argparse.Namespace, body: dict[str, Any]) -> list[str]:
    cli_path = shutil.which(args.cli)
    if not cli_path:
        raise FileNotFoundError(f"CLI not found on PATH: {args.cli}")

    spec = API_SPECS[args.api]
    endpoint = args.endpoint or os.environ.get("IACSERVICE_ENDPOINT") or DEFAULT_ENDPOINT
    command = [cli_path, "iacservice", spec["cli"], "--endpoint", endpoint]
    if args.region:
        command.extend(["--region", args.region])
    if args.profile:
        command.extend(["--profile", args.profile])
    query = normalize_query(body)
    if args.api == "ValidateModule":
        if body:
            command.extend(["--body", json.dumps(body, ensure_ascii=False)])
        return command
    for key, value in query.items():
        flag = CLI_FLAG_MAP.get(key)
        if not flag:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, list):
            command.append(flag)
            command.extend(str(item) for item in value)
            continue
        command.extend([flag, str(value)])
    return command


def cli_call(args: argparse.Namespace, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    command = cli_command(args, body)
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    response = compact_response(proc.stdout)
    api_ok = proc.returncode == 0 and response_status_ok(response)
    result = {
        "ok": api_ok,
        "api": args.api,
        "transport": "cli",
        "exit_code": proc.returncode,
        "command": evidence_command(command),
        "body_keys": sorted(body.keys()),
        "response": response,
        "stderr": proc.stderr.strip()[-2000:] if proc.stderr.strip() else "",
    }
    return (0 if api_ok else proc.returncode or 1), result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("api", choices=sorted(SUPPORTED_APIS))
    parser.add_argument("--provider-version")
    parser.add_argument("--product")
    parser.add_argument("--resource-type")
    parser.add_argument("--max-results", type=int)
    parser.add_argument("--next-token")
    parser.add_argument("--body-file", help="Path to a JSON request body file.")
    parser.add_argument("--body-json", help="Inline JSON request body string.")
    parser.add_argument(
        "--module-dir",
        help="For ValidateModule, build the request body from a Terraform module directory.",
    )
    parser.add_argument(
        "--client-token",
        help="For ValidateModule --module-dir, override the deterministic clientToken.",
    )
    parser.add_argument(
        "--source",
        default="Upload",
        help="For ValidateModule --module-dir, body.source value. Default: Upload.",
    )
    parser.add_argument(
        "--source-path",
        help="For ValidateModule --module-dir, body.sourcePath value. Default: resolved module path.",
    )
    parser.add_argument(
        "--omit-source",
        action="store_true",
        help="For ValidateModule --module-dir, omit body.source.",
    )
    parser.add_argument(
        "--omit-source-path",
        action="store_true",
        help="For ValidateModule --module-dir, omit body.sourcePath.",
    )
    parser.add_argument(
        "--param",
        action="append",
        help="Extra request body parameter as KEY=VALUE. May be repeated.",
    )
    parser.add_argument("--region", default=None, help="Optional CLI region.")
    parser.add_argument("--profile", default=None, help="Optional CLI profile.")
    parser.add_argument(
        "--endpoint",
        default=None,
        help=f"IaCService endpoint. Default: env IACSERVICE_ENDPOINT or {DEFAULT_ENDPOINT}.",
    )
    parser.add_argument(
        "--transport",
        choices=("auto", "sdk", "cli"),
        default="auto",
        help="Call transport. Default: auto (SDK first, CLI fallback).",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Optional SDK User-Agent value, for example skill/session attribution.",
    )
    parser.add_argument(
        "--cli",
        default="aliyun",
        help="Alibaba Cloud CLI executable name/path. Default: aliyun.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command and request body without calling the API.",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Follow nextToken and merge all pages for list APIs.",
    )
    parser.add_argument(
        "--force-resource-type",
        action="store_true",
        help="Call GetResourceType even if the local catalog says the name is a data source.",
    )
    args = parser.parse_args()

    body = build_body(args)

    if args.api == "GetResourceType" and args.resource_type and not args.force_resource_type:
        entry = catalog_entry(args.resource_type)
        if entry and entry.get("kind") == "data source":
            print(json.dumps({
                "ok": True,
                "api": args.api,
                "skipped": True,
                "reason": "local catalog marks resource type as data source; GetResourceType is resource-only",
                "resource_type": args.resource_type,
                "catalog": entry,
                "body_keys": sorted(body.keys()),
            }, ensure_ascii=False, indent=2))
            return 0

    if args.dry_run:
        endpoint = args.endpoint or os.environ.get("IACSERVICE_ENDPOINT") or DEFAULT_ENDPOINT
        command: list[str] | None = None
        try:
            command = cli_command(args, body)
        except FileNotFoundError:
            pass
        print(json.dumps({
            "ok": True,
            "dry_run": True,
            "api": args.api,
            "endpoint": endpoint,
            "transport": args.transport,
            "all_pages": args.all_pages,
            "sdk_available": sdk_available(),
            "command": evidence_command(command) if command else None,
            "body_keys": sorted(body.keys()),
        }, ensure_ascii=False, indent=2))
        return 0

    if args.all_pages:
        code, result = paginated_call(args, body)
    else:
        code, result = call_once(args, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
