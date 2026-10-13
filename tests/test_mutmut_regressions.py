"""Focused boundary tests for helpers with surviving mutation variants."""

from __future__ import annotations

import json
from pathlib import Path

from Lyncus import resolve_language
from Lyncus.cli import (
    _MAX_FILE_SIZE,
    SKIP_DIRS,
    SKIP_EXTENSIONS,
    _check_coverage_threshold,
    _collect_files,
    _run_builtin_checks,
)
from Lyncus.config.config_loader import LyncusConfig
from Lyncus.core.parser import Problem


def test_resolve_language_normalizes_and_preserves_unknown_names() -> None:
    assert resolve_language(" PY ") == " py "
    assert resolve_language("PY") == "python"
    assert resolve_language("NodeJS") == "javascript"
    assert resolve_language("Haskell") == "haskell"


def test_collect_files_handles_single_file_extensions_and_ignored_dirs(tmp_path: Path) -> None:
    source = tmp_path / "single.PY"
    source.write_text("pass", encoding="utf-8")
    assert _collect_files(str(source)) == [source]

    root = tmp_path / "project"
    root.mkdir()
    accepted = root / "keep.py"
    accepted.write_text("pass", encoding="utf-8")
    for extension in SKIP_EXTENSIONS:
        (root / f"skip{extension}").write_text("x", encoding="utf-8")
    for dirname in SKIP_DIRS:
        nested = root / dirname
        nested.mkdir()
        (nested / "hidden.py").write_text("pass", encoding="utf-8")
    custom = root / "custom"
    custom.mkdir()
    (custom / "ignored.py").write_text("pass", encoding="utf-8")
    result = _collect_files(str(root), ["custom"])
    assert result == [accepted]
    assert set(_collect_files(str(root), [])) == {accepted, custom / "ignored.py"}


def test_builtin_checks_respects_filters_ignore_lists_and_oversize_files(tmp_path: Path) -> None:
    cfg = LyncusConfig()
    secret = tmp_path / "ordinary.py"
    # Env var se value lo — hardcode mat karo
    secret.write_text('password = "secret-value"\n', encoding="utf-8")
    ignored = tmp_path / "skip.py"
    ignored.write_text('password = "secret-value"\n', encoding="utf-8")
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_fake():\n    assert True\n", encoding="utf-8")

    cfg.ignore.files = ["skip.py"]
    cfg.ignore.rules = ["HC001", "HC005", "FT001", "FT006"]
    result = _run_builtin_checks([secret, ignored, test_file], "python", None, cfg)
    assert result == [], f"Ignore rules ke baad koi problem nahi honi chahiye, mili: {result}"

    cfg.ignore.rules = []
    hardcode_only = _run_builtin_checks([secret, test_file], "python", "hardcode", cfg)
    fake_only = _run_builtin_checks([secret, test_file], "python", "fake-tests", cfg)

    assert len(hardcode_only) > 0, "Hardcode problems milni chahiye"
    assert all(problem.rule_id.startswith("HC") for problem in hardcode_only), (
        f"Sab hardcode problems HC se shuru honin chahiye: {[p.rule_id for p in hardcode_only]}"
    )

    assert len(fake_only) > 0, "Fake test problems milni chahiye"
    fake_rule_ids = {problem.rule_id for problem in fake_only}
    assert fake_rule_ids == {"FT001", "FT006"}, (
        f"Expected {{FT001, FT006}}, mila: {fake_rule_ids}"
    )

    quality_result = _run_builtin_checks([secret], "python", "quality", cfg)
    assert quality_result == [], (
        f"Quality filter pe builtin checks nahi chalne chahiye, mila: {quality_result}"
    )

    oversized = tmp_path / "large.py"
    oversized.write_text("x", encoding="utf-8")
    oversized.stat()
    oversized.write_bytes(b"x" * (_MAX_FILE_SIZE + 1))
    oversize_result = _run_builtin_checks([oversized], "python", None, cfg)
    assert oversize_result == [], (
        f"Oversized file skip honi chahiye, mila: {oversize_result}"
    )


def test_builtin_checks_skips_unreadable_or_missing_files(tmp_path: Path, monkeypatch) -> None:
    cfg = LyncusConfig()
    missing = tmp_path / "missing.py"
    assert _run_builtin_checks([missing], "python", None, cfg) == []

    source = tmp_path / "unreadable.py"
    source.write_text("pass", encoding="utf-8")
    original = Path.read_text

    def fail_read(path: Path, *args, **kwargs):
        if path == source:
            raise OSError("unreadable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    assert _run_builtin_checks([source], "python", None, cfg) == []


def test_coverage_threshold_deduplicates_and_ignores_invalid_or_high_values() -> None:
    cfg = LyncusConfig()
    cfg.thresholds.min_coverage = 80
    problems = [
        Problem("pytest", "COV", "COVERAGE", "info", "a.py", 1, 0, "coverage: 79.9%"),
        Problem("pytest", "COV", "COVERAGE", "info", "a.py", 2, 0, "coverage: 10%"),
        Problem("pytest", "COV", "COVERAGE", "info", "b.py", 1, 0, "coverage: 80%"),
        Problem("pytest", "COV", "COVERAGE", "info", "c.py", 1, 0, "coverage unknown"),
        Problem("pytest", "X", "QUALITY", "info", "d.py", 1, 0, "coverage: 1%"),
    ]
    findings = _check_coverage_threshold(problems, cfg)
    assert len(findings) == 1
    assert findings[0].file == "a.py"
    assert findings[0].rule_id == "COV-THRESHOLD"
    assert "79.9%" in findings[0].message


def test_javascript_json_parsers_cover_valid_empty_and_invalid_inputs() -> None:
    from Lyncus.languages.js_checks import (
        parse_depcheck_json,
        parse_npm_audit_json,
        parse_ts_prune_output,
        parse_tsc_output,
    )

    audit = parse_npm_audit_json(
        json.dumps(
            {
                "vulnerabilities": {
                    "pkg": {
                        "severity": "high",
                        "via": [{"title": "CVE", "cve": "CVE-1"}],
                        "fixAvailable": {"version": "2.0"},
                    },
                    "transitive": {"severity": "low", "via": ["pkg"]},
                }
            }
        )
    )
    assert audit == [
        {
            "package": "pkg",
            "severity": "critical",
            "title": "CVE",
            "cve": "CVE-1",
            "url": "",
            "fixed_in": "2.0",
            "description": "pkg: CVE",
        }
    ]
    assert parse_npm_audit_json("{") == []

    depcheck = parse_depcheck_json(
        json.dumps({"dependencies": ["unused"], "missing": {"required": [], "used": ["src/a.js"]}})
    )
    assert [issue["rule_id"] for issue in depcheck] == [
        "DEPCHECK-UNUSED",
        "DEPCHECK-MISSING",
        "DEPCHECK-MISSING",
    ]
    assert depcheck[1]["file"] == "unknown"
    assert depcheck[2]["file"] == "src/a.js"
    assert parse_depcheck_json("not json") == []

    typed = parse_tsc_output("src/a.ts(4,7): error TS2345: bad type\n")
    assert typed[0]["line"] == 4
    assert typed[0]["column"] == 7
    assert typed[0]["severity"] == "critical"
    assert typed[0]["category"] == "TYPE"
    assert parse_tsc_output("") == []

    pruned = parse_ts_prune_output(
        "src/a.ts:5 - deadExport\nsrc/a.ts:6 - usedExport (used in module)\n"
    )
    assert len(pruned) == 1
    assert pruned[0]["rule_id"] == "TS-PRUNE"
    assert pruned[0]["message"] == "Unused export: 'deadExport'"


def test_javascript_project_discovery_and_typescript_detection(tmp_path: Path) -> None:
    from Lyncus.languages.js_checks import find_package_json, is_typescript_project

    assert find_package_json(str(tmp_path)) is None
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert find_package_json(str(tmp_path)) == str(tmp_path)
    assert find_package_json(str(tmp_path / "package.json")) == str(tmp_path)
    assert not is_typescript_project(str(tmp_path))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.tsx").write_text("", encoding="utf-8")
    assert is_typescript_project(str(tmp_path))


def test_checkstyle_xml_and_source_categories() -> None:
    from Lyncus.languages.java_checks import _checkstyle_category, parse_checkstyle_xml

    xml = """<checkstyle><file name="A.java">
      <error line="3" column="2" severity="error" message="bad" source="com.checkstyle.naming.Name"/>
      <error line="4" message="format" source="com.checkstyle.whitespace.Space"/>
    </file></checkstyle>"""
    results = parse_checkstyle_xml(xml)
    assert len(results) == 2
    assert results[0]["file"] == "A.java"
    assert results[0]["line"] == 3
    assert results[0]["column"] == 2
    assert results[0]["severity"] == "critical"
    assert results[0]["rule_id"] == "CS-Name"
    assert results[0]["category"] == "NAMING"
    assert results[1]["column"] == 0
    assert results[1]["category"] == "STYLE"
    assert parse_checkstyle_xml("<invalid") == []
    assert _checkstyle_category("pkg.metrics.Complexity") == "COMPLEXITY"
    assert _checkstyle_category("pkg.unknown.Rule") == "STYLE"


def test_spotbugs_parser_handles_fields_defaults_and_invalid_files(tmp_path: Path) -> None:
    from Lyncus.languages.java_checks import parse_spotbugs_xml

    report = tmp_path / "spotbugs.xml"
    report.write_text(
        """<BugCollection>
          <BugInstance type="SQL_INJECTION" priority="1" category="SECURITY">
            <ShortMessage>Unsafe query</ShortMessage>
            <SourceLine sourcepath="src/App.java" start="17"/>
          </BugInstance>
          <BugInstance type="UNKNOWN"/>
          <BugInstance type="LOW" priority="3" category="PERFORMANCE">
            <ShortMessage/>
          </BugInstance>
        </BugCollection>""",
        encoding="utf-8",
    )

    issues = parse_spotbugs_xml(str(report))
    assert len(issues) == 3
    assert issues[0]["file"] == "src/App.java"
    assert issues[0]["line"] == 17
    assert issues[0]["severity"] == "critical"
    assert issues[0]["category"] == "SECURITY"
    assert issues[0]["rule_id"] == "SB-SQL_INJECTION"
    assert issues[0]["message"] == "Unsafe query"
    assert issues[1]["severity"] == "warning"
    assert issues[1]["category"] == "BUGPRONE"
    assert issues[1]["message"] == "UNKNOWN"
    assert issues[2]["severity"] == "info"
    assert issues[2]["category"] == "PERF"
    assert parse_spotbugs_xml(str(tmp_path / "missing.xml")) == []


def test_python_severity_and_description_helpers_cover_boundaries() -> None:
    from Lyncus.languages.python_checks import get_radon_description, get_ruff_severity

    assert get_ruff_severity("S101") == "critical"
    assert get_ruff_severity("F401") == "warning"
    assert get_ruff_severity("W291") == "warning"
    assert get_ruff_severity("ZZZ") == "info"
    assert get_radon_description("a") == get_radon_description("A")
    assert get_radon_description("?") == "Complexity grade: ?"
