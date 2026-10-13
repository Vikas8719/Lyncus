"""
JavaScript / TypeScript Language Checks
eslint, tsc, npm audit, ts-prune, c8, stryker-js
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"
_PACKAGE_JSON = "package.json"


@dataclass
class JsToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    typescript_only: bool = False  # Sirf TS projects ke liye


# ── JS/TS TOOL DEFINITIONS ────────────────────────────────────────────────────

JS_TOOLS: list[JsToolConfig] = [
    JsToolConfig(
        name="eslint",
        command=[
            "npx",
            "eslint",
            _PATH_ARGUMENT,
            "--format",
            "json",
            "--no-eslintrc",
            "--rule",
            '{"no-unused-vars": "warn", "no-undef": "error", "no-console": "warn"}',
            "--ext",
            ".js,.jsx,.ts,.tsx,.mjs,.cjs",
        ],
        check_type="quality",
        output_format="json",
        description="JavaScript/TypeScript linter — bugs, style, best practices",
        min_version="9.0.0",
        install_cmd="npm install -g eslint@latest",
    ),
    JsToolConfig(
        name="tsc",
        command=["npx", "tsc", "--noEmit", "--strict"],
        check_type="quality",
        output_format="text",
        description="TypeScript compiler — type errors pakadta hai",
        min_version="5.4.0",
        install_cmd="npm install -g typescript@latest",
        typescript_only=True,
    ),
    JsToolConfig(
        name="npm-audit",
        command=["npm", "audit", "--json"],
        check_type="security",
        output_format="json",
        description="npm dependency vulnerability scanner",
        min_version="built-in",
        install_cmd="npm (built-in — npm install karke use karo)",
    ),
    JsToolConfig(
        name="ts-prune",
        command=["npx", "ts-prune", "-p", "{path}/tsconfig.json"],
        check_type="deadcode",
        output_format="text",
        description="Unused TypeScript exports detector",
        min_version="0.10.3",
        install_cmd="npm install -g ts-prune",
        typescript_only=True,
    ),
    JsToolConfig(
        name="c8",
        command=[
            "npx",
            "c8",
            "--reporter=text",
            "--branches",
            "80",
            "node",
            "--experimental-vm-modules",
            "npx",
            "jest",
            "--coverage=false",
        ],
        check_type="coverage",
        output_format="text",
        description="Code coverage — V8 native coverage",
        min_version="10.0.0",
        install_cmd="npm install -g c8",
    ),
    JsToolConfig(
        name="stryker-js",
        command=[
            "npx",
            "stryker",
            "run",
            "--reporters",
            "clear-text",
        ],
        check_type="faketests",
        output_format="text",
        description="Mutation testing — fake/weak tests pakadta hai",
        min_version="8.2.0",
        install_cmd="npm install -g @stryker-mutator/core",
    ),
    JsToolConfig(
        name="jshint",
        command=["jshint", _PATH_ARGUMENT, "--reporter=jslint"],
        check_type="quality",
        output_format="json",
        description="JavaScript hint checker — common errors",
        min_version="2.13.0",
        install_cmd="npm install -g jshint",
    ),
    JsToolConfig(
        name="depcheck",
        command=["npx", "depcheck", _PATH_ARGUMENT, "--json"],
        check_type="deadcode",
        output_format="json",
        description="Unused/missing npm dependency detector",
        min_version="1.4.7",
        install_cmd="npm install -g depcheck",
    ),
]


# ── ESLINT RULE CATEGORIES ────────────────────────────────────────────────────

ESLINT_CATEGORY_MAP: dict[str, str] = {
    # Rule prefix/name → category
    "no-unused": "DEADCODE",
    "no-undef": "QUALITY",
    "no-console": "QUALITY",
    "no-var": "QUALITY",
    "prefer-const": "QUALITY",
    "eqeqeq": "BUGPRONE",
    "no-eval": "SECURITY",
    "no-implied-eval": "SECURITY",
    "no-new-func": "SECURITY",
    "no-script-url": "SECURITY",
    "security/": "SECURITY",
    "@typescript-eslint/no-explicit-any": "TYPES",
    "@typescript-eslint/no-unused-vars": "DEADCODE",
    "@typescript-eslint/": "TYPES",
    "react/": "QUALITY",
    "react-hooks/": "BUGPRONE",
    "import/": "IMPORTS",
    "jsx-a11y/": "ACCESSIBILITY",
    "sonarjs/": "QUALITY",
    "unicorn/": "QUALITY",
    "promise/": "BUGPRONE",
    "node/": "QUALITY",
    "n/": "QUALITY",
}


def get_eslint_category(rule_id: str | None) -> str:
    """ESLint rule ID se category nikalo."""
    if not rule_id:
        return "QUALITY"
    for prefix, cat in ESLINT_CATEGORY_MAP.items():
        if rule_id.startswith(prefix) or rule_id == prefix:
            return cat
    return "QUALITY"


def get_eslint_severity(eslint_severity: int) -> str:
    """ESLint severity (1=warn, 2=error) se Lyncus severity."""
    return "critical" if eslint_severity == 2 else "warning"


# ── NPM AUDIT PARSER ──────────────────────────────────────────────────────────

NPM_AUDIT_SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "critical",
    "moderate": "warning",
    "low": "info",
    "info": "info",
}


def parse_npm_audit_json(json_output: str) -> list[dict[str, Any]]:
    """npm audit --json output parse karo."""
    vulnerabilities = []
    try:
        data = json.loads(json_output)

        # npm audit v2 format
        vulns = data.get("vulnerabilities", {})
        for pkg_name, vuln_data in vulns.items():
            severity = vuln_data.get("severity", "unknown")
            via = vuln_data.get("via", [])

            # Direct vulnerabilities (not just transitive)
            direct_via = [v for v in via if isinstance(v, dict)]
            if not direct_via:
                continue

            for v in direct_via:
                vulnerabilities.append(
                    {
                        "package": pkg_name,
                        "severity": NPM_AUDIT_SEVERITY_MAP.get(severity, "warning"),
                        "title": v.get("title", "Unknown vulnerability"),
                        "cve": v.get("cve", ""),
                        "url": v.get("url", ""),
                        "fixed_in": (
                            vuln_data.get("fixAvailable", {}).get("version", "")
                            if isinstance(vuln_data.get("fixAvailable"), dict)
                            else ""
                        ),
                        "description": f"{pkg_name}: {v.get('title', '')}",
                    }
                )

    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        pass

    return vulnerabilities


# ── TSC OUTPUT PARSER ─────────────────────────────────────────────────────────


def parse_tsc_output(output: str) -> list[dict[str, Any]]:
    """TypeScript compiler output parse karo."""
    return [
        issue
        for raw_line in output.splitlines()
        if (issue := _parse_tsc_line(raw_line)) is not None
    ]


def _parse_tsc_line(raw_line: str) -> dict[str, Any] | None:
    location, separator, diagnostic = raw_line.rpartition("): ")
    if not separator:
        return None
    file, separator, coordinates = location.rpartition("(")
    if not separator:
        return None
    line, separator, column = coordinates.partition(",")
    if not separator or not line.isdigit() or not column.isdigit():
        return None
    level, separator, diagnostic = diagnostic.partition(" ")
    if not separator or level not in ("error", "warning"):
        return None
    code, separator, message = diagnostic.partition(": ")
    if not separator or not code.startswith("TS") or not code[2:].isdigit():
        return None
    return {
        "file": file.strip(),
        "line": int(line),
        "column": int(column),
        "severity": "critical" if level == "error" else "warning",
        "rule_id": code,
        "message": message.strip(),
        "category": "TYPE",
    }


# ── TS-PRUNE PARSER ───────────────────────────────────────────────────────────


def parse_ts_prune_output(output: str) -> list[dict[str, Any]]:
    """ts-prune output parse karo."""
    issues = []
    # Format: src/file.ts:45 - functionName (used in module)
    for raw_line in output.splitlines():
        location, separator, name = raw_line.partition(" - ")
        if not separator:
            continue
        file, separator, line = location.rpartition(":")
        if not separator or not line.isdigit():
            continue
        name = name.strip()
        context = None
        if name.endswith(")") and " (" in name:
            name, context = name.rsplit(" (", 1)
            context = context[:-1]
        # "used in module" ignore karo — ye actually used hai
        if context and "used in module" in context:
            continue
        issues.append(
            {
                "file": file.strip(),
                "line": int(line),
                "column": 0,
                "severity": "warning",
                "rule_id": "TS-PRUNE",
                "message": f"Unused export: '{name.strip()}'",
                "category": "DEADCODE",
            }
        )
    return issues


# ── DEPCHECK PARSER ───────────────────────────────────────────────────────────


def parse_depcheck_json(json_output: str) -> list[dict[str, Any]]:
    """depcheck --json output parse karo."""
    issues = []
    try:
        data = json.loads(json_output)

        # Unused dependencies
        for dep in data.get("dependencies", []):
            issues.append(
                {
                    "file": _PACKAGE_JSON,
                    "line": 0,
                    "column": 0,
                    "severity": "warning",
                    "rule_id": "DEPCHECK-UNUSED",
                    "message": f"Unused dependency: '{dep}' — {_PACKAGE_JSON} se remove karo",
                    "category": "DEADCODE",
                }
            )

        # Missing dependencies (used but not in package.json)
        for dep, usages in data.get("missing", {}).items():
            issues.append(
                {
                    "file": usages[0] if usages else "unknown",
                    "line": 0,
                    "column": 0,
                    "severity": "critical",
                    "rule_id": "DEPCHECK-MISSING",
                    "message": f"Missing dependency: '{dep}' use ho raha hai but package.json mein nahi",
                    "category": "QUALITY",
                }
            )

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


# ── PACKAGE.JSON FINDER ───────────────────────────────────────────────────────


def find_package_json(project_path: str) -> str | None:
    """package.json wala folder dhundo."""
    path = Path(project_path)

    if (path / _PACKAGE_JSON).exists():
        return str(path)

    if path.is_file():
        parent = path.parent
        if (parent / _PACKAGE_JSON).exists():
            return str(parent)

    for pkg in path.rglob(_PACKAGE_JSON):
        if "node_modules" not in str(pkg):
            return str(pkg.parent)

    return None


def is_typescript_project(project_path: str) -> bool:
    """Project TypeScript hai ya nahi check karo."""
    path = Path(project_path)
    return (path / "tsconfig.json").exists() or any(path.rglob("*.ts")) or any(path.rglob("*.tsx"))


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────


def get_js_tools(
    only: str | None = None,
    skip_slow: bool = False,
    is_typescript: bool = False,
) -> list[JsToolConfig]:
    """
    JS/TS tools ki filtered list.

    Args:
        only: quality / security / deadcode / coverage / faketests
        skip_slow: stryker-js skip karo (bahut slow)
        is_typescript: TS-only tools include karo
    """
    tools = JS_TOOLS.copy()

    if not is_typescript:
        tools = [t for t in tools if not t.typescript_only]

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"stryker-js", "c8"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in JS_TOOLS}
