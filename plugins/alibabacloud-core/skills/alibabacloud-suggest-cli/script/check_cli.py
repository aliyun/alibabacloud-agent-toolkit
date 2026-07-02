#!/usr/bin/env python3
"""
Lightweight regex-based checker for MCP CallCLI execution strings.

The suggest-cli skill uses `GenerateCLICommand`: take **`unifiedCli`** as the CallCLI command
string, or **`cli`** when `unifiedCli` is empty — verbatim, no manual rewriting. This checker
validates each command string against CallCLI's execution constraints.
Zero dependencies -- pure stdlib regex.

Usage:
    python3 check_cli.py <commands.sh> [...]
    python3 check_cli.py --dir <dir>

Each input file holds one CallCLI command string per line. Blank lines and
lines starting with `#` are ignored.
"""
import re
import sys
from pathlib import Path

# -- Rules ------------------------------------------------------------------

# Shell metacharacters / operators forbidden by MCP CallCLI (checked OUTSIDE
# quotes, so JMESPath/JSON values containing them are not false-flagged).
SHELL_OPERATORS = [
    (r'\$\(', "command substitution $(...)"),
    (r'`', "backtick command substitution"),
    (r'\|\|', "logical OR ||"),
    (r'&&', "logical AND &&"),
    (r'>', "output redirection >"),
    (r'<', "input redirection <"),
    (r';', "command separator ;"),
    (r'\|', "pipe |"),
]

# Local-file references forbidden by MCP CallCLI (the server is remote).
LOCAL_FILE = [
    (r'\bfileb?://', "local file reference (file:// / fileb://)"),
]


def _strip_quoted(cmd: str) -> str:
    """Remove single/double quoted spans so operator checks ignore values."""
    return re.sub(r"'[^']*'|\"[^\"]*\"", " ", cmd)


def _check_line(cmd: str, line_no: int) -> list[dict]:
    """Validate a single CallCLI command string."""
    violations = []

    # -- REQ-3001: must be an aliyun command --
    if not re.match(r'^aliyun\b', cmd.strip()):
        violations.append({
            "rule_id": "REQ-3001", "line": line_no,
            "message": "CallCLI command must start with `aliyun`",
            "fix": "Every CallCLI execution string must invoke the `aliyun` CLI binary "
                   "(no `echo`, no env prefixes, no leading subshell).",
        })
        return violations

    # -- SEC-2002: shell operators outside quotes (CallCLI forbids them) --
    unquoted = _strip_quoted(cmd)
    for pattern, label in SHELL_OPERATORS:
        if re.search(pattern, unquoted):
            violations.append({
                "rule_id": "SEC-2002", "line": line_no,
                "message": f"Shell construct not allowed by CallCLI: {label}",
                "fix": "CallCLI runs a single `aliyun` command with no shell. Remove pipes, "
                       "redirects, operators, and substitution; use --cli-query to filter instead.",
            })

    # -- SEC-2003: local file references (CallCLI server is remote) --
    for pattern, label in LOCAL_FILE:
        if re.search(pattern, cmd):
            violations.append({
                "rule_id": "SEC-2003", "line": line_no,
                "message": f"{label} cannot be used via CallCLI",
                "fix": "The MCP server is remote and has no access to local files. Run "
                       "file-based commands (e.g. oss cp) with the local Bash tool instead.",
            })

    return violations


def check(source: str) -> list[dict]:
    """Return list of {rule_id, line, message, fix} violations."""
    violations = []
    for i, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        violations.extend(_check_line(line, i))
    return violations


# -- CLI --------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: check_cli.py <commands.sh> [...] | --dir <dir>")
        sys.exit(1)

    if sys.argv[1] == "--dir":
        files = sorted(Path(sys.argv[2]).glob("*.sh"))
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
                print(f"              -> {v['fix']}")
            failed += 1

    total = passed + failed
    print(f"\n  {passed}/{total} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
