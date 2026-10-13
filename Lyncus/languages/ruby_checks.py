"""
Ruby Language Checks — rubocop, brakeman, debride, simplecov
Bundler/Gemfile detect karke tools chalata hai.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"


@dataclass
class RubyToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_gemfile: bool = False


# ── RUBY TOOL DEFINITIONS ─────────────────────────────────────────────────────

RUBY_TOOLS: list[RubyToolConfig] = [

    RubyToolConfig(
        name="rubocop",
        command=[
            "rubocop",
            "--format", "json",
            "--no-color",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="json",
        description="Ruby style guide enforcer — 350+ cops for style, lint, performance",
        min_version="1.64.0",
        install_cmd="gem install rubocop\n# Ya Gemfile mein: gem 'rubocop', require: false",
    ),

    RubyToolConfig(
        name="brakeman",
        command=[
            "brakeman",
            "--format", "json",
            "--quiet",
            "--no-exit-on-warn",
            _PATH_ARGUMENT,
        ],
        check_type="security",
        output_format="json",
        description="Rails security scanner — SQL injection, XSS, CSRF, mass assignment",
        min_version="6.1.2",
        install_cmd="gem install brakeman\n# Gemfile mein: gem 'brakeman', group: :development",
        needs_gemfile=True,
    ),

    RubyToolConfig(
        name="debride",
        command=[
            "debride",
            "--rails",    # Rails methods bhi check karo
            _PATH_ARGUMENT,
        ],
        check_type="deadcode",
        output_format="text",
        description="Dead code finder — unused methods aur classes pakadta hai",
        min_version="1.12.0",
        install_cmd="gem install debride",
    ),

    RubyToolConfig(
        name="reek",
        command=[
            "reek",
            "--format", "json",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="json",
        description="Code smell detector — long methods, feature envy, data clumps",
        min_version="6.3.0",
        install_cmd="gem install reek",
    ),

    RubyToolConfig(
        name="ruby-audit",
        command=[
            "bundle-audit", "check",
            "--update",
        ],
        check_type="security",
        output_format="text",
        description="Gem vulnerability checker — CVEs in bundled gems",
        min_version="0.9.1",
        install_cmd="gem install bundler-audit",
        needs_gemfile=True,
    ),

    RubyToolConfig(
        name="flog",
        command=[
            "flog",
            "--all",
            "--continue",
            "{path}",
        ],
        check_type="complexity",
        output_format="text",
        description="Complexity metric — ABC (assignments, branches, calls) score",
        min_version="4.8.1",
        install_cmd="gem install flog",
    ),
]


# ── RUBOCOP JSON PARSER ───────────────────────────────────────────────────────

def parse_rubocop_json(json_output: str) -> list[dict[str, Any]]:
    """RuboCop --format json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        for file_entry in data.get("files", []):
            file_path = file_entry.get("path", "")
            for offense in file_entry.get("offenses", []):
                loc      = offense.get("location", {})
                severity = offense.get("severity", "warning")
                cop      = offense.get("cop_name", "")
                msg      = offense.get("message", "")

                issues.append({
                    "file":     file_path,
                    "line":     loc.get("start_line", 0),
                    "column":   loc.get("start_column", 0),
                    "severity": _rubocop_severity(severity),
                    "rule_id":  f"RBC-{cop.replace('/', '_')}",
                    "message":  msg,
                    "category": _rubocop_category(cop),
                })

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


def _rubocop_severity(severity: str) -> str:
    sev_map = {
        "fatal":      "critical",
        "error":      "critical",
        "warning":    "warning",
        "convention": "info",
        "refactor":   "info",
        "info":       "info",
    }
    return sev_map.get(severity.lower(), "warning")


def _rubocop_category(cop_name: str) -> str:
    """RuboCop cop name se category."""
    prefix = cop_name.split("/")[0].lower()
    cat_map = {
        "style":       "STYLE",
        "layout":      "STYLE",
        "lint":        "QUALITY",
        "metrics":     "COMPLEXITY",
        "naming":      "NAMING",
        "performance": "PERF",
        "security":    "SECURITY",
        "bundler":     "QUALITY",
        "gemspec":     "QUALITY",
        "rails":       "QUALITY",
        "rspec":       "QUALITY",
    }
    return cat_map.get(prefix, "QUALITY")


# ── BRAKEMAN JSON PARSER ──────────────────────────────────────────────────────

def parse_brakeman_json(json_output: str) -> list[dict[str, Any]]:
    """Brakeman --format json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        for warning in data.get("warnings", []):
            issues.append({
                "file":     warning.get("file", ""),
                "line":     warning.get("line", 0),
                "column":   0,
                "severity": _brakeman_severity(warning.get("confidence", "Medium")),
                "rule_id":  f"BK-{warning.get('warning_code', 0)}",
                "message":  warning.get("message", ""),
                "category": "SECURITY",
            })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


def _brakeman_severity(confidence: str) -> str:
    confidence_map = {
        "High":   "critical",
        "Medium": "warning",
        "Low":    "info",
        "Weak":   "info",
    }
    return confidence_map.get(confidence, "warning")


# ── REEK JSON PARSER ──────────────────────────────────────────────────────────

def parse_reek_json(json_output: str) -> list[dict[str, Any]]:
    """Reek --format json output parse karo."""
    issues = []

    try:
        data = json.loads(json_output)
        for smell in data:
            for loc in smell.get("lines", [smell.get("source_line", 0)]):
                issues.append({
                    "file":     smell.get("source", ""),
                    "line":     loc if isinstance(loc, int) else 0,
                    "column":   0,
                    "severity": "warning",
                    "rule_id":  f"REEK-{smell.get('smell_type', 'CodeSmell').upper()}",
                    "message":  smell.get("message", ""),
                    "category": "QUALITY",
                })
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return issues


# ── DEBRIDE TEXT PARSER ───────────────────────────────────────────────────────

def parse_debride_output(output: str) -> list[dict[str, Any]]:
    """Debride text output parse karo."""
    issues = []
    for raw_line in output.splitlines():
        method, separator, location = raw_line.strip().partition(" in ")
        if not separator:
            continue
        file, separator, line = location.rpartition(":")
        if not separator or not line.isdigit():
            continue
        issues.append({
            "file":     file.strip(),
            "line":     int(line),
            "column":   0,
            "severity": "warning",
            "rule_id":  "DEB-UNUSED_METHOD",
            "message":  f"Unused method: {method.strip()}",
            "category": "DEADCODE",
        })

    return issues


# ── FLOG TEXT PARSER ──────────────────────────────────────────────────────────

def parse_flog_output(output: str) -> list[dict[str, Any]]:
    """Flog output parse karo — high complexity methods."""
    issues = []
    # Format: score: ClassName#method_name in file.rb:line
    FLOG_THRESHOLD = 25.0  # ABC score threshold

    for raw_line in output.splitlines():
        score, separator, finding = raw_line.strip().partition(":")
        if not separator:
            continue
        method, separator, location = finding.strip().partition(" in ")
        if not separator:
            continue
        file, separator, line = location.rpartition(":")
        if not separator or not line.isdigit():
            continue
        try:
            flog_score = float(score)
        except ValueError:
            continue

        if flog_score >= FLOG_THRESHOLD:
            issues.append({
                "file":     file.strip(),
                "line":     int(line),
                "column":   0,
                "severity": "critical" if flog_score >= 50 else "warning",
                "rule_id":  "FLOG-HIGH_COMPLEXITY",
                "message":  f"{method.strip()} — ABC complexity score: {flog_score:.1f}",
                "category": "COMPLEXITY",
            })

    return issues


# ── PROJECT DETECTION ─────────────────────────────────────────────────────────

RUBY_EXTENSIONS = {".rb", ".rake", ".gemspec", ".ru"}


def is_ruby_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in RUBY_EXTENSIONS


def find_ruby_files(project_path: str) -> list[str]:
    path = Path(project_path)
    ignore_dirs = {"vendor", "node_modules", ".git", "tmp", "log"}

    ruby_files = []
    for ext in RUBY_EXTENSIONS:
        for rb_file in path.rglob(f"*{ext}"):
            if not any(d in rb_file.parts for d in ignore_dirs):
                ruby_files.append(str(rb_file))
    return ruby_files


def detect_ruby_project(project_path: str) -> dict[str, Any]:
    """Ruby project type detect karo."""
    path = Path(project_path)
    has_gemfile   = (path / "Gemfile").exists()
    has_gemfile_lock = (path / "Gemfile.lock").exists()
    is_rails      = (path / "config" / "application.rb").exists()
    is_sinatra    = any("sinatra" in (path / "Gemfile").read_text().lower()
                        for _ in [None] if has_gemfile)

    if is_rails:
        framework = "rails"
    elif is_sinatra:
        framework = "sinatra"
    else:
        framework = "plain"

    return {
        "framework":     framework,
        "has_gemfile":   has_gemfile,
        "has_lock":      has_gemfile_lock,
        "ruby_version":  _detect_ruby_version(str(path)),
    }


def _detect_ruby_version(project_path: str) -> str:
    """Ruby version .ruby-version ya Gemfile se nikalo."""
    ruby_ver = Path(project_path) / ".ruby-version"
    if ruby_ver.exists():
        return ruby_ver.read_text().strip()
    return ""


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_ruby_tools(
    only: str | None = None,
    is_rails: bool = False,
    skip_slow: bool = False,
) -> list[RubyToolConfig]:
    tools = RUBY_TOOLS.copy()

    # Non-rails project ke liye brakeman skip karo
    if not is_rails:
        tools = [t for t in tools if t.name != "brakeman"]

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"reek", "flog"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in RUBY_TOOLS}
