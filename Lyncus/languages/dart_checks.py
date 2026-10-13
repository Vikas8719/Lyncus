"""
Dart / Flutter Language Checks — dart analyze, flutter analyze, dart_code_metrics
Dart aur Flutter dono support karta hai.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"
_PUBSPEC_FILE = "pubspec.yaml"


@dataclass
class DartToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    flutter_only: bool = False


DART_TOOLS: list[DartToolConfig] = [

    DartToolConfig(
        name="dart-analyze",
        command=[
            "dart", "analyze",
            "--format", "machine",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="text",
        description="Dart static analyzer — type errors, lint rules, best practices",
        min_version="3.4.0",
        install_cmd="https://dart.dev/get-dart se Dart SDK install karo",
    ),

    DartToolConfig(
        name="flutter-analyze",
        command=[
            "flutter", "analyze",
            "--no-pub",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="text",
        description="Flutter analyzer — Dart + Flutter-specific lint rules",
        min_version="3.22.0",
        install_cmd="https://flutter.dev/docs/get-started/install",
        flutter_only=True,
    ),

    DartToolConfig(
        name="dart-fix",
        command=[
            "dart", "fix",
            "--dry-run",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="text",
        description="Auto-fixable issues — counts problems that can be auto-corrected",
        min_version="3.4.0",
        install_cmd="Dart SDK built-in",
    ),

    DartToolConfig(
        name="dart-test",
        command=[
            "dart", "test",
            "--coverage", "{tmpdir}/dart_coverage",
            _PATH_ARGUMENT,
        ],
        check_type="coverage",
        output_format="text",
        description="Test coverage measurement",
        min_version="3.4.0",
        install_cmd="dart pub add dev:coverage",
    ),
]


# ── DART MACHINE FORMAT PARSER ────────────────────────────────────────────────
# Format: SEVERITY|TYPE|ERROR_CODE|FILE_PATH|LINE|COL|LENGTH|MESSAGE

def parse_dart_analyze_output(output: str) -> list[dict[str, Any]]:
    issues = []
    for line in output.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 8:
            sev, _, code, file_path, line_num, col, _, message = parts[:8]
            issues.append({
                "file":     file_path.strip(),
                "line":     int(line_num) if line_num.isdigit() else 0,
                "column":   int(col) if col.isdigit() else 0,
                "severity": _dart_severity(sev.strip()),
                "rule_id":  f"DART-{code.strip()}",
                "message":  message.strip(),
                "category": _dart_category(code.strip()),
            })
    return issues


def _dart_severity(sev: str) -> str:
    return {"ERROR": "critical", "WARNING": "warning", "INFO": "info"}.get(sev.upper(), "warning")


def _dart_category(code: str) -> str:
    code_lower = code.lower()
    if "import" in code_lower:
        return "IMPORTS"
    if "unused" in code_lower or "dead" in code_lower:
        return "DEADCODE"
    if "type" in code_lower or "cast" in code_lower:
        return "TYPE"
    if "null" in code_lower:
        return "BUGPRONE"
    return "QUALITY"


# ── PROJECT DETECTION ─────────────────────────────────────────────────────────

DART_EXTENSIONS = {".dart"}


def is_dart_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in DART_EXTENSIONS


def is_flutter_project(project_path: str) -> bool:
    path = Path(project_path)
    pubspec = path / _PUBSPEC_FILE
    if not pubspec.exists():
        return False
    content = pubspec.read_text(encoding="utf-8", errors="ignore")
    return "flutter:" in content or "flutter_test:" in content


def find_dart_root(project_path: str) -> str | None:
    path = Path(project_path)
    if (path / _PUBSPEC_FILE).exists():
        return str(path)
    for f in path.rglob(_PUBSPEC_FILE):
        return str(f.parent)
    return None


def get_dart_tools(
    only: str | None = None,
    skip_slow: bool = False,
    is_flutter: bool = False,
) -> list[DartToolConfig]:
    tools = DART_TOOLS.copy()
    if not is_flutter:
        tools = [t for t in tools if not t.flutter_only]
    if only:
        tools = [t for t in tools if t.check_type == only]
    if skip_slow:
        tools = [t for t in tools if t.name not in {"dart-test"}]
    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in DART_TOOLS}
