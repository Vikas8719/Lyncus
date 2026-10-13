"""
Rust Language Checks — clippy, rustfmt, cargo-audit, cargo-tarpaulin, cargo-machete
Rust ke tools Cargo.toml wale folder mein chalte hain, file pe nahi.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RustToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_cargo_toml: bool = True  # Cargo.toml chahiye


# ── RUST TOOL DEFINITIONS ─────────────────────────────────────────────────────

RUST_TOOLS: list[RustToolConfig] = [
    RustToolConfig(
        name="cargo-clippy",
        command=[
            "cargo",
            "clippy",
            "--message-format",
            "json",
            "--",
            "-D",
            "warnings",
            "-W",
            "clippy::all",
            "-W",
            "clippy::pedantic",
            "-W",
            "clippy::nursery",
        ],
        check_type="quality",
        output_format="json",
        description="Rust linter — bad patterns, performance issues, idiomatic code",
        min_version="latest",
        install_cmd="rustup component add clippy",
    ),
    RustToolConfig(
        name="rustfmt",
        command=["cargo", "fmt", "--", "--check"],
        check_type="quality",
        output_format="text",
        description="Rust formatter — code style consistency",
        min_version="latest",
        install_cmd="rustup component add rustfmt",
    ),
    RustToolConfig(
        name="cargo-audit",
        command=["cargo", "audit", "--json"],
        check_type="security",
        output_format="json",
        description="Dependency vulnerability scanner — CVE database check",
        min_version="0.20.0",
        install_cmd="cargo install cargo-audit",
    ),
    RustToolConfig(
        name="cargo-machete",
        command=["cargo", "machete"],
        check_type="deadcode",
        output_format="text",
        description="Unused dependencies detector — Cargo.toml cleanup",
        min_version="0.6.0",
        install_cmd="cargo install cargo-machete",
    ),
    RustToolConfig(
        name="cargo-tarpaulin",
        command=[
            "cargo",
            "tarpaulin",
            "--out",
            "Stdout",
            "--skip-clean",
        ],
        check_type="coverage",
        output_format="text",
        description="Code coverage — test coverage percentage",
        min_version="0.31.0",
        install_cmd="cargo install cargo-tarpaulin",
    ),
    RustToolConfig(
        name="cargo-check",
        command=["cargo", "check", "--message-format", "json"],
        check_type="quality",
        output_format="json",
        description="Fast compilation check — errors aur warnings",
        min_version="latest",
        install_cmd="rustup (built-in)",
        needs_cargo_toml=True,
    ),
    RustToolConfig(
        name="cargo-deny",
        command=["cargo", "deny", "check"],
        check_type="security",
        output_format="text",
        description="License, security, duplicate dependency check",
        min_version="0.14.0",
        install_cmd="cargo install cargo-deny",
    ),
    RustToolConfig(
        name="cargo-mutants",
        command=["cargo", "mutants", "--timeout", "60"],
        check_type="faketests",
        output_format="text",
        description="Mutation testing — fake/weak tests pakadta hai",
        min_version="24.0.0",
        install_cmd="cargo install cargo-mutants",
    ),
]


# ── CLIPPY LINT CATEGORIES ────────────────────────────────────────────────────

CLIPPY_CATEGORY_MAP: dict[str, str] = {
    "clippy::correctness": "BUGPRONE",  # Definite bugs
    "clippy::suspicious": "BUGPRONE",  # Probably bugs
    "clippy::style": "STYLE",  # Style issues
    "clippy::complexity": "COMPLEXITY",  # Unnecessary complexity
    "clippy::perf": "PERF",  # Performance issues
    "clippy::pedantic": "QUALITY",  # Strict rules
    "clippy::nursery": "QUALITY",  # Experimental rules
    "clippy::cargo": "DEPS",  # Cargo.toml issues
    "unused": "DEADCODE",
    "dead_code": "DEADCODE",
    "unreachable": "DEADCODE",
    "deprecated": "QUALITY",
    "unsafe": "SECURITY",
}

CLIPPY_SEVERITY_MAP: dict[str, str] = {
    "error": "critical",
    "warning": "warning",
    "note": "info",
    "help": "info",
}


def get_clippy_category(lint_name: str) -> str:
    """Clippy lint name se category nikalo."""
    for prefix, cat in CLIPPY_CATEGORY_MAP.items():
        if lint_name.startswith(prefix) or prefix in lint_name:
            return cat
    return "QUALITY"


def get_clippy_severity(level: str) -> str:
    return CLIPPY_SEVERITY_MAP.get(level, "warning")


# ── CARGO AUDIT SEVERITY ──────────────────────────────────────────────────────

CARGO_AUDIT_SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "critical",
    "medium": "warning",
    "low": "info",
    "none": "info",
}


def get_audit_severity(cvss_score: float | None, advisory_severity: str) -> str:
    """CVSS score ya advisory severity se Lyncus severity nikalo."""
    if cvss_score is not None:
        if cvss_score >= 9.0:
            return "critical"
        if cvss_score >= 7.0:
            return "critical"
        if cvss_score >= 4.0:
            return "warning"
        return "info"
    return CARGO_AUDIT_SEVERITY_MAP.get(advisory_severity.lower(), "warning")


# ── CARGO.TOML FINDER ─────────────────────────────────────────────────────────


def find_cargo_toml(project_path: str) -> str | None:
    """
    Project path mein Cargo.toml dhundo.
    Runner ko Cargo.toml wale folder mein chahiye.
    """
    path = Path(project_path)

    search_path = path.parent if path.is_file() else path
    for parent in (search_path, *search_path.parents):
        if (parent / "Cargo.toml").exists():
            return str(parent)

    # Recursive search (max 3 levels)
    for cargo in path.rglob("Cargo.toml"):
        if "target" not in str(cargo):
            return str(cargo.parent)

    return None


# ── RUSTFMT DIFF PARSER ───────────────────────────────────────────────────────


def parse_rustfmt_diff(output: str) -> list[dict[str, Any]]:
    """rustfmt --check output parse karo."""
    issues = []
    lines = output.splitlines()

    for line in lines:
        if line.startswith("Diff in "):
            # "Diff in src/main.rs at line 42:"
            parts = line.split(" at line ")
            if len(parts) == 2:
                file_part = parts[0].replace("Diff in ", "").strip()
                try:
                    line_num = int(parts[1].rstrip(":"))
                except ValueError:
                    line_num = 0
                issues.append(
                    {
                        "file": file_part,
                        "line": line_num,
                        "message": "rustfmt formatting required — cargo fmt chalao",
                    }
                )

    return issues


# ── TARPAULIN COVERAGE PARSER ─────────────────────────────────────────────────


def parse_tarpaulin_coverage(output: str) -> float | None:
    """
    cargo-tarpaulin output se coverage percentage nikalo.
    Returns: float (0.0-100.0) ya None agar parse na ho
    """
    import re

    # "XX.XX% coverage, Y/Z lines covered"
    for marker in re.finditer(r"%\s+coverage", output):
        value = output[: marker.start()].rstrip().split()[-1:]
        if value and "." in value[0]:
            try:
                return float(value[0])
            except ValueError:
                continue
    return None


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────


def get_rust_tools(
    only: str | None = None,
    skip_slow: bool = False,
) -> list[RustToolConfig]:
    """
    Rust tools ki filtered list.

    Args:
        only: quality / security / deadcode / coverage / faketests
        skip_slow: cargo-tarpaulin aur cargo-mutants skip karo (bohot slow hain)
    """
    tools = RUST_TOOLS.copy()

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"cargo-tarpaulin", "cargo-mutants"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in RUST_TOOLS}
