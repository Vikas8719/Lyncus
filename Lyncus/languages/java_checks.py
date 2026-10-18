"""
Java Language Checks — checkstyle, spotbugs, find-sec-bugs, pitest, jacoco, pmd
Maven aur Gradle dono support karta hai. pom.xml ya build.gradle detect karke tools chalata hai.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET

_PATH_ARGUMENT = "{path}"
_POM_FILE = "pom.xml"
_GRADLE_FILE = "build.gradle"


@dataclass
class JavaToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_build_file: bool = True   # pom.xml ya build.gradle chahiye
    build_tool: str = "any"         # maven / gradle / any


# ── JAVA TOOL DEFINITIONS ─────────────────────────────────────────────────────

JAVA_TOOLS: list[JavaToolConfig] = [

    JavaToolConfig(
        name="checkstyle",
        command=[
            "java", "-jar", "{checkstyle_jar}",
            "-c", "/google_checks.xml",
            "-f", "xml",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="xml",
        description="Code style checker — Google/Sun Java conventions enforce karta hai",
        min_version="10.17.0",
        install_cmd=(
            "# Jar download karo:\n"
            "wget https://github.com/checkstyle/checkstyle/releases/download/"
            "checkstyle-10.17.0/checkstyle-10.17.0-all.jar"
        ),
    ),

    JavaToolConfig(
        name="spotbugs",
        command=[
            "spotbugs",
            "-textui",
            "-xml",
            "-output", "{tmpdir}/spotbugs_out.xml",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="xml",
        description="Bytecode static analysis — null pointers, infinite loops, bad practices",
        min_version="4.8.6",
        install_cmd=(
            "# Maven:\n"
            "<plugin><groupId>com.github.spotbugs</groupId>"
            "<artifactId>spotbugs-maven-plugin</artifactId>"
            "<version>4.8.6.4</version></plugin>\n"
            "# Gradle: id 'com.github.spotbugs' version '6.0.18'"
        ),
        build_tool="any",
    ),

    JavaToolConfig(
        name="pmd",
        command=[
            "pmd",
            "check",
            "-d", _PATH_ARGUMENT,
            "-R", "rulesets/java/quickstart.xml",
            "-f", "xml",
            "--no-fail-on-violation",
        ],
        check_type="quality",
        output_format="xml",
        description="Static analysis — dead code, design issues, complexity, optimizations",
        min_version="7.3.0",
        install_cmd="# Download: https://github.com/pmd/pmd/releases\n# macOS: brew install pmd",
    ),

    JavaToolConfig(
        name="find-sec-bugs",
        command=[
            "spotbugs",
            "-textui",
            "-xml",
            "-output", "{tmpdir}/findsecbugs_out.xml",
            "-pluginList", "{findsecbugs_jar}",
            _PATH_ARGUMENT,
        ],
        check_type="security",
        output_format="xml",
        description="Security scanner — OWASP Top 10, injection flaws, crypto misuse",
        min_version="1.13.0",
        install_cmd=(
            "# Maven plugin mein add karo:\n"
            "<plugin>com.h3xstream.findsecbugs:findsecbugs-plugin:1.13.0</plugin>"
        ),
    ),

    JavaToolConfig(
        name="pitest",
        command=[
            "mvn", "org.pitest:pitest-maven:mutationCoverage",
            "-DoutputFormats=JSON",
        ],
        check_type="faketests",
        output_format="json",
        description="Mutation testing — weak/fake tests pakadta hai",
        min_version="1.16.1",
        install_cmd=(
            "# Maven pom.xml mein:\n"
            "<plugin><groupId>org.pitest</groupId>"
            "<artifactId>pitest-maven</artifactId>"
            "<version>1.16.1</version></plugin>"
        ),
        build_tool="maven",
    ),

    JavaToolConfig(
        name="jacoco",
        command=[
            "mvn", "jacoco:report",
            "-DdataFile=target/jacoco.exec",
        ],
        check_type="coverage",
        output_format="xml",
        description="Code coverage — instruction, branch, line coverage",
        min_version="0.8.12",
        install_cmd=(
            "# Maven:\n"
            "<plugin><groupId>org.jacoco</groupId>"
            "<artifactId>jacoco-maven-plugin</artifactId>"
            "<version>0.8.12</version></plugin>"
        ),
        build_tool="maven",
    ),

    JavaToolConfig(
        name="google-java-format-check",
        command=[
            "java", "-jar", "{gjf_jar}",
            "--dry-run",
            "--set-exit-if-changed",
            "--aosp",  # Android Open Source style
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="text",
        description="Google Java Format checker — formatting consistency",
        min_version="1.22.0",
        install_cmd=(
            "wget https://github.com/google/google-java-format/releases/download/"
            "v1.22.0/google-java-format-1.22.0-all-deps.jar"
        ),
    ),
]


# ── CHECKSTYLE XML PARSER ─────────────────────────────────────────────────────

def parse_checkstyle_xml(xml_output: str) -> list[dict[str, Any]]:
    """checkstyle -f xml output parse karo."""
    issues = []

    try:
        root = ET.fromstring(xml_output)

        for file_elem in root.findall(".//file"):
            file_path = file_elem.get("name", "")

            for error in file_elem.findall("error"):
                line    = int(error.get("line", "0"))
                col     = int(error.get("column", "0") or "0")
                sev     = error.get("severity", "warning")
                message = error.get("message", "")
                source  = error.get("source", "")

                # Source class se rule ID nikalo
                rule_id = source.split(".")[-1] if source else "CS-STYLE"

                issues.append({
                    "file":     file_path,
                    "line":     line,
                    "column":   col,
                    "severity": _java_severity(sev),
                    "rule_id":  f"CS-{rule_id}",
                    "message":  message,
                    "category": _checkstyle_category(source),
                })

    except ET.ParseError:
        pass

    return issues


def _checkstyle_category(source: str) -> str:
    cat_map = {
        "design":     "QUALITY",
        "coding":     "QUALITY",
        "imports":    "IMPORTS",
        "naming":     "NAMING",
        "whitespace": "STYLE",
        "blocks":     "STYLE",
        "javadoc":    "DOCSTRING",
        "metrics":    "COMPLEXITY",
        "regexp":     "QUALITY",
        "size":       "COMPLEXITY",
    }
    for key, cat in cat_map.items():
        if key in source.lower():
            return cat
    return "STYLE"


# ── SPOTBUGS / FIND-SEC-BUGS XML PARSER ──────────────────────────────────────

def parse_spotbugs_xml(xml_path: str) -> list[dict[str, Any]]:
    """SpotBugs XML report parse karo."""
    issues = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        assert root is not None
        for bug in root.findall(".//BugInstance"):
            bug_type    = bug.get("type", "")
            priority    = bug.get("priority", "2")  # SpotBugs: 1 high, 2 medium, 3 low
            category    = bug.get("category", "CORRECTNESS")

            # Source line
            source = bug.find(".//SourceLine")
            file_path = source.get("sourcepath", "") if source is not None else ""
            line      = int(source.get("start", "0")) if source is not None else 0

            # Short message
            msg_elem = bug.find(".//ShortMessage")
            message  = msg_elem.text if msg_elem is not None and msg_elem.text else bug_type

            issues.append({
                "file":     file_path,
                "line":     line,
                "column":   0,
                "severity": _spotbugs_severity(int(priority)),
                "rule_id":  f"SB-{bug_type}",
                "message":  message,
                "category": _spotbugs_category(category),
            })

    except (ET.ParseError, OSError, ValueError):
        pass

    return issues


def _spotbugs_severity(priority: int) -> str:
    if priority == 1:
        return "critical"
    if priority == 2:
        return "warning"
    return "info"


def _spotbugs_category(category: str) -> str:
    cat_map = {
        "CORRECTNESS":       "BUGPRONE",
        "BAD_PRACTICE":      "QUALITY",
        "MALICIOUS_CODE":    "SECURITY",
        "MT_CORRECTNESS":    "BUGPRONE",
        "PERFORMANCE":       "PERF",
        "SECURITY":          "SECURITY",
        "STYLE":             "STYLE",
        "EXPERIMENTAL":      "QUALITY",
        "I18N":              "QUALITY",
    }
    return cat_map.get(category.upper(), "QUALITY")


# ── PMD XML PARSER ────────────────────────────────────────────────────────────

def parse_pmd_xml(xml_output: str) -> list[dict[str, Any]]:
    """PMD XML output parse karo."""
    issues = []

    try:
        root = ET.fromstring(xml_output)

        for file_elem in root.findall(".//file"):
            file_path = file_elem.get("name", "")

            for violation in file_elem.findall("violation"):
                line        = int(violation.get("beginline", "0"))
                col         = int(violation.get("begincolumn", "0"))
                priority    = int(violation.get("priority", "3"))
                rule        = violation.get("rule", "")
                ruleset     = violation.get("ruleset", "")
                message     = (violation.text or "").strip()

                issues.append({
                    "file":     file_path,
                    "line":     line,
                    "column":   col,
                    "severity": _pmd_severity(priority),
                    "rule_id":  f"PMD-{rule}",
                    "message":  message,
                    "category": _pmd_category(ruleset),
                })

    except ET.ParseError:
        pass

    return issues


def _pmd_severity(priority: int) -> str:
    # PMD: 1=high, 2=medium_high, 3=medium, 4=medium_low, 5=low
    if priority <= 2:
        return "critical"
    if priority == 3:
        return "warning"
    return "info"


def _pmd_category(ruleset: str) -> str:
    cat_map = {
        "Best Practices": "QUALITY",
        "Code Style":     "STYLE",
        "Design":         "QUALITY",
        "Documentation":  "DOCSTRING",
        "Error Prone":    "BUGPRONE",
        "Multithreading": "BUGPRONE",
        "Performance":    "PERF",
        "Security":       "SECURITY",
        "Unnecessary":    "DEADCODE",
    }
    for key, cat in cat_map.items():
        if key.lower() in ruleset.lower():
            return cat
    return "QUALITY"


# ── JACOCO XML PARSER ─────────────────────────────────────────────────────────

def parse_jacoco_xml(xml_path: str) -> dict[str, float | None]:
    """JaCoCo XML report se coverage data nikalo."""
    result: dict[str, float | None] = {
        "instruction_coverage": None,
        "branch_coverage":      None,
        "line_coverage":        None,
        "method_coverage":      None,
    }

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Top-level counters
        assert root is not None
        for counter in root.findall("counter"):
            ctype   = counter.get("type", "")
            missed  = int(counter.get("missed", "0"))
            covered = int(counter.get("covered", "0"))
            total   = missed + covered

            if total == 0:
                continue

            pct = (covered / total) * 100

            if ctype == "INSTRUCTION":
                result["instruction_coverage"] = round(pct, 2)
            elif ctype == "BRANCH":
                result["branch_coverage"] = round(pct, 2)
            elif ctype == "LINE":
                result["line_coverage"] = round(pct, 2)
            elif ctype == "METHOD":
                result["method_coverage"] = round(pct, 2)

    except (ET.ParseError, OSError, ValueError):
        pass

    return result


# ── BUILD SYSTEM DETECTION ────────────────────────────────────────────────────

def detect_build_system(project_path: str) -> str | None:
    """Maven ya Gradle detect karo."""
    path = Path(project_path)

    if (path / _POM_FILE).exists():
        return "maven"
    if (path / _GRADLE_FILE).exists() or (path / "build.gradle.kts").exists():
        return "gradle"
    if (path / "gradlew").exists():
        return "gradle"

    # Recursive check (multi-module projects)
    for pom in path.rglob(_POM_FILE):
        if "target" not in str(pom):
            return "maven"
    for gradle in path.rglob(_GRADLE_FILE):
        if "build" not in str(gradle).split("/")[-2:]:
            return "gradle"

    return None


def find_java_root(project_path: str) -> str | None:
    """Java project root dhundo (pom.xml ya build.gradle wala folder)."""
    path = Path(project_path)

    if (path / _POM_FILE).exists() or (path / _GRADLE_FILE).exists():
        return str(path)

    if path.is_file():
        parent = path.parent
        if (parent / _POM_FILE).exists():
            return str(parent)

    for pom in path.rglob(_POM_FILE):
        if "target" not in str(pom):
            return str(pom.parent)

    return None


# ── JAVA FILE DETECTION ───────────────────────────────────────────────────────

JAVA_EXTENSIONS = {".java", ".kt", ".scala"}


def _java_severity(level: str) -> str:
    sev_map = {
        "error":   "critical",
        "warning": "warning",
        "info":    "info",
        "ignore":  "info",
    }
    return sev_map.get(level.lower(), "warning")


def is_java_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in JAVA_EXTENSIONS


def find_java_files(project_path: str) -> list[str]:
    """Project mein sab .java files dhundo, generated code ignore karo."""
    path = Path(project_path)
    ignore_dirs = {"target", "build", ".gradle", "generated", "gen", "out"}

    java_files = []
    for java_file in path.rglob("*.java"):
        parts = set(java_file.parts)
        if not parts.intersection(ignore_dirs):
            java_files.append(str(java_file))

    return java_files


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_java_tools(
    only: str | None = None,
    skip_slow: bool = False,
    build_system: str = "any",
) -> list[JavaToolConfig]:
    """
    Java tools ki filtered list.

    Args:
        only: quality / security / faketests / coverage
        skip_slow: pitest aur jacoco skip karo (maven build chahiye)
        build_system: maven / gradle / any
    """
    tools = JAVA_TOOLS.copy()

    if build_system != "any":
        tools = [t for t in tools if t.build_tool in (build_system, "any")]

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"pitest", "jacoco", "spotbugs"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in JAVA_TOOLS}
