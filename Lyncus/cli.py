"""
Lyncus CLI — Phase 4 Final Version
Commands: scan, doctor, install-deps, init, badge
Full Lyncus.toml support, SARIF output, badge generation.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape as rich_escape

from Lyncus.config.config_loader import LyncusConfig, load_config, write_default_config
from Lyncus.core.badge import generate_problems_badge, generate_score_badge
from Lyncus.core.detector import EXTENSION_MAP, detect_language, get_supported_languages
from Lyncus.core.html_reporter import export_html_report
from Lyncus.core.install_deps import install_missing, print_doctor_table
from Lyncus.core.parser import Problem, parse_results
from Lyncus.core.reporter import (
    export_json,
    make_progress,
    print_header,
    print_problems,
    print_summary,
)
from Lyncus.core.preview import (
    ToolPreview,
    build_preview,
    create_rapidcheck_runner,
    cleanup_rapidcheck_runner,
    print_preview,
)
from Lyncus.core.runner import (
    TOOL_REGISTRY,
    ToolConfig,
    ToolRunOptions,
    _project_test_tool,
    check_tool_available,
    get_available_tools,
    run_all_tools,
)
from Lyncus.core.sarif import export_sarif
from Lyncus.core.utils import calc_score  # ✅ Fix #10: shared score function
from Lyncus.rules.fake_test_rules import scan_file_for_fake_tests
from Lyncus.rules.hardcode_rules import scan_file_for_hardcode

console = Console()

# Named version constant — shared between cli.py and reporter.py
_LYNCUS_VERSION = "1.0.0"

SUPPORTED_LANGUAGES = get_supported_languages()


@dataclass
class _ScanOutputOptions:
    output: str
    severity: str
    report_file: str | None
    html_file: str | None
    sarif_file: str | None
    badge_file: str | None


@dataclass
class _ScanReport:
    cfg: LyncusConfig
    problems: list[Problem]
    scan_time: float
    files_scanned: int
    skipped_tools: list[str]
    path: str
    language: str
    available_tools: list[str]
    score: int
    critical_count: int
    warning_count: int


SKIP_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".ico",
    ".svg",
    ".json",
    ".zip",
    ".tar",
    ".gz",
    ".lock",
    ".whl",
    ".egg",
}

# Only source files handled by the supported language scanners are collected.
# This excludes documentation, configuration, reports, and other project data.
SOURCE_EXTENSIONS = frozenset(EXTENSION_MAP)

# Named size constants — avoid magic numbers
_MAX_FILE_SIZE_MB = 5
_BYTES_PER_MB = 1024 * 1024
# Skip files larger than 5 MB to prevent memory spikes
_MAX_FILE_SIZE = _MAX_FILE_SIZE_MB * _BYTES_PER_MB

SKIP_DIRS = {
    "venv",
    ".venv",
    "env",
    ".env",
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".cache",
    "cache",
    ".hypothesis",
    "target",
    "bin",
    "obj",
    ".ruff_cache",
    ".pytest_cache",
    "vendor",
    "packages",
    ".gradle",
    "cmake-build-debug",
}


# ── HELPERS ───────────────────────────────────────────────────────────────────


def _should_ignore_path(fpath: Path, root: Path, ignore_paths: list[str]) -> bool:
    """
    Check whether a file should be ignored based on configured ignore paths.

    Entries like 'Lyncus/rules/' in pyproject.toml [tool.Lyncus.ignore] paths are
    path prefixes, not bare directory names. We match against the relative path so
    that partial-path ignores work correctly across platforms.
    """
    try:
        rel = fpath.relative_to(root)
    except ValueError:
        rel = fpath

    rel_str = rel.as_posix()  # Windows pe bhi '/' use karo

    for ig in ignore_paths:
        ig_normalized = ig.strip().replace("\\", "/").rstrip("/")
        if not ig_normalized:
            continue
        # Exact prefix match — e.g. "Lyncus/rules" matches "Lyncus/rules/fake_test_rules.py"
        if rel_str == ig_normalized or rel_str.startswith(ig_normalized + "/"):
            return True
        # Sirf naam match bhi check karo — e.g. "rules/" matches any "rules" dir
        if Path(ig_normalized).name and rel_str.startswith(Path(ig_normalized).name + "/"):
            return True
    return False


def _collect_files(project_path: str, ignore_paths: list[str] | None = None) -> list[Path]:
    root = Path(project_path)
    if root.is_file():
        return [root] if root.suffix.lower() in SOURCE_EXTENSIONS else []

    # Simple dir-name set — fast O(1) lookup
    _ignore_dirnames = {
        Path(ig.strip().replace("\\", "/").rstrip("/")).name
        for ig in (ignore_paths or [])
        if ig.strip()
    }
    extra_ignore = SKIP_DIRS | _ignore_dirnames

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in extra_ignore]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fname.lower() == ".env" or fname.lower().startswith(".env."):
                continue
            if fpath.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            # Full relative-path check for deep entries like "Lyncus/rules/"
            if ignore_paths and _should_ignore_path(fpath, root, ignore_paths):
                continue
            files.append(fpath)
    return files


def _run_builtin_checks(
    files: list[Path],
    language: str,
    only: str | None,
    cfg: LyncusConfig,
    project_root: str | None = None,
) -> list[Problem]:
    problems: list[Problem] = []
    root = Path(project_root) if project_root else None

    for fpath in files:
        fpath_str = str(fpath)

        # Match against relative path from config root
        if root and cfg.ignore.paths and _should_ignore_path(fpath, root, cfg.ignore.paths):
            continue

        if any(ig.rstrip("/") in fpath_str for ig in cfg.ignore.files):
            continue
        try:
            if fpath.stat().st_size > _MAX_FILE_SIZE:
                continue
        except OSError:
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        problems.extend(_run_builtin_file_checks(fpath, fpath_str, content, language, only, cfg))

    return problems


def _run_builtin_file_checks(
    file_path: Path,
    file_name: str,
    content: str,
    language: str,
    only: str | None,
    cfg: LyncusConfig,
) -> list[Problem]:
    problems = []
    if only in (None, "hardcode"):
        problems.extend(_check_hardcode(file_name, content, cfg))
    if only in (None, "fake-tests") and _is_test_file(file_path):
        problems.extend(_check_fake_tests(file_name, content, language, cfg))
    return problems


def _check_hardcode(
    file_name: str,
    content: str,
    cfg: LyncusConfig,
) -> list[Problem]:
    return [
        Problem(
            tool="Lyncus-builtin",
            rule_id=match.rule_id,
            category=match.category,
            severity=match.severity,
            file=match.file,
            line=match.line,
            column=match.column,
            message=match.description,
            suggestion="",
        )
        for match in scan_file_for_hardcode(
            file_name,
            content,
            check_credentials=cfg.hardcode.check_credentials,
            check_paths=cfg.hardcode.check_paths,
            check_urls=cfg.hardcode.check_urls,
            check_magic_nums=cfg.hardcode.check_magic_numbers,
        )
        if match.rule_id not in cfg.ignore.rules
    ]


def _check_fake_tests(
    file_name: str,
    content: str,
    language: str,
    cfg: LyncusConfig,
) -> list[Problem]:
    return [
        Problem(
            tool="Lyncus-builtin",
            rule_id=match.rule_id,
            category="FAKE-TEST",
            severity=match.severity,
            file=file_name,
            line=match.line,
            column=0,
            message=match.description,
            suggestion=match.suggestion,
        )
        for match in scan_file_for_fake_tests(content, language)
        if match.rule_id not in cfg.ignore.rules
    ]


def _is_test_file(file_path: Path) -> bool:
    name = file_path.name.lower()
    return "test" in name or "spec" in name or name.endswith("_test.py")


# Alias for shared score utility
_calc_score = calc_score


def _enforce_ci_threshold(score: int, cfg: LyncusConfig, ci_mode: bool) -> None:
    """
    In CI mode, check the quality score against the configured threshold.
    Exits with code 1 if score is below cfg.thresholds.min_score.
    """
    if not ci_mode:
        return
    threshold = cfg.thresholds.min_score
    if score < threshold:
        console.print(
            f"\n[red]❌ CI FAIL: Quality score {score}/100 < threshold {threshold:.0f}[/red]"
        )
        raise SystemExit(1)
    console.print(
        f"\n[green]✅ CI PASS: Quality score {score}/100 ≥ threshold {threshold:.0f}[/green]"
    )


def _check_coverage_threshold(
    problems: list[Problem],
    cfg: LyncusConfig,
) -> list[Problem]:
    """
    Compare coverage findings against the configured threshold.
    Adds a warning problem if any file's coverage falls below min_coverage.
    """
    extra: list[Problem] = []
    seen_files: set[str] = set()

    for p in problems:
        if p.category != "COVERAGE":
            continue
        percent_index = p.message.find("%")
        if percent_index < 0:
            continue
        cov_val = _extract_coverage_percentage(p.message[:percent_index])
        if cov_val is None:
            continue
        if cov_val < cfg.thresholds.min_coverage and p.file not in seen_files:
            seen_files.add(p.file)
            extra.append(
                Problem(
                    tool="Lyncus-threshold",
                    rule_id="COV-THRESHOLD",
                    category="COVERAGE",
                    severity="warning",
                    file=p.file,
                    line=0,
                    column=0,
                    message=(
                        f"Coverage {cov_val:.1f}% < threshold {cfg.thresholds.min_coverage:.0f}% "
                        f"— add more tests or update the --coverage threshold"
                    ),
                    suggestion=f"Set min_coverage = {int(cov_val)} in Lyncus.toml or add tests",
                )
            )
    return extra


def _extract_coverage_percentage(message: str) -> float | None:
    parts = message.rstrip().split()
    if not parts:
        return None
    value = parts[-1]
    if not any(character.isdigit() for character in value) or not all(
        character.isdigit() or character == "." for character in value
    ):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _resolve_scan_language(path: str, lang: str) -> str:
    if lang != "auto":
        return lang
    try:
        detected_lang = detect_language(path).primary_language
    except FileNotFoundError as error:
        console.print(f"[red]❌ {error}[/red]")
        raise SystemExit(1) from None
    if detected_lang == "unknown":
        console.print("[red]❌ Could not detect language. Use --lang to specify.[/red]")
        raise SystemExit(1)
    return detected_lang


def _run_scan_checks(
    path: str,
    files: list[Path],
    language: str,
    only: str | None,
    cfg: LyncusConfig,
    verbose: bool = False,
) -> list[Problem]:
    all_problems: list[Problem] = []
    with make_progress() as progress:
        task = progress.add_task("Scanning...", total=100)
        progress.update(task, advance=20, description="Built-in checks...")
        all_problems.extend(_run_builtin_checks(files, language, only, cfg, project_root=path))
        progress.update(task, advance=20, description="External tools...")
        if only not in ("hardcode", "fake-tests"):
            results = asyncio.run(
                run_all_tools(
                    language=language,
                    project_path=path,
                    only=only,
                    skip_unavailable=cfg.tools.skip_unavailable,
                    options=ToolRunOptions(
                        timeout_seconds=cfg.scan.timeout,
                        tool_timeouts=cfg.tools.timeouts,
                    ),
                    skip_slow=cfg.tools.skip_slow,
                    verbose=verbose,
                )
            )
            progress.update(task, advance=40, description="Parsing results...")
            tool_problems = [
                problem
                for problem in parse_results(results)
                if problem.rule_id not in cfg.ignore.rules
            ]
            all_problems.extend(tool_problems)
            all_problems.extend(_check_coverage_threshold(tool_problems, cfg))
        progress.update(task, advance=20, description="Building reports...")
    return all_problems


def _write_scan_outputs(
    options: _ScanOutputOptions,
    report: _ScanReport,
) -> None:
    # Count tools that actually ran (not skipped) — used for score N/A logic
    ran_tools_count = len(report.available_tools)

    do_all = options.output == "all"
    if options.output == "table" or do_all:
        # Show score/counts before potentially long findings so the score stays visible.
        print_summary(
            problems=report.problems,
            scan_time=report.scan_time,
            files_scanned=report.files_scanned,
            skipped_tools=report.skipped_tools,
            ran_tools=ran_tools_count,
        )
        print_problems(report.problems, severity_filter=options.severity)
    if options.output == "json" or do_all:
        export_json(
            report.problems,
            report.path,
            report.language,
            report.scan_time,
            options.report_file or report.cfg.report.json_file,
            ran_tools=ran_tools_count,
        )
    if options.output == "html" or do_all:
        html_output = options.html_file or report.cfg.report.html_file
        export_html_report(
            problems=report.problems,
            project_path=report.path,
            language=report.language,
            tools_used=report.available_tools or ["Lyncus-builtin"],
            scan_time=report.scan_time,
            output_file=html_output,
        )
        console.print(f"  [green]✅ HTML report saved:[/green] {html_output}")
    if options.output == "sarif" or do_all:
        sarif_output = options.sarif_file or report.cfg.report.sarif_file
        export_sarif(
            report.problems,
            report.path,
            report.language,
            report.scan_time,
            sarif_output,
        )
        console.print(f"  [green]✅ SARIF report saved:[/green] {sarif_output}")
    if do_all or options.badge_file:
        _write_badges(
            options.badge_file or report.cfg.report.badge_file,
            report.score,
            report.critical_count,
            report.warning_count,
        )


def _write_badges(
    badge_file: str,
    score: int,
    critical_count: int,
    warning_count: int,
) -> None:
    generate_score_badge(score, badge_file)
    issues_badge = str(Path(badge_file).with_name(Path(badge_file).stem + "-issues.svg"))
    generate_problems_badge(critical_count, warning_count, issues_badge)
    console.print(f"  [green]✅ Badge saved:[/green] {badge_file}")


def _display_mutation_score(problems: list[Problem]) -> None:
    """
    Display mutation testing score if results are present.
    Parses killed/survived/total from mutmut JSON output.
    """
    import json as _json

    mutation_results = [p for p in problems if p.tool in ("mutmut",) and p.category in ("MUTATION", "faketests")]
    if not mutation_results:
        # Attempt to parse mutmut JSON output directly
        try:
            import os as _os
            stats_path = _os.path.join("mutants", "mutmut-cicd-stats.json")
            if _os.path.exists(stats_path):
                data = _json.loads(open(stats_path, encoding="utf-8").read())
                killed = data.get("killed", 0)
                survived = data.get("survived", 0)
                total = killed + survived
                if total > 0:
                    mut_score = int((killed / total) * 100)
                    color = "green" if mut_score >= 70 else "yellow" if mut_score >= 40 else "red"
                    console.print()
                    console.print(
                        f"  [bold magenta]🧬 Mutation Score:[/bold magenta] "
                        f"[bold {color}]{mut_score}/100[/bold {color}]  "
                        f"[dim](killed {killed}/{total} mutants)[/dim]"
                    )
        except Exception:
            pass
        return

    # Also check problem list directly
    for p in mutation_results:
        if "%" in p.message:
            console.print(f"\n  [bold magenta]🧬 Mutation Result:[/bold magenta] {p.message}")


def _auto_install_missing_tools(
    detected_lang: str,
    skipped_tools: list[str],
    project_path: str = ".",
    skip_slow: bool = False,
) -> tuple[list[str], list[str]]:
    """
    Install missing scanner, test, property, and supported mutation tools for this project.
    Returns: (available_tools, skipped_tools) updated lists.
    """
    from Lyncus.core.install_deps import install_tool_commands
    from Lyncus.core.platform import should_skip_tool_on_platform

    test_tool = _project_test_tool(detected_lang, project_path)
    commands = _collect_scanner_install_commands(
        detected_lang, skipped_tools, test_tool, skip_slow
    )
    preview_result = build_preview(detected_lang, project_path)
    _collect_preview_install_commands(
        preview_result.missing_tools, test_tool, commands, skip_slow
    )

    mutation = preview_result.mutation
    if mutation and mutation.supported and mutation.platform_ok and not mutation.installed:
        if not skip_slow and mutation.install_cmd:
            commands.setdefault(mutation.tool, mutation.install_cmd)

    if commands:
        from Lyncus.core.platform import is_ci
        ci_note = " (all tools will be available in CI/CD)" if not is_ci() else ""
        console.print(
            f"  [yellow]📦 {len(commands)} project tool(s) missing — "
            f"auto-installing (pip/npm/cargo only)...{ci_note}[/yellow]"
        )
        install_tool_commands(commands)

    tool_availability = get_available_tools(detected_lang)
    available = [
        name for name, ok in tool_availability.items()
        if ok and not should_skip_tool_on_platform(name)[0]
    ]
    skipped = []
    for name, is_available in tool_availability.items():
        if is_available:
            continue
        should_skip, _ = should_skip_tool_on_platform(name)
        if not should_skip:
            skipped.append(name)
    if test_tool:
        # Verify test_tool belongs to the detected language before listing it
        lang_key = "javascript" if detected_lang == "typescript" else detected_lang
        if test_tool.language in {lang_key, detected_lang}:
            if check_tool_available(test_tool.name):
                if test_tool.name not in available:
                    available.append(test_tool.name)
            elif test_tool.name not in skipped:
                skipped.append(test_tool.name)
    if skipped:
        _display_skipped_tool_hints(skipped, detected_lang)
    return available, skipped


def _display_skipped_tool_hints(skipped: list[str], detected_lang: str) -> None:
    """Print user-friendly install hints for skipped tools."""
    _SYSTEM_MGR_PREFIXES = ("winget ", "choco ", "brew ", "apt ", "apt-get ", "snap ")
    system_tools: list[str] = []
    other_tools: list[str] = []
    for name in skipped:
        registry_tool = next((t for t in TOOL_REGISTRY if t.name == name), None)
        if registry_tool and registry_tool.install_cmd:
            candidates = [p.strip() for p in registry_tool.install_cmd.split(" / ") if p.strip()]
            if all(c.lower().startswith(_SYSTEM_MGR_PREFIXES) for c in candidates):
                system_tools.append(name)
                continue
        other_tools.append(name)

    if system_tools:
        safe_system = rich_escape(", ".join(system_tools))
        safe_lang = rich_escape(detected_lang)
        console.print(
            f"  [dim]ℹ  System-installer tools (winget/apt/brew) not auto-installed: "
            f"{safe_system}[/dim]"
        )
        console.print(
            f"     [dim]→ Local install: [bold]Lyncus install-deps --lang {safe_lang}[/bold][/dim]"
        )
        console.print(
            f"     [dim]→ CI/CD (GitHub Actions): these tools install automatically "
            f"on ubuntu-latest runners.[/dim]"
        )
    if other_tools:
        non_vcpkg = [t for t in other_tools if t != "rapidcheck"]
        vcpkg_tools = [t for t in other_tools if t == "rapidcheck"]
        if non_vcpkg:
            console.print(
                f"  [dim]ℹ  Could not install: {rich_escape(', '.join(non_vcpkg))} "
                f"— run 'Lyncus doctor' for manual install commands.[/dim]"
            )
        if vcpkg_tools:
            console.print(
                "  [dim]ℹ  rapidcheck: vcpkg manifest mode detected — "
                "add 'rapidcheck' to vcpkg.json then run 'vcpkg install'[/dim]"
            )


def _collect_scanner_install_commands(
    detected_lang: str,
    skipped_tools: list[str],
    test_tool: ToolConfig | None,
    skip_slow: bool,
) -> dict[str, str]:
    from Lyncus.core.platform import should_skip_tool_on_platform

    lang_key = "javascript" if detected_lang == "typescript" else detected_lang
    # Only install tools that belong to the detected language — never cross-language
    allowed_languages = {lang_key, detected_lang}
    # These are slow (winget = minutes), may need elevation, and block the scan.
    # Users must run 'Lyncus install-deps --lang <lang>' for these manually.
    SYSTEM_MANAGER_PREFIXES = (
        "winget ", "choco ", "brew ",
        "apt ", "apt-get ", "snap ",
    )

    commands: dict[str, str] = {}
    for tool in TOOL_REGISTRY:
        # Hard guard: skip any tool whose language does not match detected lang
        if tool.language not in allowed_languages:
            continue
        if tool.name == "pytest-cov" and test_tool is None:
            continue
        if tool.name in skipped_tools and tool.install_cmd:
            should_skip, _ = should_skip_tool_on_platform(tool.name)
            if should_skip or (skip_slow and tool.check_type in {"coverage", "faketests"}):
                continue
            # Skip tools whose ONLY install path is a system manager
            # (e.g. cppcheck on Windows requires winget/choco — not auto-installable)
            all_candidates = [p.strip() for p in tool.install_cmd.split(" / ") if p.strip()]
            has_safe_install = any(
                not c.lower().startswith(SYSTEM_MANAGER_PREFIXES)
                for c in all_candidates
            )
            if not has_safe_install:
                # Show a one-time install hint in install_tool_commands output
                continue
            commands[tool.name] = tool.install_cmd
    if test_tool and not check_tool_available(test_tool.name) and test_tool.install_cmd:
        # Also guard test_tool language
        test_lang_key = "javascript" if detected_lang == "typescript" else detected_lang
        if test_tool.language in {test_lang_key, detected_lang}:
            all_candidates = [p.strip() for p in test_tool.install_cmd.split(" / ") if p.strip()]
            has_safe_install = any(
                not c.lower().startswith(SYSTEM_MANAGER_PREFIXES)
                for c in all_candidates
            )
            if has_safe_install:
                commands[test_tool.name] = test_tool.install_cmd
    return commands


def _collect_preview_install_commands(
    missing_tools: list[ToolPreview],
    test_tool: ToolConfig | None,
    commands: dict[str, str],
    skip_slow: bool,
) -> None:
    for preview_tool in missing_tools:
        if (
            preview_tool.name == "rapidcheck"
            and test_tool is not None
            and shutil.which("vcpkg")
        ):
            # vcpkg manifest mode: `vcpkg install <pkg>` does not work here.
            # The user must add 'rapidcheck' to vcpkg.json and run `vcpkg install` manually.
            # Skip auto-install and show an informative hint instead.
            commands.pop("rapidcheck", None)
            continue
        if preview_tool.auto_create or preview_tool.check_type == "mutation" or not preview_tool.install_cmd:
            continue
        if preview_tool.check_type == "property" and test_tool is None:
            continue
        if preview_tool.name == "hypothesis":
            if test_tool is None or "pytest-cov" in commands:
                continue
        if skip_slow and preview_tool.check_type == "coverage":
            continue
        commands.setdefault(preview_tool.name, preview_tool.install_cmd)


def _pre_scan_setup(
    path: str,
    detected_lang: str,
    cfg: LyncusConfig,
    skip_slow: bool,
) -> tuple[bool, list[str], list[str]]:
    """
    Pre-scan setup:
      - mutation platform check
      - project-aware test/property tool detection
      - tool availability + auto-install
    Returns: (rapidcheck_created, available_tools, skipped_tools)
    """
    rapidcheck_created = False

    if not skip_slow:
        preview_result = build_preview(detected_lang, path)

        if preview_result.mutation and not preview_result.mutation.platform_ok:
            console.print(
                f"  [dim]ℹ  {preview_result.mutation.tool} skipped on this platform.[/dim]"
            )

    tool_availability = get_available_tools(detected_lang)
    available_tools = [t for t, ok in tool_availability.items() if ok]
    skipped_tools = [t for t, ok in tool_availability.items() if not ok]
    available_tools, skipped_tools = _auto_install_missing_tools(
        detected_lang,
        skipped_tools,
        project_path=path,
        skip_slow=skip_slow,
    )

    return rapidcheck_created, available_tools, skipped_tools


def _post_scan_exit(
    all_problems: list[Problem],
    scan_time: float,
    files: list[Path],
    path: str,
    detected_lang: str,
    available_tools: list[str],
    skipped_tools: list[str],
    cfg: LyncusConfig,
    options: _ScanOutputOptions,
    ci_mode: bool,
    fail_on: str,
) -> None:
    """Post-scan: reports, mutation display, CI check, exit code."""
    score = _calc_score(all_problems)
    critical_count = sum(1 for p in all_problems if p.severity == "critical")
    warning_count = sum(1 for p in all_problems if p.severity == "warning")

    _write_scan_outputs(
        options,
        _ScanReport(
            cfg=cfg,
            problems=all_problems,
            scan_time=scan_time,
            files_scanned=len(files),
            skipped_tools=skipped_tools,
            path=path,
            language=detected_lang,
            available_tools=available_tools,
            score=score,
            critical_count=critical_count,
            warning_count=warning_count,
        ),
    )
    _display_mutation_score(all_problems)
    _enforce_ci_threshold(score, cfg, ci_mode)

    should_fail = (
        (fail_on == "critical" and critical_count > 0)
        or (fail_on == "warning" and (critical_count + warning_count) > 0)
        or (fail_on == "any" and len(all_problems) > 0)
    )
    raise SystemExit(1 if should_fail else 0)


# ── CLI GROUP ─────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(_LYNCUS_VERSION, prog_name="🐺 Lyncus")
def main() -> None:
    """
    🐺 Lyncus — Multi-language code quality scanner.

    "Jo dikhta nahi, woh pakad lega"
    """
    pass


# ── SCAN COMMAND ──────────────────────────────────────────────────────────────


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--lang",
    "-l",
    default="auto",
    help=f"Language. Options: auto, {', '.join(SUPPORTED_LANGUAGES)}",
)
@click.option(
    "--only",
    "-o",
    default=None,
    type=click.Choice(["hardcode", "fake-tests", "dead-code", "security", "quality"]),
    help="Run only one category of checks.",
)
@click.option(
    "--severity",
    "-s",
    default="all",
    type=click.Choice(["all", "critical", "warning", "info"]),
    help="Severity filter.",
)
@click.option(
    "--output",
    "-f",
    default=None,
    type=click.Choice(["table", "json", "html", "sarif", "all"]),
    help="Output format. 'all' = table + JSON + HTML + SARIF + badge.",
)
@click.option("--report-file", default=None, help="JSON report output filename.")
@click.option("--html-file", default=None, help="HTML report output filename.")
@click.option("--sarif-file", default=None, help="SARIF output filename.")
@click.option("--badge-file", default=None, help="SVG badge output filename.")
@click.option(
    "--config",
    "-c",
    default=None,
    type=click.Path(exists=True),
    help="Lyncus.toml config file path.",
)
@click.option("--ci-mode", is_flag=True, help="CI mode — fail if score is below threshold.")
@click.option("--skip-slow", is_flag=True, help="Skip mutation testing and other slow tools.")
@click.option("--verbose", "-v", is_flag=True, help="Show real-time status for each tool.")
@click.option(
    "--fail-on",
    default="critical",
    type=click.Choice(["critical", "warning", "any", "never"]),
    help="When to return exit code 1.",
)
def scan(
    path: str,
    lang: str,
    only: str | None,
    severity: str,
    output: str,
    report_file: str | None,
    html_file: str | None,
    sarif_file: str | None,
    badge_file: str | None,
    config: str | None,
    ci_mode: bool,
    skip_slow: bool,
    verbose: bool,
    fail_on: str,
) -> None:
    """
    Scan a project for code quality issues.

    \b
    Examples:
      Lyncus scan .
      Lyncus scan ./src --lang python --severity critical
      Lyncus scan . --output all          ← generate all report formats
      Lyncus scan . --only hardcode
      Lyncus scan . --ci-mode --fail-on critical
      Lyncus scan . --config Lyncus.toml
      Lyncus scan . --verbose             ← show live status per tool
    """
    start_time = time.time()
    cfg = load_config(project_path=path, config_file=config)
    cfg.tools.skip_slow = cfg.tools.skip_slow or skip_slow
    output = output or cfg.scan.output or "table"
    detected_lang = _resolve_scan_language(path, lang)

    # ── PRE-SCAN: Language-specific checks + tool availability ───────────────
    _rapidcheck_created, available_tools, skipped_tools = _pre_scan_setup(
        path, detected_lang, cfg, skip_slow=cfg.tools.skip_slow
    )

    # Collect skip reasons for each skipped tool — used in print_header
    from Lyncus.core.platform import should_skip_tool_on_platform
    _skipped_reasons: dict[str, str] = {}
    for _tool_name in skipped_tools:
        _skip, _reason = should_skip_tool_on_platform(_tool_name)
        if _skip and _reason:
            _skipped_reasons[_tool_name] = _reason
        elif _tool_name not in _skipped_reasons:
            _skipped_reasons[_tool_name] = "not installed"

    print_header(
        path,
        detected_lang,
        available_tools or ["Lyncus-builtin"],
        skipped_tools=skipped_tools,
        skipped_reasons=_skipped_reasons,
    )
    files = _collect_files(path, cfg.ignore.paths)
    all_problems = _run_scan_checks(path, files, detected_lang, only, cfg, verbose=verbose)

    # ── POST-SCAN: RapidCheck cleanup ─────────────────────────────────────────
    if _rapidcheck_created:
        cleanup_rapidcheck_runner(path)
        console.print("  [dim]🧹 RapidCheck runner cleaned up.[/dim]")
    scan_time = time.time() - start_time
    score = _calc_score(all_problems)
    critical_count = sum(1 for p in all_problems if p.severity == "critical")
    warning_count = sum(1 for p in all_problems if p.severity == "warning")
    _write_scan_outputs(
        _ScanOutputOptions(
            output=output,
            severity=severity,
            report_file=report_file,
            html_file=html_file,
            sarif_file=sarif_file,
            badge_file=badge_file,
        ),
        _ScanReport(
            cfg=cfg,
            problems=all_problems,
            scan_time=scan_time,
            files_scanned=len(files),
            skipped_tools=skipped_tools,
            path=path,
            language=detected_lang,
            available_tools=available_tools,
            score=score,
            critical_count=critical_count,
            warning_count=warning_count,
        ),
    )

    # ── Mutation Score ─────────────────────────────────────────────────────────
    _display_mutation_score(all_problems)

    _enforce_ci_threshold(score, cfg, ci_mode)
    should_fail = (
        (fail_on == "critical" and critical_count > 0)
        or (fail_on == "warning" and (critical_count + warning_count) > 0)
        or (fail_on == "any" and len(all_problems) > 0)
    )
    raise SystemExit(1 if should_fail else 0)


# ── DOCTOR COMMAND ────────────────────────────────────────────────────────────


@main.command()
@click.option("--lang", "-l", default="all", help="Check tools for a specific language.")
def doctor(lang: str) -> None:
    """
    System check — show installed tools and their status.

    \b
    Examples:
      Lyncus doctor
      Lyncus doctor --lang python
      Lyncus doctor --lang rust
    """
    console.print()
    console.print("[bold cyan]🐺 Lyncus — System Check[/bold cyan]\n")
    print_doctor_table(lang)


# ── INSTALL-DEPS COMMAND ──────────────────────────────────────────────────────


@main.command("install-deps")
@click.option("--lang", "-l", default="python", help="Install dependencies for a specific language.")
@click.option("--all", "install_all", is_flag=True, help="Install dependencies for all languages.")
@click.option("--dry-run", is_flag=True, help="Print commands only, do not execute.")
def install_deps_cmd(lang: str, install_all: bool, dry_run: bool) -> None:
    """
    Install missing tools (OS-aware).

    \b
    Examples:
      Lyncus install-deps --lang python
      Lyncus install-deps --lang ruby
      Lyncus install-deps --all --dry-run
    """
    target = "all" if install_all else lang
    if dry_run:
        console.print("[dim]Dry run mode — printing commands only, not executing[/dim]\n")
    install_missing(language=target, dry_run=dry_run)


# ── INIT COMMAND ──────────────────────────────────────────────────────────────


@main.command()
@click.option(
    "--output", "-o", default="Lyncus.toml", help="Config filename (default: Lyncus.toml)."
)
@click.option("--force", is_flag=True, help="Overwrite existing config file.")
def init(output: str, force: bool) -> None:
    """
    Create a Lyncus.toml config file in the project.

    \b
    Examples:
      Lyncus init
      Lyncus init --output .Lyncus.toml
      Lyncus init --force
    """
    outpath = Path(output)
    if outpath.exists() and not force:
        console.print(
            f"[yellow]⚠️  {output} already exists. Use --force to overwrite.[/yellow]"
        )
        raise SystemExit(1)

    write_default_config(output)
    console.print(f"[green]✅ Config file created:[/green] {output}")
    console.print("[dim]   Edit it to match your preferences.[/dim]")
    console.print("[dim]   Docs: https://github.com/yourname/Lyncus#configuration[/dim]")


# ── PREVIEW COMMAND ───────────────────────────────────────────────────────────


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--lang",
    "-l",
    default="auto",
    help=f"Language. Options: auto, {', '.join(SUPPORTED_LANGUAGES)}",
)
@click.option("--no-prompt", is_flag=True, help="Skip the interactive scan prompt (for CI use).")
def preview(path: str, lang: str, no_prompt: bool) -> None:
    """
    Show a project preview before scanning — tools, status, install commands.

    \b
    What it shows:
      • Detected language
      • Which tools are installed / missing
      • Mutation testing availability
      • RapidCheck / Hypothesis auto-runner status
      • Install commands for missing tools
      • Suggested scan command

    \b
    Examples:
      Lyncus preview .
      Lyncus preview ./src --lang cuda
      Lyncus preview . --no-prompt      ← for CI/scripting
    """
    detected_lang = _resolve_scan_language(path, lang)
    result = build_preview(detected_lang, path)
    user_wants_scan = print_preview(result, interactive=not no_prompt)

    if user_wants_scan:
        console.print(f"\n  [bold green]▶ Starting scan...[/bold green]\n")
        # Mutation check first
        mutation_info = result.mutation
        run_mutation = mutation_info is None or mutation_info.platform_ok
        if mutation_info is not None and not mutation_info.platform_ok:
            console.print(
                f"  [dim]ℹ  {mutation_info.tool} skipped on this platform.[/dim]"
            )

        # RapidCheck auto-runner if needed
        rapidcheck_created = False
        rc_tool = next((t for t in result.tools if t.name == "rapidcheck" and t.auto_create and not t.installed), None)
        if rapidcheck_created:
            success, msg = create_rapidcheck_runner(path)
            if success:
                rapidcheck_created = True
                console.print(f"  [yellow]🔧 RapidCheck runner created:[/yellow] {msg}")

        # Actual scan — ctx.invoke preserves real-time output
        try:
            ctx = click.get_current_context()
            scan_kwargs: dict[str, object] = {
                "path": path,
                "lang": detected_lang,
                "only": None,
                "severity": "all",
                "output": None,
                "report_file": None,
                "html_file": None,
                "sarif_file": None,
                "badge_file": None,
                "config": None,
                "ci_mode": False,
                "skip_slow": not run_mutation,
                "verbose": False,
                "fail_on": "critical",
            }
            ctx.invoke(scan, **scan_kwargs)
        except SystemExit as e:
            # Cleanup rapidcheck runner
            if rapidcheck_created:
                cleanup_rapidcheck_runner(path)
            raise
        except Exception:
            if rapidcheck_created:
                cleanup_rapidcheck_runner(path)
            raise

        # Cleanup rapidcheck runner (success case)
        if rapidcheck_created:
            cleanup_rapidcheck_runner(path)


# ── BADGE COMMAND ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--score", "-s", required=True, type=int, help="Quality score (0–100).")
@click.option("--critical", "-c", default=0, type=int, help="Number of critical issues.")
@click.option("--warnings", "-w", default=0, type=int, help="Number of warnings.")
@click.option("--language", "-l", default=None, help="Also generate a language badge.")
@click.option("--output", "-o", default="Lyncus-badge.svg", help="Badge output filename.")
def badge(score: int, critical: int, warnings: int, language: str | None, output: str) -> None:
    """
    Generate an SVG badge — embed it in your README.

    \b
    Examples:
      Lyncus badge --score 87
      Lyncus badge --score 42 --critical 3 --warnings 5
      Lyncus badge --score 95 --language python --output badges/python.svg

    Add to README:
      ![Lyncus Score](Lyncus-badge.svg)
    """
    score = max(0, min(100, score))

    generate_score_badge(score, output)
    console.print(f"[green]✅ Score badge saved:[/green] {output}")

    if critical >= 0 or warnings >= 0:
        # Fix #9: Use Path.stem so the name is correct even without a .svg extension
        issues_file = str(Path(output).with_name(Path(output).stem + "-issues.svg"))
        generate_problems_badge(critical, warnings, issues_file)
        console.print(f"[green]✅ Issues badge saved:[/green] {issues_file}")

    if language:
        from Lyncus.core.badge import generate_language_badge

        lang_file = str(Path(output).with_name(Path(output).stem + f"-{language.lower()}.svg"))
        generate_language_badge(language, lang_file)
        console.print(f"[green]✅ Language badge saved:[/green] {lang_file}")

    console.print("\n[dim]Add to README:[/dim]")
    console.print(f"[cyan]  ![Lyncus Score]({output})[/cyan]")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
