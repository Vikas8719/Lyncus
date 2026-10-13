"""
Lyncus/core/sarif.py
SARIF 2.1.0 output exporter — GitHub Advanced Security ke saath kaam karta hai.
SARIF = Static Analysis Results Interchange Format
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Lyncus.core.parser import Problem

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)

Lyncus_VERSION = "1.0.0"
Lyncus_URI = "https://github.com/yourname/Lyncus"


def _severity_to_sarif(severity: str) -> str:
    """Lyncus severity → SARIF level."""
    return {
        "critical": "error",
        "warning": "warning",
        "info": "note",
    }.get(severity, "warning")


def _make_rule(problem: Problem) -> dict[str, Any]:
    """Ek SARIF rule entry banao."""
    return {
        "id": problem.rule_id,
        "name": problem.rule_id.replace("-", "").replace("_", ""),
        "shortDescription": {"text": f"{problem.category}: {problem.rule_id}"},
        "fullDescription": {"text": problem.message},
        "helpUri": f"{Lyncus_URI}/docs/rules#{problem.rule_id.lower()}",
        "properties": {
            "tags": [problem.category.lower(), problem.tool],
            "severity": problem.severity,
        },
    }


def export_sarif(
    problems: list[Problem],
    project_path: str,
    language: str,
    scan_time: float,
    output_file: str = "Lyncus-report.sarif",
) -> None:
    """
    SARIF 2.1.0 file export karo.
    GitHub Actions mein upload kar sakte ho:
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: Lyncus-report.sarif
    """
    project_root = Path(project_path).resolve()

    # Unique rules collect karo
    rules_map: dict[str, dict[str, Any]] = {}
    for p in problems:
        if p.rule_id not in rules_map:
            rules_map[p.rule_id] = _make_rule(p)

    # Results
    results = []
    for p in problems:
        # File URI — relative to project root
        try:
            rel_path = Path(p.file).resolve().relative_to(project_root)
            uri = str(rel_path).replace("\\", "/")
        except (ValueError, OSError):
            uri = p.file.replace("\\", "/")

        result: dict[str, Any] = {
            "ruleId": p.rule_id,
            "level": _severity_to_sarif(p.severity),
            "message": {"text": p.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": uri,
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": max(1, p.line),
                            "startColumn": max(1, p.column) if p.column else 1,
                        },
                    }
                }
            ],
            "properties": {
                "tool": p.tool,
                "category": p.category,
                "severity": p.severity,
            },
        }

        # Suggestion agar hai
        if p.suggestion:
            result["fixes"] = [
                {
                    "description": {"text": p.suggestion},
                    "artifactChanges": [],
                }
            ]

        results.append(result)

    sarif_doc = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Lyncus",
                        "version": Lyncus_VERSION,
                        "informationUri": Lyncus_URI,
                        "shortDescription": {"text": "Multi-language code quality scanner"},
                        "rules": list(rules_map.values()),
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "startTimeUtc": datetime.now(UTC).isoformat(),
                        "endTimeUtc": datetime.now(UTC).isoformat(),
                        "toolExecutionNotices": [],
                        "properties": {
                            "language": language,
                            "scan_time_sec": round(scan_time, 2),
                            "project_path": str(project_root),
                        },
                    }
                ],
                "originalUriBaseIds": {
                    "%SRCROOT%": {
                        "uri": project_root.as_uri() + "/",
                    }
                },
                "results": results,
                "properties": {
                    "Lyncus_version": Lyncus_VERSION,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        ],
    }

    Path(output_file).write_text(
        json.dumps(sarif_doc, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
