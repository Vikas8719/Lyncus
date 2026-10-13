"""
tests/test_parser.py — parser.py ke liye targeted tests.

Ye bugs pakad lete hain jo pehle miss ho gaye the:
 - radon multi-file attribution (Fix #5)
 - mypy note lines skip hona
 - HTML reporter XSS escape (Fix #1)
 - ruff multi-file parsing
"""

from __future__ import annotations

import json
import string

from hypothesis import given
from hypothesis import strategies as st

from Lyncus.core.parser import (
    _parse_cargo_machete,
    _parse_dotnet_format,
    _parse_generic,
    _parse_go_vet,
    _parse_gosec,
    _parse_mutmut,
    _parse_mypy,
    _parse_radon,
    _parse_ruff,
    _parse_staticcheck,
    _parse_vulture,
    parse_results,
)
from Lyncus.core.runner import ToolResult

# ── helpers ──────────────────────────────────────────────────────────────────


def _result(tool: str, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(
        tool_name=tool,
        language="python",
        success=True,
        stdout=stdout,
        stderr=stderr,
        return_code=0,
    )


class TestParseMutmut:
    def test_summarizes_mutation_stats(self):
        stats = {
            "killed": 6,
            "survived": 2,
            "suspicious": 1,
            "timeout": 1,
            "no_tests": 3,
            "skipped": 4,
            "total": 17,
        }

        problems = _parse_mutmut(_result("mutmut", json.dumps(stats)))

        assert len(problems) == 1
        assert problems[0].rule_id == "MUTATION-SCORE"
        assert "53.8%" in problems[0].message
        assert "3 without tests" in problems[0].message

    def test_mutmut_stats_are_registered_for_scan_results(self):
        problems = parse_results([_result("mutmut", json.dumps({"killed": 1, "survived": 1}))])

        assert len(problems) == 1
        assert problems[0].tool == "mutmut"

    def test_invalid_mutmut_json_is_reported(self):
        problems = _parse_mutmut(_result("mutmut", "not json"))

        assert len(problems) == 1
        assert problems[0].rule_id == "MUTMUT-RUN-FAILED"


# ── ruff ─────────────────────────────────────────────────────────────────────


class TestParseRuff:
    def test_single_finding(self):
        out = "src/main.py:10:5: E501 line too long (120 > 88 characters)\n"
        probs = _parse_ruff(_result("ruff", out))
        assert len(probs) == 1
        assert probs[0].file == "src/main.py"
        assert probs[0].line == 10
        assert probs[0].column == 5
        assert "E501" in probs[0].rule_id

    def test_multi_file_correct_attribution(self):
        """✅ Ruff multi-file — har finding apni file se jaaye."""
        out = "a.py:1:1: E501 line too long\nb.py:5:2: F401 unused import\n"
        probs = _parse_ruff(_result("ruff", out))
        assert len(probs) == 2
        files = [p.file for p in probs]
        assert "a.py" in files
        assert "b.py" in files
        assert probs[0].file == "a.py"
        assert probs[1].file == "b.py"

    def test_empty_output_no_crash(self):
        probs = _parse_ruff(_result("ruff", ""))
        assert probs == []


# ── mypy ─────────────────────────────────────────────────────────────────────


class TestParseMypy:
    def test_error_line_parsed(self):
        out = "mymodule.py:12: error: Incompatible types [assignment]\n"
        probs = _parse_mypy(_result("mypy", out))
        assert len(probs) == 1
        assert probs[0].file == "mymodule.py"
        assert probs[0].line == 12
        assert probs[0].severity == "critical"

    def test_note_lines_skipped(self):
        """✅ 'note:' lines problem nahi banni chahiye."""
        out = (
            "mymodule.py:12: error: Incompatible types [assignment]\n"
            "mymodule.py:12: note: Expected type 'int', got 'str'\n"
        )
        probs = _parse_mypy(_result("mypy", out))
        assert len(probs) == 1, "note: line bhi problem ban gaya!"

    def test_warning_severity(self):
        out = "mymodule.py:5: warning: Unused variable [var]\n"
        probs = _parse_mypy(_result("mypy", out))
        if probs:
            assert probs[0].severity == "warning"

    @given(
        filename=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=12),
        line=st.integers(min_value=1, max_value=100_000),
        message=st.text(alphabet=string.ascii_letters, min_size=1, max_size=80),
        code=st.sampled_from(["assignment", "arg-type", "return-value"]),
    )
    def test_valid_error_line_preserves_fields(self, filename, line, message, code):
        output = f"{filename}.py:{line}: error: {message} [{code}]\n"

        problems = _parse_mypy(_result("mypy", output))

        assert len(problems) == 1
        assert problems[0].file == f"{filename}.py"
        assert problems[0].line == line
        assert problems[0].message == message
        assert problems[0].rule_id == code
        assert problems[0].severity == "critical"

    @given(
        filename=st.text(alphabet=string.ascii_letters + "_-", min_size=1, max_size=24),
        line=st.integers(min_value=1, max_value=1_000_000),
        message=st.text(alphabet=string.ascii_letters + " .,!?-", min_size=1, max_size=100)
        .map(str.strip)
        .filter(bool),
        level=st.sampled_from(["error", "warning"]),
        code=st.one_of(st.none(), st.sampled_from(["assignment", "arg-type", "return-value"])),
    )
    def test_generated_diagnostics_preserve_severity_and_optional_code(
        self, filename, line, message, level, code
    ):
        code_suffix = f" [{code}]" if code else ""
        output = f"src/{filename}.py:{line}: {level}: {message}{code_suffix}\n"

        problems = _parse_mypy(_result("mypy", output))

        assert len(problems) == 1
        assert problems[0].file == f"src/{filename}.py"
        assert problems[0].line == line
        assert problems[0].message == message
        assert problems[0].rule_id == (code or "MYPY")
        assert problems[0].severity == ("critical" if level == "error" else "warning")

    @given(raw_output=st.text(max_size=2_000))
    def test_arbitrary_output_never_crashes_or_emits_invalid_locations(self, raw_output):
        problems = _parse_mypy(_result("mypy", raw_output))

        assert all(problem.line > 0 for problem in problems)
        assert all(problem.severity in {"critical", "warning"} for problem in problems)

    @given(
        filename=st.text(alphabet=string.ascii_letters, min_size=1, max_size=16),
        line=st.integers(min_value=1, max_value=100_000),
        message=st.text(alphabet=string.ascii_letters + " ", min_size=1, max_size=60)
        .map(str.strip)
        .filter(bool),
    )
    def test_adding_note_diagnostic_does_not_change_findings(self, filename, line, message):
        error = f"{filename}.py:{line}: error: {message} [assignment]"
        note = f"{filename}.py:{line}: note: extra context"

        without_note = _parse_mypy(_result("mypy", error))
        with_note = _parse_mypy(_result("mypy", f"{error}\n{note}"))

        assert with_note == without_note


# ── radon ────────────────────────────────────────────────────────────────────


class TestParseRadon:
    RADON_OUTPUT = """\
utils.py
    C 5:0 helper_func - C (12)
    D 20:4 another_func - D (20)
models.py
    F 1:0 mega_function - F (55)
"""

    def test_multi_file_correct_attribution(self):
        """✅ Fix #5: Radon multi-file — sab findings apni sahi file mein jaayein."""
        probs = _parse_radon(_result("radon", self.RADON_OUTPUT))
        assert len(probs) == 3, f"3 findings chahiye, mila {len(probs)}"

        utils_probs = [p for p in probs if p.file == "utils.py"]
        models_probs = [p for p in probs if p.file == "models.py"]

        assert len(utils_probs) == 2, (
            f"utils.py mein 2 findings chahiye, mili {len(utils_probs)}. "
            f"Bug: sab aakhri file mein ja rahe hain?"
        )
        assert len(models_probs) == 1, f"models.py mein 1 finding chahiye, mili {len(models_probs)}"

    def test_only_bad_grades_reported(self):
        """Grade A aur B report nahi hone chahiye."""
        out = "clean.py\n    A 1:0 simple_fn - A (2)\n    B 5:0 ok_fn - B (6)\n"
        probs = _parse_radon(_result("radon", out))
        assert probs == [], f"Grade A/B report nahi hone chahiye, mila: {probs}"

    def test_correct_line_numbers(self):
        probs = _parse_radon(_result("radon", self.RADON_OUTPUT))
        lines = {p.file: p.line for p in probs}
        assert lines.get("models.py") == 1

    def test_empty_output_no_crash(self):
        probs = _parse_radon(_result("radon", ""))
        assert probs == []


# ── vulture ──────────────────────────────────────────────────────────────────


class TestParseVulture:
    def test_unused_function_detected(self):
        out = "mymodule.py:45: unused function 'old_helper' (60%)\n"
        probs = _parse_vulture(_result("vulture", out))
        assert len(probs) == 1
        assert probs[0].file == "mymodule.py"
        assert probs[0].line == 45
        assert probs[0].category == "DEAD-CODE"


class TestAdditionalParsers:
    def test_go_parsers_support_json_and_text_formats(self):
        staticcheck = _parse_staticcheck(
            _result(
                "staticcheck",
                '{"code":"ST1001","location":{"file":"main.go","line":2,"column":3},'
                '"message":"style issue"}\n'
                "other.go:4:5: another style issue (ST1001)\n",
            )
        )
        gosec = _parse_gosec(
            _result(
                "gosec",
                '{"Issues":[{"rule_id":"G101","severity":"HIGH","file":"main.go",'
                '"line":"12","column":"4","details":"hardcoded credentials"}]}',
            )
        )
        go_vet = _parse_go_vet(
            _result(
                "go-vet",
                stderr="main.go:8:2: printf format %d has arg of wrong type\n",
            )
        )

        assert [(problem.file, problem.line) for problem in staticcheck] == [
            ("main.go", 2),
            ("other.go", 4),
        ]
        assert gosec[0].severity == "critical"
        assert gosec[0].message == "hardcoded credentials"
        assert go_vet[0].file == "main.go"
        assert go_vet[0].column == 2

    def test_text_parsers_filter_and_map_findings(self):
        machete = _parse_cargo_machete(
            _result("cargo-machete", '    "unused_crate" -- Cargo.toml\n')
        )
        dotnet_format = _parse_dotnet_format(
            _result("dotnet-format", stdout="src/Program.cs formatted.\n")
        )
        generic = _parse_generic(
            _result(
                "custom-tool",
                stdout=(
                    "src/main.py:7:3: issue found\n"
                    "vendor/lib.py:8: issue ignored\n"
                    "src/main.py:9: note: supporting detail\n"
                ),
            )
        )

        assert len(machete) == 1
        assert "unused_crate" in machete[0].message
        assert dotnet_format[0].file == "src/Program.cs"
        assert [(problem.file, problem.line, problem.column) for problem in generic] == [
            ("src/main.py", 7, 3),
        ]

    def test_dispatch_skips_empty_results_and_uses_generic_fallback(self):
        results = [
            _result("ruff"),
            ToolResult(
                tool_name="ruff",
                language="python",
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                skipped=True,
            ),
            _result("custom-tool", stdout="src/main.py:7: issue found\n"),
        ]

        problems = parse_results(results)

        assert len(problems) == 1
        assert problems[0].tool == "custom-tool"
        assert problems[0].line == 7


# ── html_reporter XSS ────────────────────────────────────────────────────────
class TestHtmlReporterXSS:
    """✅ Fix #1: XSS — user data HTML mein escape hona chahiye."""

    def _make_html(self, **kwargs):
        import os
        import tempfile
        from pathlib import Path

        from Lyncus.core.html_reporter import export_html_report
        from Lyncus.core.parser import Problem

        p = Problem(
            tool=kwargs.get("tool", "ruff"),
            rule_id="E001",
            category=kwargs.get("category", "QUALITY"),
            severity="warning",
            file=kwargs.get("file", "test.py"),
            line=1,
            column=0,
            message=kwargs.get("message", "test message"),
            suggestion=kwargs.get("suggestion", ""),
        )
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            tmp = f.name
        try:
            export_html_report([p], str(Path(tmp).parent / "proj"), "python", ["ruff"], 1.0, tmp)
            return open(tmp, encoding="utf-8").read()
        finally:
            os.unlink(tmp)

    def test_xss_in_message_escaped(self):
        """Script tag message mein escape hona chahiye."""
        html = self._make_html(message="<script>alert('xss')</script>")
        assert "<script>alert" not in html, "XSS in message nahi escape hua!"
        assert "&lt;script&gt;" in html or "alert" not in html

    def test_xss_in_file_path_escaped(self):
        """Malicious file path JS string mein inject nahi hona chahiye."""
        evil_path = "x');alert(document.cookie);//.py"
        html = self._make_html(file=evil_path)
        # Raw single-quote + close paren JS injection nahi honi chahiye
        assert "');alert(document.cookie)" not in html, (
            "File path JS string mein inject ho raha hai — XSS!"
        )

    def test_xss_in_suggestion_escaped(self):
        """Suggestion field bhi escape hona chahiye."""
        html = self._make_html(suggestion="<img src=x onerror=alert(1)>")
        assert "<img src=x" not in html, "XSS in suggestion nahi escape hua!"

    def test_xss_in_category_escaped(self):
        """Category data attribute mein inject nahi hona chahiye."""
        html = self._make_html(category='"><script>alert(1)</script>')
        assert "<script>alert(1)</script>" not in html, "XSS in category!"
