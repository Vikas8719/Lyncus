"""
Go Language Checks — staticcheck, gosec, golangci-lint, go vet, deadcode, gocognit
Go tools module root (go.mod wale folder) mein chalte hain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ALL_PACKAGES = "./..."

# Named constants
_GOCOGNIT_COMPLEXITY_THRESHOLD = 15   # Cognitive complexity threshold (functions above this are flagged)
_GOSEC_RSA_MIN_KEY_SIZE = 2048        # Minimum secure RSA key size in bits


@dataclass
class GoToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_go_mod: bool = True


# ── GO TOOL DEFINITIONS ───────────────────────────────────────────────────────

GO_TOOLS: list[GoToolConfig] = [

    GoToolConfig(
        name="go-vet",
        command=["go", "vet", _ALL_PACKAGES],
        check_type="quality",
        output_format="text",
        description="Built-in Go analyzer — suspicious constructs, common mistakes",
        min_version="built-in",
        install_cmd="go (built-in, kuch install nahi karna)",
    ),

    GoToolConfig(
        name="staticcheck",
        command=["staticcheck", "-f", "json", _ALL_PACKAGES],
        check_type="quality",
        output_format="json",
        description="Advanced static analysis — bugs, performance, simplifications",
        min_version="2024.1",
        install_cmd="go install honnef.co/go/tools/cmd/staticcheck@latest",
    ),

    GoToolConfig(
        name="gosec",
        command=[
            "gosec",
            "-fmt", "json",
            "-out", "/dev/stdout",
            "-quiet",
            _ALL_PACKAGES,
        ],
        check_type="security",
        output_format="json",
        description="Security scanner — SQL injection, command injection, crypto issues",
        min_version="2.20.0",
        install_cmd="go install github.com/securego/gosec/v2/cmd/gosec@latest",
    ),

    GoToolConfig(
        name="golangci-lint",
        command=[
            "golangci-lint", "run",
            "--out-format", "json",
            "--timeout", "120s",
        ],
        check_type="quality",
        output_format="json",
        description="Meta linter — 50+ linters ek saath chalata hai",
        min_version="1.59.0",
        install_cmd=(
            "# macOS:\nbrew install golangci-lint\n"
            "# Linux:\ncurl -sSfL https://raw.githubusercontent.com/golangci/"
            "golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin"
        ),
    ),

    GoToolConfig(
        name="deadcode",
        command=["deadcode", "-test", _ALL_PACKAGES],
        check_type="deadcode",
        output_format="text",
        description="Unused function detector — dead code pakadta hai",
        min_version="latest",
        install_cmd="go install golang.org/x/tools/cmd/deadcode@latest",
    ),

    GoToolConfig(
        name="gocognit",
        command=["gocognit", "-over", "15", "{path}"],
        check_type="complexity",
        output_format="text",
        description="Cognitive complexity checker — complex functions flag karta hai",
        min_version="1.1.0",
        install_cmd="go install github.com/uudashr/gocognit/cmd/gocognit@latest",
    ),

    GoToolConfig(
        name="go-test-coverage",
        command=["go", "test", "-coverprofile=coverage.out", "-covermode=atomic", _ALL_PACKAGES],
        check_type="coverage",
        output_format="text",
        description="Test coverage measurement",
        min_version="built-in",
        install_cmd="go (built-in)",
    ),
]


# ── STATICCHECK RULE CATEGORIES ───────────────────────────────────────────────

STATICCHECK_CATEGORY_MAP: dict[str, str] = {
    "SA": "QUALITY",     # Static analysis
    "S":  "SIMPLIFY",    # Code simplification
    "ST": "STYLE",       # Style
    "QF": "QUICKFIX",    # Quick fixes
    "U":  "DEADCODE",    # Unused code
}


def get_staticcheck_category(code: str) -> str:
    """Staticcheck check code se category nikalo."""
    for prefix, cat in sorted(STATICCHECK_CATEGORY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        suffix = code.removeprefix(prefix)
        if code.startswith(prefix) and suffix.isdigit():
            return cat
    return "QUALITY"


def get_staticcheck_severity(code: str) -> str:
    """Staticcheck code se severity nikalo."""
    # U (unused) codes warnings hain
    if code.startswith("U"):
        return "warning"
    # SA1xxx = correctness bugs — critical
    if code.startswith("SA1"):
        return "critical"
    if code.startswith("SA"):
        return "warning"
    return "info"


# ── GOSEC RULE DESCRIPTIONS ───────────────────────────────────────────────────

GOSEC_RULE_MAP: dict[str, tuple[str, str]] = {
    # (category, description)
    "G101": ("SECURITY", "Hardcoded credentials found"),
    "G102": ("SECURITY", "Network binding to all interfaces"),
    "G103": ("SECURITY", "Unsafe package use"),
    "G104": ("QUALITY",  "Errors unhandled — error return ignored"),
    "G106": ("SECURITY", "SSH InsecureIgnoreHostKey use"),
    "G107": ("SECURITY", "URL provided to HTTP request from variable"),
    "G108": ("SECURITY", "Profiling endpoint automatically exposed"),
    "G109": ("SECURITY", "Potential integer overflow"),
    "G110": ("SECURITY", "Potential DoS via decompression bomb"),
    "G111": ("SECURITY", "Directory traversal via HTTP request"),
    "G112": ("SECURITY", "Insecure TLS minimum version"),
    "G113": ("SECURITY", "Potential integer overflow in strconv"),
    "G114": ("SECURITY", "HTTP serve with deprecated insecure function"),
    "G201": ("SECURITY", "SQL string formatting — injection risk"),
    "G202": ("SECURITY", "SQL string concatenation — injection risk"),
    "G203": ("SECURITY", "Use of unescaped data in HTML template"),
    "G204": ("SECURITY", "Subprocess with variable — injection risk"),
    "G301": ("SECURITY", "Poor file permissions on created directory"),
    "G302": ("SECURITY", "Poor file permissions on file"),
    "G303": ("SECURITY", "Creating tempfile with bad permissions"),
    "G304": ("SECURITY", "File path provided as taint input"),
    "G305": ("SECURITY", "File traversal when extracting zip/tar"),
    "G306": ("SECURITY", "Poor file permissions when writing"),
    "G401": ("SECURITY", "Use of weak cryptographic primitive (MD5/SHA1)"),
    "G402": ("SECURITY", "TLS InsecureSkipVerify set to true"),
    "G403": ("SECURITY", "Insecure RSA key size < 2048"),
    "G404": ("SECURITY", "Insecure random number source (math/rand)"),
    "G405": ("SECURITY", "Use of weak cipher (DES/RC4)"),
    "G406": ("SECURITY", "Use of MD4 or RIPEMD160"),
    "G501": ("SECURITY", "Import of blacklisted package: crypto/md5"),
    "G502": ("SECURITY", "Import of blacklisted package: crypto/des"),
    "G503": ("SECURITY", "Import of blacklisted package: crypto/rc4"),
    "G504": ("SECURITY", "Import of blacklisted package: net/http/cgi"),
    "G505": ("SECURITY", "Import of blacklisted package: crypto/sha1"),
    "G601": ("SECURITY", "Implicit memory aliasing in for loop"),
    "G602": ("SECURITY", "Slice access out of bounds"),
}


def get_gosec_info(rule_id: str) -> tuple[str, str]:
    """Gosec rule ID se (category, description) nikalo."""
    return GOSEC_RULE_MAP.get(rule_id, ("SECURITY", f"Security issue: {rule_id}"))


GOSEC_SEVERITY_MAP: dict[str, str] = {
    "HIGH":   "critical",
    "MEDIUM": "warning",
    "LOW":    "info",
}


def get_gosec_severity(severity: str) -> str:
    return GOSEC_SEVERITY_MAP.get(severity.upper(), "warning")


# ── GOLANGCI-LINT OUTPUT PARSER ───────────────────────────────────────────────

def parse_golangci_json(json_output: str) -> list[dict[str, Any]]:
    """golangci-lint JSON output parse karo."""
    issues = []
    try:
        data = json.loads(json_output)
        for issue in data.get("Issues", []) or []:
            pos = issue.get("Pos", {})
            issues.append({
                "linter":   issue.get("FromLinter", "golangci"),
                "text":     issue.get("Text", ""),
                "file":     pos.get("Filename", ""),
                "line":     pos.get("Line", 0),
                "column":   pos.get("Column", 0),
                "severity": _golangci_severity(issue.get("Severity", "")),
                "category": _golangci_category(issue.get("FromLinter", "")),
            })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return issues


def _golangci_severity(severity: str) -> str:
    sev_map = {"error": "critical", "warning": "warning", "": "warning"}
    return sev_map.get(severity.lower(), "warning")


def _golangci_category(linter_name: str) -> str:
    security_linters = {"gosec", "gocritic", "staticcheck"}
    deadcode_linters = {"deadcode", "unused", "unparam"}
    if linter_name in security_linters:
        return "SECURITY"
    if linter_name in deadcode_linters:
        return "DEADCODE"
    return "QUALITY"


# ── GO.MOD FINDER ─────────────────────────────────────────────────────────────

def find_go_mod(project_path: str) -> str | None:
    """go.mod wala folder dhundo — tools wahan chalenge."""
    path = Path(project_path)

    search_path = path.parent if path.is_file() else path
    for parent in (search_path, *search_path.parents):
        if (parent / "go.mod").exists():
            return str(parent)

    for go_mod in path.rglob("go.mod"):
        return str(go_mod.parent)

    return None


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_go_tools(
    only: str | None = None,
    skip_slow: bool = False,
) -> list[GoToolConfig]:
    """
    Go tools ki filtered list.

    Args:
        only: quality / security / deadcode / complexity / coverage
        skip_slow: golangci-lint (slow) skip karo
    """
    tools = GO_TOOLS.copy()

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"golangci-lint", "go-test-coverage"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in GO_TOOLS}
