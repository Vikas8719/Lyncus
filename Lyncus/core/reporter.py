"""
Reporter — Renders terminal output using Rich: colors, tables, progress bars.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from Lyncus.core.parser import Problem

console = Console()

# Named score constants — magic number ban jaate the
_SCORE_GREEN_THRESHOLD = 80   # score >= 80 → green
_SCORE_YELLOW_THRESHOLD = 50  # score >= 50 → yellow
_CRITICAL_PENALTY = 15        # score penalty per critical issue
_WARNING_PENALTY = 5          # score penalty per warning issue
_SCORE_MAX = 100

# Badge SVG width constants
_BADGE_LEFT_WIDTH = 80         # Left panel ("🐺 Lyncus") px width
_BADGE_MIN_RIGHT_WIDTH = 60    # Minimum right panel px width
_BADGE_ISSUES_MIN_RIGHT = 70   # Minimum right panel width for issues badge
_BADGE_LANG_TOTAL_WIDTH = 120  # Total badge width for language badge
_BADGE_LANG_HALF_WIDTH = 60    # Each half for language badge


# ── SEVERITY CONFIG ───────────────────────────────────────────────────────────
SEVERITY_ICONS = {
    "critical": "❌",
    "warning": "⚠️ ",
    "info": "ℹ️ ",
}

SEVERITY_COLORS = {
    "critical": "red",
    "warning": "yellow",
    "info": "blue",
}

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _score(problems: list[Problem]) -> int:
    """
    Calculate a 0-100 score based on problems found.

    Critical = -15, Warning = -5, Info = 0 (no penalty).
    COMPLEXITY warnings get no penalty — radon/lizard findings are refactor hints,
    not real bugs. A project with 30 complex functions should not score 0/100.
    Info issues do not affect the score — they are improvement hints, not blockers.
    """
    if not problems:
        return _SCORE_MAX
    critical = sum(
        1 for p in problems
        if p.severity == "critical" and p.category != "COMPLEXITY"
    )
    warnings = sum(
        1 for p in problems
        if p.severity == "warning" and p.category != "COMPLEXITY"
    )
    return max(0, _SCORE_MAX - (critical * _CRITICAL_PENALTY) - (warnings * _WARNING_PENALTY))


def _score_color(score: int) -> str:
    if score >= _SCORE_GREEN_THRESHOLD:
        return "green"
    if score >= _SCORE_YELLOW_THRESHOLD:
        return "yellow"
    return "red"


def _score_emoji(score: int) -> str:
    if score >= _SCORE_GREEN_THRESHOLD:
        return "🟢"
    if score >= _SCORE_YELLOW_THRESHOLD:
        return "🟡"
    return "🔴"


# ── PROGRESS BAR ──────────────────────────────────────────────────────────────
def make_progress() -> Progress:
    """Create a scanning progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[bold]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    )


# ── TERMINAL REPORTER ─────────────────────────────────────────────────────────
def print_header(  # noqa: PLR0913
    project_path: str,
    language: str,
    tools: list[str],
    skipped_tools: list[str] | None = None,
    skipped_reasons: dict[str, str] | None = None,
) -> None:
    """Print the Lyncus scan header."""
    console.print()
    console.print(
        Panel(
            Text("🐺  Lyncus — Code Quality Scanner", style="bold white", justify="center"),
            style="bold cyan",
            box=box.DOUBLE,
        )
    )
    # project_path aur tool names mein [ ] ho sakte hain — Rich inhe markup samajhta hai
    safe_project = rich_escape(project_path)
    safe_language = rich_escape(language)
    safe_tools = rich_escape(", ".join(tools))
    console.print(f"  [bold]📁 Project  :[/bold] {safe_project}")
    console.print(f"  [bold]🔍 Language :[/bold] [cyan]{safe_language}[/cyan] (auto-detected)")
    console.print(f"  [bold]🛠  Tools    :[/bold] {safe_tools}")

    # Skipped tools — platform incompatible ya not installed
    if skipped_tools:
        _PLATFORM_KEYWORDS = ("requires linux", "windows", "macos", "wsl", "not available on")
        _NOT_INSTALLED_KEYWORDS = ("not installed",)
        for tool_name in skipped_tools:
            reason = (skipped_reasons or {}).get(tool_name, "")
            reason_lower = reason.lower()
            safe_tool = rich_escape(tool_name)
            safe_reason = rich_escape(reason if reason else "not available on this platform")
            if any(kw in reason_lower for kw in _PLATFORM_KEYWORDS):
                # Platform-incompatible — CI/CD pe chalega
                console.print(
                    f"  [dim]⏭  {safe_tool} — {safe_reason} "
                    f"(CI/CD pe automatically available)[/dim]"
                )
            elif any(kw in reason_lower for kw in _NOT_INSTALLED_KEYWORDS) or not reason:
                console.print(f"  [dim]⏭  {safe_tool} — {safe_reason}[/dim]")
    console.print()


def print_problems(problems: list[Problem], severity_filter: str = "all") -> None:
    """Problems ko grouped aur colored print karo."""

    # Filter karo
    if severity_filter != "all":
        problems = [p for p in problems if p.severity == severity_filter]

    # Sort karo — critical pehle
    problems = sorted(problems, key=lambda p: SEVERITY_ORDER.get(p.severity, 9))

    # Group by severity
    groups: dict[str, list[Problem]] = {"critical": [], "warning": [], "info": []}
    for p in problems:
        groups.setdefault(p.severity, []).append(p)

    if not problems:
        console.print(
            Panel(
                "  [bold green]✅  No problems found! Code looks clean.[/bold green]",
                style="green",
            )
        )
        return

    # Critical
    if groups["critical"]:
        console.rule(f"[bold red]❌  CRITICAL PROBLEMS ({len(groups['critical'])})[/bold red]")
        _print_group(groups["critical"])

    # Warnings
    if groups["warning"]:
        console.rule(f"[bold yellow]⚠️   WARNINGS ({len(groups['warning'])})[/bold yellow]")
        _print_group(groups["warning"])

    # Info
    if groups["info"]:
        console.rule(f"[bold blue]ℹ️   INFO ({len(groups['info'])})[/bold blue]")
        _print_group(groups["info"])


def _print_group(problems: list[Problem]) -> None:
    """Print all problems in a single severity group."""
    for p in problems:
        color = SEVERITY_COLORS.get(p.severity, "white")
        icon = SEVERITY_ICONS.get(p.severity, "•")

        # Category badge
        category_text = Text(f"[{p.category:<10}]", style=f"bold {color}")
        # File location
        location = f"{p.file}:{p.line}"
        if p.column:
            location += f":{p.column}"
        # Message
        msg = p.message[:80]

        console.print(
            f"  {icon} ",
            category_text,
            f"[dim]{location:<40}[/dim]",
            f"[{color}]{msg}[/{color}]",
        )

        # Suggestion agar hai
        if p.suggestion:
            console.print(f"     [dim]💡 {p.suggestion}[/dim]")

    console.print()


def print_summary(
    problems: list[Problem],
    scan_time: float,
    files_scanned: int,
    skipped_tools: list[str],
    ran_tools: int = -1,
) -> None:
    """Final summary table print karo."""
    critical = sum(1 for p in problems if p.severity == "critical")
    warnings = sum(1 for p in problems if p.severity == "warning")
    info = sum(1 for p in problems if p.severity == "info")

    # Jab koi bhi tool actually run nahi hua, score N/A dikhao
    # (0/100 misleading hai jab scanning hi nahi hui)
    no_tools_ran = ran_tools == 0
    score = _score(problems) if not no_tools_ran else 0

    console.rule("[bold]📊  SUMMARY[/bold]")
    console.print()

    # Summary table
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Label", style="bold")
    table.add_column("Value")

    table.add_row("Critical", f"[red]{critical}[/red]  ❌")
    table.add_row("Warnings", f"[yellow]{warnings}[/yellow]  ⚠️ ")
    table.add_row("Info", f"[blue]{info}[/blue]  ℹ️ ")
    table.add_row("Files", str(files_scanned))
    if no_tools_ran:
        table.add_row("Score", "[dim]N/A — no tools ran[/dim]  ⚫")
    else:
        table.add_row(
            "Score",
            f"[{_score_color(score)}]{score}/100[/{_score_color(score)}]  {_score_emoji(score)}",
        )
    table.add_row("Time", f"{scan_time:.1f}s")

    console.print(table)

    if skipped_tools:
        safe_skipped = rich_escape(", ".join(skipped_tools))
        console.print(f"  [dim]⏭  Skipped tools (not installed): {safe_skipped}[/dim]")
        console.print(
            "  [dim]   Run [bold]Lyncus doctor[/bold] to see installation commands.[/dim]"
        )

    console.print()


def print_doctor(language_tools: dict[str, dict[str, bool]]) -> None:
    """Lyncus doctor output print karo."""
    console.print()
    console.print(
        Panel(
            Text("🐺  Lyncus — System Check", style="bold white", justify="center"),
            style="bold cyan",
            box=box.DOUBLE,
        )
    )

    total_available = 0
    total_tools = 0

    for language, tools in language_tools.items():
        console.print(f"\n  [bold cyan]{language.upper()} Tools:[/bold cyan]")
        for tool, available in tools.items():
            total_tools += 1
            if available:
                total_available += 1
                console.print(f"    [green]✅[/green]  {tool:<20} installed")
            else:
                console.print(f"    [red]❌[/red]  {tool:<20} [dim]NOT INSTALLED[/dim]")

    console.print()
    console.rule()
    console.print(
        f"\n  [bold]{total_available}/{total_tools}[/bold] tools available\n"
        "  Run [bold cyan]Lyncus install-deps --all[/bold cyan] to install missing tools\n"
    )


# ── JSON REPORTER ─────────────────────────────────────────────────────────────
def export_json(
    problems: list[Problem],
    project_path: str,
    language: str,
    scan_time: float,
    output_file: str = "Lyncus-report.json",
    ran_tools: int = -1,
) -> None:
    """Export problems to a JSON report file."""
    no_tools_ran = ran_tools == 0
    computed_score = _score(problems) if not no_tools_ran else None
    data = {
        "Lyncus_version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "project": project_path,
        "language": language,
        "scan_time_seconds": round(scan_time, 2),
        "summary": {
            "critical": sum(1 for p in problems if p.severity == "critical"),
            "warning": sum(1 for p in problems if p.severity == "warning"),
            "info": sum(1 for p in problems if p.severity == "info"),
            "total": len(problems),
            "score": computed_score,  # None jab koi tool nahi chala
        },
        "problems": [
            {
                "tool": p.tool,
                "rule_id": p.rule_id,
                "category": p.category,
                "severity": p.severity,
                "file": p.file,
                "line": p.line,
                "column": p.column,
                "message": p.message,
                "suggestion": p.suggestion,
            }
            for p in problems
        ],
    }

    # ASCII escaping keeps the report portable across Windows code pages while
    # UTF-8 makes the file encoding explicit for consumers.
    Path(output_file).write_text(
        json.dumps(data, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    console.print(f"  [green]✅ JSON report saved:[/green] {output_file}")


# ── HTML REPORTER ─────────────────────────────────────────────────────────────
def export_html(
    problems: list[Problem],
    project_path: str,
    language: str,
    scan_time: float,
    output_file: str = "Lyncus-report.html",
) -> None:
    """Export problems to an HTML report file."""
    score = _score(problems)
    critical = sum(1 for p in problems if p.severity == "critical")
    warnings = sum(1 for p in problems if p.severity == "warning")
    info = sum(1 for p in problems if p.severity == "info")

    if score >= _SCORE_GREEN_THRESHOLD:
        score_color = "#22c55e"
    elif score >= _SCORE_YELLOW_THRESHOLD:
        score_color = "#f59e0b"
    else:
        score_color = "#ef4444"

    rows = ""
    for p in sorted(problems, key=lambda x: SEVERITY_ORDER.get(x.severity, 9)):
        sev_colors = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}
        color = sev_colors.get(p.severity, "#6b7280")
        rows += f"""
        <tr>
          <td><span style="color:{color};font-weight:bold">{p.severity.upper()}</span></td>
          <td><code>{p.category}</code></td>
          <td>{p.file}:{p.line}</td>
          <td>{p.message}</td>
          <td><em>{p.suggestion or "—"}</em></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Lyncus Report — {project_path}</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
    h1   {{ color: #7dd3fc; }} h2 {{ color: #94a3b8; }}
    .summary {{ display: flex; gap: 16px; margin: 24px 0; flex-wrap: wrap; }}
    .card {{ background: #1e293b; border-radius: 8px; padding: 16px 24px; min-width: 100px; text-align: center; }}
    .card .num {{ font-size: 2rem; font-weight: bold; }}
    .card .label {{ font-size: 0.85rem; color: #94a3b8; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th {{ background: #334155; padding: 10px 14px; text-align: left; color: #7dd3fc; }}
    td {{ padding: 8px 14px; border-bottom: 1px solid #334155; font-size: 0.9rem; }}
    tr:hover {{ background: #273549; }}
    code {{ background: #334155; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>🐺 Lyncus — Code Quality Report</h1>
  <p>Project: <code>{project_path}</code> &nbsp;|&nbsp; Language: <code>{language}</code> &nbsp;|&nbsp; Scan time: {scan_time:.1f}s</p>

  <div class="summary">
    <div class="card"><div class="num" style="color:{score_color}">{score}</div><div class="label">Score / 100</div></div>
    <div class="card"><div class="num" style="color:#ef4444">{critical}</div><div class="label">Critical</div></div>
    <div class="card"><div class="num" style="color:#f59e0b">{warnings}</div><div class="label">Warnings</div></div>
    <div class="card"><div class="num" style="color:#3b82f6">{info}</div><div class="label">Info</div></div>
  </div>

  <h2>Problems</h2>
  <table>
    <thead><tr><th>Severity</th><th>Category</th><th>Location</th><th>Message</th><th>Suggestion</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <p style="color:#475569;margin-top:24px;font-size:0.8rem">
    Generated by Lyncus v1.0.0 — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
  </p>
</body>
</html>"""

    Path(output_file).write_text(html, encoding="utf-8")
    console.print(f"  [green]✅ HTML report saved:[/green] {output_file}")
