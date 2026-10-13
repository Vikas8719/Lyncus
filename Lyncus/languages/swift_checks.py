"""
Swift Language Checks — swiftlint, periphery, swift compiler
iOS/macOS/SPM projects ke liye.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"


@dataclass
class SwiftToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_xcode: bool = False


SWIFT_TOOLS: list[SwiftToolConfig] = [

    SwiftToolConfig(
        name="swiftlint",
        command=[
            "swiftlint",
            "lint",
            "--path", _PATH_ARGUMENT,
            "--reporter", "json",
            "--quiet",
        ],
        check_type="quality",
        output_format="json",
        description="Swift style and conventions — 200+ rules",
        min_version="0.56.2",
        install_cmd=(
            "# macOS:\nbrew install swiftlint\n"
            "# SPM:\n.package(url: \"https://github.com/realm/SwiftLint\", from: \"0.56.0\")"
        ),
    ),

    SwiftToolConfig(
        name="periphery",
        command=[
            "periphery", "scan",
            "--project",             _PATH_ARGUMENT,
            "--format", "json",
            "--quiet",
            "--skip-build",
        ],
        check_type="deadcode",
        output_format="json",
        description="Dead code detector — unused types, functions, imports",
        min_version="2.21.1",
        install_cmd=(
            "# macOS:\nbrew install peripheryapp/periphery/periphery\n"
            "# SPM: .package(url: \"https://github.com/peripheryapp/periphery\", from: \"2.21.0\")"
        ),
        needs_xcode=True,
    ),

    SwiftToolConfig(
        name="swift-build",
        command=[
            "swift", "build",
            "--package-path",             _PATH_ARGUMENT,
            "-Xswiftc", "-warnings-as-errors",
        ],
        check_type="quality",
        output_format="text",
        description="Swift compiler warnings — type errors, deprecations",
        min_version="5.10",
        install_cmd="Xcode ya Swift toolchain install karo",
    ),
]


# ── SWIFTLINT JSON PARSER ─────────────────────────────────────────────────────

def parse_swiftlint_json(json_output: str) -> list[dict[str, Any]]:
    issues = []
    try:
        data = json.loads(json_output)
        for item in data:
            sev = item.get("severity", "Warning")
            issues.append({
                "file":     item.get("file", ""),
                "line":     item.get("line", 0),
                "column":   item.get("character", 0),
                "severity": "critical" if sev == "Error" else "warning",
                "rule_id":  f"SW-{item.get('rule_id', 'STYLE').upper()}",
                "message":  item.get("reason", ""),
                "category": _swiftlint_category(item.get("type", "")),
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return issues


def _swiftlint_category(rule_type: str) -> str:
    cat_map = {
        "Idiomatic":   "STYLE",
        "Style":       "STYLE",
        "Lint":        "QUALITY",
        "Performance": "PERF",
        "Metrics":     "COMPLEXITY",
    }
    return cat_map.get(rule_type, "QUALITY")


# ── PERIPHERY JSON PARSER ─────────────────────────────────────────────────────

def parse_periphery_json(json_output: str) -> list[dict[str, Any]]:
    issues = []
    try:
        data = json.loads(json_output)
        for item in data:
            location = item.get("location", {})
            issues.append({
                "file":     location.get("file", ""),
                "line":     location.get("line", 0),
                "column":   location.get("column", 0),
                "severity": "warning",
                "rule_id":  "SW-DEAD-CODE",
                "message":  item.get("message", "Unused declaration"),
                "category": "DEADCODE",
            })
    except (json.JSONDecodeError, KeyError):
        pass
    return issues


# ── PROJECT DETECTION ─────────────────────────────────────────────────────────

SWIFT_EXTENSIONS = {".swift"}


def is_swift_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in SWIFT_EXTENSIONS


def find_swift_root(project_path: str) -> str | None:
    path = Path(project_path)
    if (path / "Package.swift").exists():
        return str(path)
    for f in path.rglob("Package.swift"):
        return str(f.parent)
    for f in path.rglob("*.xcodeproj"):
        return str(f.parent)
    return None


def get_swift_tools(only: str | None = None, skip_slow: bool = False) -> list[SwiftToolConfig]:
    tools = SWIFT_TOOLS.copy()
    if only:
        tools = [t for t in tools if t.check_type == only]
    if skip_slow:
        tools = [t for t in tools if t.name not in {"periphery"}]
    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in SWIFT_TOOLS}
