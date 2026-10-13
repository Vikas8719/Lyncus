"""
Kotlin Language Checks — detekt, ktlint, kotlin-compiler
Android aur JVM Kotlin projects ke liye.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"


@dataclass
class KotlinToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_gradle: bool = False


KOTLIN_TOOLS: list[KotlinToolConfig] = [
    KotlinToolConfig(
        name="detekt",
        command=[
            "detekt",
            "--input",
            _PATH_ARGUMENT,
            "--report",
            "xml:{tmpdir}/detekt_report.xml",
            "--report",
            "txt:{tmpdir}/detekt_report.txt",
        ],
        check_type="quality",
        output_format="xml",
        description="Kotlin static analysis — code smells, complexity, style",
        min_version="1.23.6",
        install_cmd=(
            "# Gradle (recommended):\n"
            'plugins { id("io.gitlab.arturbosch.detekt") version "1.23.6" }\n'
            "# CLI:\n"
            "curl -sSLO https://github.com/detekt/detekt/releases/download/v1.23.6/"
            "detekt-cli-1.23.6-all.jar"
        ),
    ),
    KotlinToolConfig(
        name="ktlint",
        command=[
            "ktlint",
            f"{_PATH_ARGUMENT}/**/*.kt",
            "--reporter=json,output={tmpdir}/ktlint_report.json",
        ],
        check_type="quality",
        output_format="json",
        description="Kotlin code style enforcer — official Kotlin coding conventions",
        min_version="1.3.1",
        install_cmd=(
            "# macOS:\nbrew install ktlint\n"
            "# Linux:\ncurl -sSLO https://github.com/pinterest/ktlint/releases/download/"
            "1.3.1/ktlint && chmod +x ktlint && sudo mv ktlint /usr/local/bin/"
        ),
    ),
    KotlinToolConfig(
        name="kotlin-compiler",
        command=[
            "kotlinc",
            _PATH_ARGUMENT,
            "-nowarn",
            "-d",
            "{tmpdir}/Lyncus_kotlin_out.jar",
        ],
        check_type="quality",
        output_format="text",
        description="Kotlin compiler warnings — type errors, deprecation",
        min_version="2.0.0",
        install_cmd=(
            "# macOS: brew install kotlin\n"
            "# Linux: snap install kotlin --classic\n"
            "# Windows: choco install kotlinc"
        ),
    ),
    KotlinToolConfig(
        name="android-lint",
        command=[
            "./gradlew",
            "lint",
            "--stacktrace",
        ],
        check_type="quality",
        output_format="xml",
        description="Android Lint — Android-specific issues, performance, security",
        min_version="8.5.0",
        install_cmd="Android Gradle Plugin 8.5+ (build.gradle mein automatic)",
        needs_gradle=True,
    ),
]


# ── DETEKT XML PARSER ─────────────────────────────────────────────────────────


def parse_detekt_xml(xml_path: str) -> list[dict[str, Any]]:
    from defusedxml import ElementTree as ET

    issues: list[dict[str, Any]] = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        if root is None:
            return issues
        for file_elem in root.findall(".//file"):
            file_path = file_elem.get("name", "")
            for error in file_elem.findall("error"):
                line = int(error.get("line", "0"))
                col = int(error.get("column", "0") or "0")
                sev = error.get("severity", "warning")
                msg = error.get("message", "")
                source = error.get("source", "")
                rule_id = source.split(".")[-1] if source else "DETEKT"
                issues.append(
                    {
                        "file": file_path,
                        "line": line,
                        "column": col,
                        "severity": _kotlin_severity(sev),
                        "rule_id": f"DK-{rule_id}",
                        "message": msg,
                        "category": _detekt_category(source),
                    }
                )
    except Exception:
        pass
    return issues


def _kotlin_severity(sev: str) -> str:
    return {"error": "critical", "warning": "warning", "info": "info"}.get(sev, "warning")


def _detekt_category(source: str) -> str:
    src = source.lower()
    if "complexity" in src:
        return "COMPLEXITY"
    if "security" in src:
        return "SECURITY"
    if "performance" in src:
        return "PERF"
    if "naming" in src:
        return "NAMING"
    if "style" in src:
        return "STYLE"
    if "unused" in src or "dead" in src:
        return "DEADCODE"
    if "exception" in src or "coroutine" in src:
        return "BUGPRONE"
    return "QUALITY"


# ── KTLINT JSON PARSER ────────────────────────────────────────────────────────


def parse_ktlint_json(json_output: str) -> list[dict[str, Any]]:
    issues = []
    try:
        data = json.loads(json_output)
        for file_data in data:
            file_path = file_data.get("file", "")
            for error in file_data.get("errors", []):
                issues.append(
                    {
                        "file": file_path,
                        "line": error.get("line", 0),
                        "column": error.get("col", 0),
                        "severity": "warning",
                        "rule_id": f"KT-{error.get('rule', 'STYLE')}",
                        "message": error.get("message", ""),
                        "category": "STYLE",
                    }
                )
    except (json.JSONDecodeError, KeyError):
        pass
    return issues


# ── PROJECT DETECTION ─────────────────────────────────────────────────────────

KOTLIN_EXTENSIONS = {".kt", ".kts"}


def is_kotlin_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in KOTLIN_EXTENSIONS


def find_kotlin_root(project_path: str) -> str | None:
    path = Path(project_path)
    if (path / "build.gradle.kts").exists() or (path / "build.gradle").exists():
        return str(path)
    for f in path.rglob("build.gradle.kts"):
        return str(f.parent)
    return None


def get_kotlin_tools(only: str | None = None, skip_slow: bool = False) -> list[KotlinToolConfig]:
    tools = KOTLIN_TOOLS.copy()
    if only:
        tools = [t for t in tools if t.check_type == only]
    if skip_slow:
        tools = [t for t in tools if t.name not in {"android-lint"}]
    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in KOTLIN_TOOLS}
