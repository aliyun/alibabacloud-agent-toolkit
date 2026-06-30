#!/usr/bin/env python3
"""
Lightweight regex-based RunScript sandbox pre-checker.
Catches common agent coding mistakes before remote validation.
Zero dependencies — pure stdlib regex only.

Usage:
    python3 check_sandbox.py <script.py> [...]
    python3 check_sandbox.py --dir <dir>
"""
import re
import sys
from pathlib import Path

# ── Rules ────────────────────────────────────────────────────────────

IMPORT_WHITELIST = {
    "asyncio", "collections", "csv", "dataclasses", "datetime", "decimal",
    "enum", "fractions", "functools", "itertools", "json", "math", "re",
    "statistics", "string", "time", "typing", "uuid",
}

FORBIDDEN_FUNCS = [
    "eval", "exec", "compile", "__import__",
    "getattr", "setattr", "hasattr", "delattr",
    "globals", "locals", "vars",
]

# product.action → blocked (case-insensitive match)
BLOCKED_APIS = {
    "ram.listaccesskeys", "sts.assumerole",
    "kms.getsecretvalue", "ecs.describeuserdata",
}

CLI_META_PRODUCTS = {"configure", "plugin", "ossutil", "autocompletion"}

SDK_PATTERNS = [
    (r'\bAcsClient\s*\(', "AcsClient"),
    (r'\bfrom\s+alibabacloud_\w+\.client\s+import', "alibabacloud SDK Client"),
    (r'\bClient\s*\([^)]*access_key', "SDK Client with credentials"),
]

Q = ("\"", "'")


def _str_val(pattern_body: str) -> str:
    """Build a regex that captures a string value in quotes."""
    return rf'["\']({pattern_body}?)["\']'


def check(source: str) -> list[dict]:
    """Return list of {rule_id, line, message, fix} violations."""
    violations = []
    lines = source.splitlines()
    has_result = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # ── SEC-4001: forbidden import ──
        m = re.match(r'^(?:import|from)\s+([\w.]+)', stripped)
        if m:
            mod = m.group(1).split(".")[0]
            if mod not in IMPORT_WHITELIST:
                violations.append({
                    "rule_id": "SEC-4001", "line": i,
                    "message": f"Forbidden import: {mod}",
                    "fix": f"Remove 'import {mod}'. Allowed: {', '.join(sorted(IMPORT_WHITELIST))}. "
                           f"call_cli is pre-injected — do not import it.",
                })

        # ── SEC-4001b: importlib ──
        if re.search(r'\bimportlib\b', stripped):
            violations.append({
                "rule_id": "SEC-4001", "line": i,
                "message": "importlib disallowed",
                "fix": "Remove importlib usage. Dynamic module loading is blocked by the sandbox.",
            })

        # ── OBF-3018: print() ──
        if re.search(r'\bprint\s*\(', stripped):
            violations.append({
                "rule_id": "OBF-3018", "line": i,
                "message": "print() disallowed",
                "fix": "Remove print(); assign data to 'result' instead (dict or list).",
            })

        # ── SEC-4002: eval / exec / reflection ──
        for fn in FORBIDDEN_FUNCS:
            if re.search(rf'\b{fn}\s*\(', stripped):
                violations.append({
                    "rule_id": "SEC-4002", "line": i,
                    "message": f"Forbidden call: {fn}()",
                    "fix": f"Remove {fn}(). Sandbox blocks all reflection and dynamic code execution.",
                })

        # ── SEC-4002: input() ──
        if re.search(r'\binput\s*\(', stripped):
            violations.append({
                "rule_id": "SEC-4002", "line": i,
                "message": "input() disallowed",
                "fix": "Remove input(). The RunScript runtime handles user confirmation (HITL) automatically.",
            })

        # ── SEC-4005: SDK client instantiation ──
        for pattern, label in SDK_PATTERNS:
            if re.search(pattern, stripped):
                violations.append({
                    "rule_id": "SEC-4005", "line": i,
                    "message": f"SDK client detected: {label}",
                    "fix": "Remove SDK client code. Use call_cli(product, version, action, params) instead.",
                })

        # ── SEC-4006: open() for write ──
        m_open = re.search(r'\bopen\s*\(\s*["\']([^"\']+)["\']', stripped)
        if m_open:
            path = m_open.group(1)
            if not path.startswith("/tmp"):
                violations.append({
                    "rule_id": "SEC-4006", "line": i,
                    "message": f"open() outside /tmp: '{path}'",
                    "fix": "Only /tmp paths are writable. Use result variable to return data.",
                })

        # ── SLP-3001: time.sleep > 30 ──
        m_sleep = re.search(r'time\.sleep\s*\(\s*(\d+)', stripped)
        if m_sleep and int(m_sleep.group(1)) > 30:
            violations.append({
                "rule_id": "SLP-3001", "line": i,
                "message": f"time.sleep({m_sleep.group(1)}) > 30s",
                "fix": "Split into a loop: for _ in range(N): time.sleep(30)",
            })

        # ── result assignment ──
        if re.match(r'^\s*result\s*=', line):
            has_result = True

    # ── call_cli deep checks (whole-source) ──
    _check_call_cli(source, lines, violations)

    if not has_result:
        violations.append({
            "rule_id": "OUT-3001", "line": 0,
            "message": "No 'result = ...' assignment found",
            "fix": "Add 'result = <dict or list>' at the end of the script to return data.",
        })

    return violations


def _check_call_cli(source: str, lines: list[str], violations: list[dict]):
    """Parse call_cli() invocations and check product/action/params."""
    # Match call_cli(...) including multiline — find each invocation
    for m in re.finditer(r'call_cli\s*\(', source):
        start = m.start()
        line_no = source[:start].count('\n') + 1

        # Extract the full arg string (balanced parens, up to 500 chars)
        arg_str = _extract_balanced_parens(source, m.end() - 1)
        if not arg_str:
            continue

        # Extract product
        pm = re.search(r'product\s*=\s*["\']([^"\']+)["\']', arg_str)
        product = pm.group(1) if pm else ""

        # Extract action
        am = re.search(r'action\s*=\s*["\']([^"\']+)["\']', arg_str)
        action = am.group(1) if am else ""

        # ── CLI-META: forbidden product ──
        if product.lower() in CLI_META_PRODUCTS:
            violations.append({
                "rule_id": "CLI-META", "line": line_no,
                "message": f"Forbidden CLI meta product: '{product}'",
                "fix": f"'{product}' is a CLI meta command, not a cloud API. Use a real product name.",
            })

        # ── BLK-5001: blocked API ──
        api_key = f"{product}.{action}".lower()
        if api_key in BLOCKED_APIS:
            violations.append({
                "rule_id": "BLK-5001", "line": line_no,
                "message": f"Blocked API: {product}.{action}",
                "fix": f"{product}.{action} returns credentials/secrets and is blocked. Remove this call.",
            })

        # ── BLK-4001: aliyun substring in params values ──
        params_m = re.search(r'params\s*=\s*\{([^}]+)\}', arg_str, re.DOTALL)
        if params_m:
            values = re.findall(r'["\']([^"\']+)["\']', params_m.group(1))
            for val in values:
                if re.search(r'aliyun(?![a-zA-Z_])', val):
                    violations.append({
                        "rule_id": "BLK-4001", "line": line_no,
                        "message": f"Param value '{val[:50]}' contains 'aliyun'",
                        "fix": f"Remove 'aliyun' from '{val[:40]}'. Use plain value or query API to fetch at runtime.",
                    })


def _extract_balanced_parens(source: str, open_pos: int) -> str:
    """Extract content inside balanced () starting at open_pos. Max 2000 chars."""
    depth = 0
    end = min(open_pos + 2000, len(source))
    for i in range(open_pos, end):
        if source[i] == '(':
            depth += 1
        elif source[i] == ')':
            depth -= 1
            if depth == 0:
                return source[open_pos + 1:i]
    return source[open_pos + 1:end]


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: check_sandbox.py <script.py> [...] | --dir <dir>")
        sys.exit(1)

    files = []
    if sys.argv[1] == "--dir":
        files = sorted(Path(sys.argv[2]).glob("*.py"))
    else:
        files = [Path(f) for f in sys.argv[1:]]

    passed = failed = 0
    for f in files:
        vs = check(f.read_text())
        if not vs:
            print(f"  PASS  {f.name}")
            passed += 1
        else:
            print(f"  FAIL  {f.name} ({len(vs)})")
            for v in vs:
                ln = f"L{v['line']}" if v["line"] else "   "
                print(f"        {ln}  [{v['rule_id']}] {v['message']}")
                print(f"              → {v['fix']}")
            failed += 1

    total = passed + failed
    print(f"\n  {passed}/{total} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
