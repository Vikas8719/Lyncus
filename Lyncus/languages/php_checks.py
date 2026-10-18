"""
PHP Language Checks — phpcs, phpstan, psalm, phan
Composer.json detect karke tools chalata hai.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET

_PATH_ARGUMENT = "{path}"
_PHPCPD_REPORT = "{tmpdir}/phpcpd.xml"


@dataclass
class PhpToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_composer: bool = False


# ── PHP TOOL DEFINITIONS ──────────────────────────────────────────────────────

PHP_TOOLS: list[PhpToolConfig] = [

    PhpToolConfig(
        name="phpcs",
        command=[
            "phpcs",
            "--standard=PSR12",
            "--report=json",
            "--severity=1",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="json",
        description="PHP CodeSniffer — PSR-12/PSR-2 coding standards enforce karta hai",
        min_version="3.10.1",
        install_cmd=(
            "composer global require squizlabs/php_codesniffer\n"
            "# Ya: phive install phpcs"
        ),
    ),

    PhpToolConfig(
        name="phpstan",
        command=[
            "phpstan", "analyse",
            "--level=8",
            "--error-format=json",
            "--no-progress",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="json",
        description="PHPStan — strict type checking, level 0-9 (8 default)",
        min_version="1.11.0",
        install_cmd=(
            "composer require --dev phpstan/phpstan\n"
            "# Ya: phive install phpstan"
        ),
    ),

    PhpToolConfig(
        name="psalm",
        command=[
            "psalm",
            "--output-format=json",
            "--no-progress",
            "--show-info=true",
            _PATH_ARGUMENT,
        ],
        check_type="security",
        output_format="json",
        description="Psalm — security analysis, type inference, taint analysis",
        min_version="5.24.0",
        install_cmd=(
            "composer require --dev vimeo/psalm\n"
            "# Init: ./vendor/bin/psalm --init"
        ),
        needs_composer=True,
    ),

    PhpToolConfig(
        name="phan",
        command=[
            "phan",
            "--output-mode=json",
            "--no-progress-bar",
            "--quick",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="json",
        description="Phan — deep static analysis, dead code detection, type checking",
        min_version="5.4.5",
        install_cmd=(
            "composer require --dev phan/phan\n"
            "# Requires php-ast extension: pecl install ast"
        ),
    ),

    PhpToolConfig(
        name="composer-audit",
        command=[
            "composer", "audit",
            "--format=json",
            "--no-interaction",
        ],
        check_type="security",
        output_format="json",
        description="Composer security audit — vulnerable packages check karta hai",
        min_version="Composer 2.4+",
        install_cmd="# Composer 2.4+ mein built-in hai",
        needs_composer=True,
    ),

    PhpToolConfig(
        name="phpcpd",
        command=[
            "phpcpd",
            "--min-lines=5",
            "--min-tokens=70",
            "--log-pmd", _PHPCPD_REPORT,
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="xml",
        description="PHP Copy-Paste Detector — duplicate code blocks pakadta hai",
        min_version="6.0.3",
        install_cmd="phive install phpcpd",
    ),
]


# ── PHPCS JSON PARSER ─────────────────────────────────────────────────────────

def parse_phpcs_json(json_output: str) -> list[dict[str, Any]]:
    """PHP CodeSniffer --report=json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        files = data.get("files", {})

        for file_path, file_data in files.items():
            for msg in file_data.get("messages", []):
                issues.append({
                    "file":     file_path,
                    "line":     msg.get("line", 0),
                    "column":   msg.get("column", 0),
                    "severity": "critical" if msg.get("type") == "ERROR" else "warning",
                    "rule_id":  f"PHPCS-{msg.get('source', 'Style').split('.')[-1]}",
                    "message":  msg.get("message", ""),
                    "category": _phpcs_category(msg.get("source", "")),
                })

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


def _phpcs_category(source: str) -> str:
    source_lower = source.lower()
    if "comment" in source_lower or "docblock" in source_lower:
        return "DOCSTRING"
    if "whitespace" in source_lower or "indent" in source_lower:
        return "STYLE"
    if "naming" in source_lower or "camel" in source_lower:
        return "NAMING"
    if "function" in source_lower or "method" in source_lower:
        return "QUALITY"
    return "STYLE"


# ── PHPSTAN JSON PARSER ───────────────────────────────────────────────────────

def parse_phpstan_json(json_output: str) -> list[dict[str, Any]]:
    """PHPStan --error-format=json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        # File errors
        for file_path, file_errors in data.get("files", {}).items():
            for error in file_errors.get("messages", []):
                issues.append({
                    "file":     file_path,
                    "line":     error.get("line", 0),
                    "column":   0,
                    "severity": "critical" if error.get("ignorable") is False else "warning",
                    "rule_id":  "PHPSTAN-TYPE",
                    "message":  error.get("message", ""),
                    "category": "TYPE",
                })

        # Not-file-specific errors
        for error in data.get("errors", []):
            issues.append({
                "file":     "",
                "line":     0,
                "column":   0,
                "severity": "critical",
                "rule_id":  "PHPSTAN-CONFIG",
                "message":  str(error),
                "category": "QUALITY",
            })

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


# ── PSALM JSON PARSER ─────────────────────────────────────────────────────────

def parse_psalm_json(json_output: str) -> list[dict[str, Any]]:
    """Psalm --output-format=json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        for issue in data:
            severity = issue.get("severity", "warning")
            issues.append({
                "file":     issue.get("file_name", ""),
                "line":     issue.get("line_from", 0),
                "column":   issue.get("column_from", 0),
                "severity": "critical" if severity == "error" else "warning",
                "rule_id":  f"PSALM-{issue.get('type', 'Unknown')}",
                "message":  issue.get("message", ""),
                "category": _psalm_category(issue.get("type", "")),
            })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


def _psalm_category(issue_type: str) -> str:
    security_types = {
        "TaintedInput", "TaintedHtml", "TaintedSql", "TaintedShell",
        "TaintedFile", "TaintedHeader", "TaintedCookie",
    }
    if issue_type in security_types:
        return "SECURITY"
    if "Undefined" in issue_type or "Unresolved" in issue_type:
        return "QUALITY"
    if "Deprecated" in issue_type or "Unused" in issue_type:
        return "DEADCODE"
    if "Type" in issue_type or "Mismatch" in issue_type:
        return "TYPE"
    return "QUALITY"


# ── PHAN JSON PARSER ──────────────────────────────────────────────────────────

def parse_phan_json(json_output: str) -> list[dict[str, Any]]:
    """Phan --output-mode=json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        if not isinstance(data, list):
            data = [data]

        for item in data:
            issues.append({
                "file":     item.get("filename", ""),
                "line":     item.get("line", 0),
                "column":   item.get("col", 0),
                "severity": _phan_severity(item.get("severity", 10)),
                "rule_id":  f"PHAN-{item.get('check_name', 'General')}",
                "message":  item.get("description", ""),
                "category": _phan_category(item.get("check_name", "")),
            })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


def _phan_severity(severity: int) -> str:
    # Phan: 10=critical, 5=normal, 1=low
    if severity >= 10:
        return "critical"
    if severity >= 5:
        return "warning"
    return "info"


def _phan_category(check_name: str) -> str:
    check_lower = check_name.lower()
    if "taint" in check_lower or "security" in check_lower:
        return "SECURITY"
    if "unused" in check_lower or "dead" in check_lower:
        return "DEADCODE"
    if "type" in check_lower:
        return "TYPE"
    return "QUALITY"


# ── COMPOSER AUDIT PARSER ─────────────────────────────────────────────────────

def parse_composer_audit_json(json_output: str) -> list[dict[str, Any]]:
    """Composer audit --format=json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        advisories = data.get("advisories", {})

        for package_name, package_advisories in advisories.items():
            for advisory in package_advisories:
                issues.append({
                    "file":     "composer.lock",
                    "line":     0,
                    "column":   0,
                    "severity": "critical",
                    "rule_id":  f"CVE-{advisory.get('cve', 'UNKNOWN')}",
                    "message":  f"{package_name}: {advisory.get('title', 'Vulnerability found')}",
                    "category": "SECURITY",
                })

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


# ── PHPCPD XML PARSER ─────────────────────────────────────────────────────────

def parse_phpcpd_xml(xml_path: str) -> list[dict[str, Any]]:
    """PHP Copy-Paste Detector PMD XML output parse karo."""
    issues = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for dup in root.findall(".//duplication"):
            lines     = int(dup.get("lines", "0"))
            tokens    = int(dup.get("tokens", "0"))
            first_file = dup.find("file")

            if first_file is None:
                continue

            file_path = first_file.get("path", "")
            line      = int(first_file.get("line", "0"))

            issues.append({
                "file":     file_path,
                "line":     line,
                "column":   0,
                "severity": "warning",
                "rule_id":  "PHPCPD-DUPLICATE",
                "message":  f"Duplicate code block: {lines} lines, {tokens} tokens",
                "category": "QUALITY",
            })

    except (ET.ParseError, OSError, ValueError):
        pass

    return issues


# ── PROJECT DETECTION ─────────────────────────────────────────────────────────

PHP_EXTENSIONS = {".php", ".phtml", ".php5", ".php7", ".php8"}


def is_php_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in PHP_EXTENSIONS


def find_php_files(project_path: str) -> list[str]:
    path = Path(project_path)
    ignore_dirs = {"vendor", "node_modules", ".git", "cache", "storage", "public/build"}

    php_files = []
    for php_file in path.rglob("*.php"):
        if not any(d in php_file.parts for d in ignore_dirs):
            php_files.append(str(php_file))
    return php_files


def detect_php_project(project_path: str) -> dict[str, Any]:
    """PHP project type detect karo (Laravel, Symfony, WordPress, etc.)."""
    path = Path(project_path)

    is_laravel   = (path / "artisan").exists()
    is_symfony   = (path / "bin" / "console").exists()
    is_wordpress = (path / "wp-config.php").exists() or (path / "wp-config-sample.php").exists()
    is_composer  = (path / "composer.json").exists()

    if is_laravel:
        framework = "laravel"
    elif is_symfony:
        framework = "symfony"
    elif is_wordpress:
        framework = "wordpress"
    else:
        framework = "plain"

    php_version = _detect_php_version(str(path))

    return {
        "framework":    framework,
        "has_composer": is_composer,
        "php_version":  php_version,
    }


def _detect_php_version(project_path: str) -> str:
    """PHP version composer.json ya .php-version se nikalo."""
    composer = Path(project_path) / "composer.json"
    if composer.exists():
        try:
            data = json.loads(composer.read_text())
            php_req = data.get("require", {}).get("php", "")
            if php_req:
                return str(php_req)
        except (json.JSONDecodeError, OSError):
            pass

    php_ver_file = Path(project_path) / ".php-version"
    if php_ver_file.exists():
        return php_ver_file.read_text().strip()

    return ""


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_php_tools(
    only: str | None = None,
    has_composer: bool = True,
    skip_slow: bool = False,
) -> list[PhpToolConfig]:
    tools = PHP_TOOLS.copy()

    if not has_composer:
        tools = [t for t in tools if not t.needs_composer]

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"psalm", "phan"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in PHP_TOOLS}
