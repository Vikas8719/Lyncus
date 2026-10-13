"""
C# Language Checks — dotnet format, Roslyn, StyleCop, Stryker, security-scan, coverlet
.NET 8+ ke liye optimized. .csproj / .sln detect karke tools chalata hai.
"""

from __future__ import annotations

import json
from defusedxml import ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"

# Named constants — magic numbers nahi
_STRYKER_MIN_MUTATION_THRESHOLD = 60   # Stryker mutation score CI fail threshold (%)
_COVERLET_VERSION = "6.0.0"           # Coverlet collector version


@dataclass
class CSharpToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_build: bool = False    # dotnet build pehle chahiye


# ── C# TOOL DEFINITIONS ───────────────────────────────────────────────────────

CSHARP_TOOLS: list[CSharpToolConfig] = [

    CSharpToolConfig(
        name="dotnet-format",
        command=[
            "dotnet", "format",
            "--verify-no-changes",
            "--report", "{tmpdir}/dotnet_format_report.json",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="json",
        description="Official .NET formatter — style aur formatting issues",
        min_version=".NET 8.0",
        install_cmd="dotnet tool install -g dotnet-format",
    ),

    CSharpToolConfig(
        name="dotnet-build-warnings",
        command=[
            "dotnet", "build",
            _PATH_ARGUMENT,
            "--nologo",
            "-v", "minimal",
            "/p:TreatWarningsAsErrors=false",
        ],
        check_type="quality",
        output_format="text",
        description="Roslyn compiler warnings — type errors, nullable warnings, unused vars",
        min_version=".NET 8.0",
        install_cmd="# .NET SDK install karo: https://dotnet.microsoft.com/download",
        needs_build=True,
    ),

    CSharpToolConfig(
        name="dotnet-security-scan",
        command=[
            "security-scan",
            _PATH_ARGUMENT,
            "--export",
            "--no-banner",
        ],
        check_type="security",
        output_format="text",
        description="Security vulnerability scanner — SQL injection, XSS, hardcoded secrets",
        min_version="5.6.7",
        install_cmd="dotnet tool install -g security-scan",
    ),

    CSharpToolConfig(
        name="stryker",
        command=[
            "dotnet-stryker",
            "--project", _PATH_ARGUMENT,
            "--reporter", "json",
            "--output-path", "{tmpdir}/stryker_output",
            "--threshold-break", str(_STRYKER_MIN_MUTATION_THRESHOLD),
        ],
        check_type="faketests",
        output_format="json",
        description="Mutation testing — fake/weak tests pakadta hai",
        min_version="3.13.0",
        install_cmd="dotnet tool install -g dotnet-stryker",
    ),

    CSharpToolConfig(
        name="coverlet",
        command=[
            "dotnet", "test",
            _PATH_ARGUMENT,
            "--collect", "XPlat Code Coverage",
            "--results-directory", "{tmpdir}/coverage",
            "--",
            "DataCollectionRunSettings.DataCollectors.DataCollector.Configuration.Format=cobertura",
        ],
        check_type="coverage",
        output_format="xml",
        description="Code coverage — line, branch, method coverage (Cobertura format)",
        min_version="6.0.0",
        install_cmd=f"dotnet add package coverlet.collector --version {_COVERLET_VERSION}",
    ),

    CSharpToolConfig(
        name="roslynator",
        command=[
            "roslynator", "analyze",
            _PATH_ARGUMENT,
            "--output", "{tmpdir}/roslynator_out.xml",
            "--format", "xml",
        ],
        check_type="quality",
        output_format="xml",
        description="Roslyn-based analyzer — 500+ code quality rules",
        min_version="0.8.10",
        install_cmd="dotnet tool install -g roslynator.dotnet.cli",
    ),
]


# ── DOTNET FORMAT JSON PARSER ─────────────────────────────────────────────────

def parse_dotnet_format_json(json_output: str) -> list[dict[str, Any]]:
    """dotnet format --report JSON output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        # Format: list of {DocumentId, FilePath, FileChanges: [{LineNumber, CharNumber, DiagnosticId, FormatDescription}]}
        for doc in data:
            file_path = doc.get("FilePath", "")
            for change in doc.get("FileChanges", []):
                issues.append({
                    "file":     file_path,
                    "line":     change.get("LineNumber", 0),
                    "column":   change.get("CharNumber", 0),
                    "severity": "info",
                    "rule_id":  f"FMT-{change.get('DiagnosticId', 'STYLE')}",
                    "message":  change.get("FormatDescription", "Formatting issue"),
                    "category": "STYLE",
                })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


# ── DOTNET BUILD WARNINGS PARSER ──────────────────────────────────────────────

def parse_dotnet_build_output(output: str) -> list[dict[str, Any]]:
    """dotnet build output se warnings/errors parse karo."""
    return [
        issue
        for raw_line in output.splitlines()
        if (issue := _parse_dotnet_build_line(raw_line)) is not None
    ]


def _parse_dotnet_build_line(raw_line: str) -> dict[str, Any] | None:
    location, separator, diagnostic = raw_line.rpartition("): ")
    if not separator:
        return None
    file, separator, coordinates = location.rpartition("(")
    if not separator:
        return None
    line, separator, col = coordinates.partition(",")
    if not separator or not line.isdigit() or not col.isdigit():
        return None
    level, separator, diagnostic = diagnostic.partition(" ")
    if not separator or level not in ("error", "warning"):
        return None
    code, separator, msg = diagnostic.partition(": ")
    if not separator:
        return None
    if not _is_valid_dotnet_code(code):
        return None
    if msg.endswith("]") and " [" in msg:
        msg = msg.rpartition(" [")[0]
    return {
        "file":     file.strip().replace("\\", "/"),
        "line":     int(line),
        "column":   int(col),
        "severity": "critical" if level == "error" else "warning",
        "rule_id":  f"CS-{code}",
        "message":  msg.strip(),
        "category": _cs_category(code),
    }


def _is_valid_dotnet_code(code: str) -> bool:
    prefix = code.rstrip("0123456789")
    suffix = code[len(prefix):]
    return (
        prefix.isalpha()
        and prefix.isupper()
        and (prefix != "CS" or bool(suffix))
        and (not suffix or suffix.isdigit())
    )


def _cs_category(code: str) -> str:
    """C# diagnostic code se category."""
    # CS0 series = compiler errors
    # CS1 series = language features
    # CS8 series = nullable/pattern matching
    if code.startswith("CS8"):
        return "NULLABLE"
    if code.startswith(("CS0168", "CS0219")):
        return "DEADCODE"
    if code.startswith("SA"):
        return "STYLE"
    if code.startswith("CA"):
        return "QUALITY"
    if code.startswith("S"):
        return "SECURITY"
    return "QUALITY"


# ── STRYKER JSON PARSER ────────────────────────────────────────────────────────

def parse_stryker_json(json_path: str) -> dict[str, Any]:
    """Stryker mutation testing result parse karo."""
    result: dict[str, Any] = {
        "mutation_score": None,
        "killed": 0,
        "survived": 0,
        "timeout": 0,
        "total": 0,
        "survived_mutants": [],
    }

    try:
        with open(json_path) as f:
            data = json.load(f)

        files = data.get("files", {})
        total_killed = 0
        total_survived = 0
        total_timeout = 0

        for file_path, file_data in files.items():
            for mutant in file_data.get("mutants", []):
                status = mutant.get("status", "")
                if status == "Killed":
                    total_killed += 1
                elif status == "Survived":
                    total_survived += 1
                    # Survived mutants = problem
                    result["survived_mutants"].append({
                        "file":        file_path,
                        "line":        mutant.get("location", {}).get("start", {}).get("line", 0),
                        "mutator":     mutant.get("mutatorName", ""),
                        "original":    mutant.get("originalLine", ""),
                        "replacement": mutant.get("replacement", ""),
                    })
                elif status == "Timeout":
                    total_timeout += 1

        total = total_killed + total_survived + total_timeout
        result.update({
            "killed":  total_killed,
            "survived": total_survived,
            "timeout": total_timeout,
            "total":   total,
            "mutation_score": round((total_killed / total * 100) if total > 0 else 0, 2),
        })

    except (json.JSONDecodeError, OSError, KeyError):
        pass

    return result


# ── COVERLET COBERTURA PARSER ─────────────────────────────────────────────────

def parse_coverlet_xml(xml_path: str) -> dict[str, Any]:
    """Coverlet Cobertura XML report parse karo."""
    result: dict[str, Any] = {
        "line_rate":   None,
        "branch_rate": None,
        "packages":    [],
    }

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        result["line_rate"]   = round(float(root.get("line-rate", 0)) * 100, 2)
        result["branch_rate"] = round(float(root.get("branch-rate", 0)) * 100, 2)

        for package in root.findall(".//package"):
            result["packages"].append({
                "name":        package.get("name", ""),
                "line_rate":   round(float(package.get("line-rate", 0)) * 100, 2),
                "branch_rate": round(float(package.get("branch-rate", 0)) * 100, 2),
            })

    except (ET.ParseError, OSError, ValueError):
        pass

    return result


# ── ROSLYNATOR XML PARSER ──────────────────────────────────────────────────────

def parse_roslynator_xml(xml_output: str) -> list[dict[str, Any]]:
    """Roslynator XML analyze output parse karo."""
    issues = []

    try:
        root = ET.fromstring(xml_output)

        for diag in root.findall(".//Diagnostic"):
            file_path = diag.findtext("FilePath", "")
            line      = int(diag.findtext("Line", "0") or "0")
            col       = int(diag.findtext("Column", "0") or "0")
            id_       = diag.findtext("Id", "")
            severity  = diag.findtext("Severity", "warning").lower()
            message   = diag.findtext("Message", "")

            issues.append({
                "file":     file_path,
                "line":     line,
                "column":   col,
                "severity": "critical" if severity == "error" else severity,
                "rule_id":  f"ROS-{id_}",
                "message":  message,
                "category": "QUALITY",
            })

    except ET.ParseError:
        pass

    return issues


# ── PROJECT DETECTION ─────────────────────────────────────────────────────────

CSHARP_EXTENSIONS = {".cs", ".cshtml", ".razor"}


def is_csharp_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in CSHARP_EXTENSIONS


def find_csharp_files(project_path: str) -> list[str]:
    """Project mein sab .cs files dhundo — generated code ignore karo."""
    path = Path(project_path)
    ignore_dirs = {"obj", "bin", "generated", ".vs", "packages", "node_modules"}

    cs_files = []
    for cs_file in path.rglob("*.cs"):
        parts = set(cs_file.parts)
        if not parts.intersection(ignore_dirs):
            cs_files.append(str(cs_file))

    return cs_files


def detect_dotnet_project(project_path: str) -> dict[str, Any]:
    """
    .NET project type detect karo.
    Returns: {"type": "solution|project|none", "files": [...], "target_framework": str}
    """
    path = Path(project_path)

    # Solution file
    sln_files = list(path.glob("*.sln"))
    if sln_files:
        return {
            "type": "solution",
            "files": [str(f) for f in sln_files],
            "target_framework": _detect_framework(str(sln_files[0])),
        }

    # Project file
    csproj_files = list(path.rglob("*.csproj"))
    ignore_dirs = {"obj", "bin", "packages"}
    csproj_files = [
        f for f in csproj_files
        if not any(d in str(f) for d in ignore_dirs)
    ]

    if csproj_files:
        return {
            "type": "project",
            "files": [str(f) for f in csproj_files],
            "target_framework": _detect_framework(str(csproj_files[0])),
        }

    return {"type": "none", "files": [], "target_framework": ""}


def _detect_framework(csproj_path: str) -> str:
    """Target framework .csproj se nikalo."""
    try:
        tree = ET.parse(csproj_path)
        root = tree.getroot()
        tf = root.findtext(".//TargetFramework") or root.findtext(".//TargetFrameworks", "")
        return tf.split(";")[0].strip() if tf else ""
    except (ET.ParseError, OSError):
        return ""


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_csharp_tools(
    only: str | None = None,
    skip_slow: bool = False,
) -> list[CSharpToolConfig]:
    tools = CSHARP_TOOLS.copy()

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"stryker", "coverlet"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in CSHARP_TOOLS}
