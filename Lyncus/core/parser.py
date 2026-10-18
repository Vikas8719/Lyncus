"""
Output Parser — Sab tools ka raw output parse karke
unified Problem format mein convert karta hai.
Phase 3: C++, C#, Java, Ruby, PHP, Go, Rust, Kotlin, Swift, Dart parsers added.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Named constants — magic numbers nahi
_VULTURE_DEFAULT_CONFIDENCE = 70  # Default confidence threshold for vulture
_MAX_MESSAGE_DISPLAY_LEN = 80     # Truncation length for displayed messages

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from Lyncus.core.runner import ToolResult


@dataclass
class Problem:
    tool: str
    rule_id: str
    category: str  # HARDCODE / FAKE-TEST / DEAD-CODE / SECURITY / TYPE / QUALITY ...
    severity: str  # critical / warning / info
    file: str
    line: int
    column: int
    message: str
    suggestion: str = ""


def parse_results(results: list[ToolResult]) -> list[Problem]:
    """Sab ToolResult ko parse karke unified Problem list banao."""
    problems: list[Problem] = []
    try:
        for result in results:
            if result.skipped or (
                not result.stdout and not result.stderr and result.temporary_directory is None
            ):
                continue
            parser = PARSERS.get(result.tool_name)
            if result.tool_name.endswith("-tests") or result.tool_name == "ctest":
                parser = _parse_test_runner
            if parser:
                problems.extend(parser(result))
            else:
                problems.extend(_parse_generic(result))
    finally:
        for result in results:
            if result.temporary_directory:
                result.temporary_directory.cleanup()
    return problems


# PYTHON PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_ruff(result: ToolResult) -> list[Problem]:
    problems = []
    for raw_line in result.stdout.splitlines():
        fields = raw_line.rsplit(":", 3)
        if len(fields) != 4:
            continue
        file, line, col, finding = fields
        code, separator, msg = finding.strip().partition(" ")
        if not separator or not line.isdigit() or not col.isdigit():
            continue
        code_prefix = code.rstrip("0123456789")
        code_suffix = code[len(code_prefix) :]
        if not code_prefix.isalpha() or not code_prefix.isupper() or not code_suffix.isdigit():
            continue
        from Lyncus.languages.python_checks import get_ruff_category, get_ruff_severity

        problems.append(
            Problem(
                tool="ruff",
                rule_id=code,
                category=get_ruff_category(code),
                severity=get_ruff_severity(code),
                file=file.strip(),
                line=int(line),
                column=int(col),
                message=msg.strip(),
            )
        )
    return problems


def _parse_mypy(result: ToolResult) -> list[Problem]:
    return [
        problem
        for raw_line in result.stdout.splitlines()
        if (problem := _parse_mypy_line(raw_line)) is not None
    ]


def _parse_mypy_line(raw_line: str) -> Problem | None:
    location, separator, finding = raw_line.partition(": ")
    if not separator:
        return None
    file, separator, line = location.rpartition(":")
    if not separator or not line.isdigit():
        return None
    level, separator, msg = finding.partition(": ")
    if not separator or level not in ("error", "warning", "note") or level == "note":
        return None
    code = None
    if msg.endswith("]") and " [" in msg:
        msg, _, code = msg.rpartition(" [")
        code = code[:-1]
    from Lyncus.languages.python_checks import get_mypy_category

    return Problem(
        tool="mypy",
        rule_id=code or "MYPY",
        category=get_mypy_category(code or ""),
        severity="critical" if level == "error" else "warning",
        file=file.strip(),
        line=int(line),
        column=0,
        message=msg.strip(),
    )


def _parse_bandit(result: ToolResult) -> list[Problem]:
    problems = []
    from Lyncus.languages.python_checks import BANDIT_SEVERITY_MAP, get_bandit_description

    issue_blocks = re.split(r"(?m)^>>\s+Issue:\s*", result.stdout)
    for block in issue_blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue
        header = re.match(r"\[([^\]]+)\]\s+([^\r\n]+)", lines[0])
        severity_line = next((line for line in lines if "Severity:" in line), None)
        location_line = next((line for line in lines if "Location:" in line), None)
        if not header or not severity_line or not location_line:
            continue
        severity_match = re.search(r"Severity:\s*(\w+)", severity_line)
        location_match = re.search(r"Location:\s*(.+)", location_line)
        if not severity_match or not location_match:
            continue
        location_parts = location_match.group(1).rsplit(":", 1)
        if len(location_parts) != 2 or not location_parts[1].isdigit():
            continue
        rule, msg = header.groups()
        severity = severity_match.group(1)
        file, line = location_parts
        rule_id = rule.split(":")[0].strip()
        normalized_file = file.strip().replace("\\", "/").lower()
        file_name = normalized_file.rsplit("/", 1)[-1]
        path_parts = set(normalized_file.split("/"))
        is_test_file = (
            bool(path_parts & {"test", "tests"})
            or file_name.startswith("test_")
            or file_name.endswith("_test.py")
        )
        # pytest assert statements are expected in tests; Bandit B101 is useful
        # for production code, but creates one noisy INFO per test assertion.
        if rule_id == "B101" and is_test_file:
            continue
        problems.append(
            Problem(
                tool="bandit",
                rule_id=rule_id,
                category="SECURITY",
                severity=BANDIT_SEVERITY_MAP.get(severity.upper(), "warning"),
                file=file.strip(),
                line=int(line),
                column=0,
                message=f"{msg.strip()} — {get_bandit_description(rule_id)}",
            )
        )
    return problems


def _parse_vulture(result: ToolResult) -> list[Problem]:
    problems = []
    from Lyncus.languages.python_checks import get_vulture_severity

    for raw_line in result.stdout.splitlines():
        location, separator, msg = raw_line.rpartition(": ")
        if not separator:
            continue
        file, separator, line = location.rpartition(":")
        if not separator or not line.isdigit() or not msg.startswith("unused "):
            continue
        confidence = None
        if msg.endswith("%)") and " (" in msg:
            msg, _, confidence = msg.rpartition(" (")
            confidence = confidence[:-2]
            if not confidence.isdigit():
                continue
        conf = int(confidence or _VULTURE_DEFAULT_CONFIDENCE)
        problems.append(
            Problem(
                tool="vulture",
                rule_id="DEAD-CODE",
                category="DEAD-CODE",
                severity=get_vulture_severity(conf),
                file=file.strip(),
                line=int(line),
                column=0,
                message=msg.strip(),
            )
        )
    return problems


def _parse_radon(result: ToolResult) -> list[Problem]:
    """radon cc output parse karo.

    ✅ Fix #5: Line-by-line iterate karo — current_file header pe update ho,
    findings us file se associate hon. Pehle wala code sirf last file track karta tha.

    radon cc output format:
        path/to/file.py
            A  5:0 my_function - A (2)
            C  20:0 complex_func - C (15)
        another_file.py
            B  1:0 some_func - B (8)
    """
    # Directories jinka output skip karna hai — venv, site-packages, etc.
    # Forward slash aur backslash dono handle karo (Windows + Linux)
    _RADON_SKIP_SEGMENTS = {
        "site-packages", "dist-packages",
        "venv", ".venv", "venv-win", "venv-linux", "venv-mac",
        "env", "node_modules", ".git", "build", "dist",
        "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    }

    def _is_third_party(filepath: str) -> bool:
        """Path ke segments check karo — koi bhi skip segment ho toh True."""
        normalized = filepath.replace("\\", "/")
        parts = set(normalized.split("/"))
        return bool(parts & _RADON_SKIP_SEGMENTS)

    problems = []
    current_file = ""
    skip_current = False
    for raw_line in result.stdout.splitlines():
        if raw_line and not raw_line[0].isspace() and raw_line.rstrip().endswith(".py"):
            current_file = raw_line.strip()
            skip_current = _is_third_party(current_file)
            continue

        if skip_current:
            continue

        problem = _parse_radon_finding(raw_line.strip(), current_file)
        if problem:
            problems.append(problem)
    return problems


def _parse_radon_finding(finding: str, file: str) -> Problem | None:
    if not file or len(finding) < 2 or finding[0] not in "ABCDEF":
        return None
    level_and_position = finding[1:].split(None, 1)
    if len(level_and_position) != 2:
        return None
    position, description = level_and_position
    if ":" not in position:
        return None
    line, col = position.split(":", 1)
    name, separator, ranking = description.partition(" - ")
    if not separator:
        return None
    grade, separator, score = ranking.partition(" (")
    if (
        not separator
        or not score.endswith(")")
        or grade not in ("C", "D", "E", "F")
        or not line.isdigit()
        or not col.isdigit()
        or not score[:-1].isdigit()
    ):
        return None
    from Lyncus.languages.python_checks import get_radon_description, get_radon_severity

    return Problem(
        tool="radon",
        rule_id=f"CC-{grade}",
        category="COMPLEXITY",
        severity=get_radon_severity(grade),
        file=file,
        line=int(line),
        column=int(col),
        message=f"'{name}' complexity {grade} (score:{score[:-1]}) — {get_radon_description(grade)}",
    )


def _parse_pytest_cov(result: ToolResult) -> list[Problem]:
    """
    pytest-cov + Hypothesis output parse karo.

    Dono types handle karta hai:
      1. Hypothesis falsifying examples — property test failures
      2. Coverage warnings — low branch coverage per file

    pytest -q output format:
      FAILED tests/test_foo.py::test_bar - hypothesis.errors.Unsatisfied...
      Falsifying example: test_bar(x=5, y=-1)
      ...
      TOTAL    120     18    85%
    """
    problems: list[Problem] = []
    output = result.stdout + "\n" + result.stderr

    # ── 1. Hypothesis Failures ─────────────────────────────────────────────
    # Pattern: "Falsifying example: <test_name>(<args>)"
    _HYPO_FALSIFY_RE = re.compile(
        r"Falsifying example: (\w+)\(([^)]*)\)", re.MULTILINE
    )
    # Pattern: "FAILED tests/test_foo.py::test_bar - <ErrorType>: <msg>"
    _PYTEST_FAILED_RE = re.compile(
        r"FAILED (.+?)::(\w+)\s+-\s+(.+)", re.MULTILINE
    )
    # Pattern: "hypothesis.errors.Flaky" ya "hypothesis.errors.Unsatisfied"
    _HYPO_ERROR_RE = re.compile(
        r"(hypothesis\.errors\.\w+|AssertionError): (.+)", re.MULTILINE
    )

    failed_tests: dict[str, tuple[str, str]] = {}  # test_name → (file, error_msg)
    for m in _PYTEST_FAILED_RE.finditer(output):
        file_path, test_name, error = m.groups()
        failed_tests[test_name] = (file_path.strip(), error.strip())

    for m in _HYPO_FALSIFY_RE.finditer(output):
        test_name, args = m.groups()
        file_path, error_msg = failed_tests.get(test_name, (".", ""))

        # Error context — try to get the actual assertion error
        hypo_err = _HYPO_ERROR_RE.search(output, m.start())
        detail = hypo_err.group(2)[:120] if hypo_err else error_msg[:120]

        problems.append(Problem(
            tool="pytest-cov",
            rule_id="HYPO-FALSIFY",
            category="PROPERTY",
            severity="critical",
            file=file_path,
            line=0,
            column=0,
            message=(
                f"Hypothesis falsifying example found: {test_name}({args}) — {detail}"
                if detail else
                f"Hypothesis found a failing example for {test_name}({args})"
            ),
            suggestion="Add @settings(max_examples=1000) or fix the property invariant",
        ))

    # ── 2. Hypothesis Flaky Tests ──────────────────────────────────────────
    _HYPO_FLAKY_RE = re.compile(
        r"hypothesis\.errors\.Flaky.*?in (\w+)", re.MULTILINE | re.DOTALL
    )
    for m in _HYPO_FLAKY_RE.finditer(output):
        test_name = m.group(1)
        file_path, _ = failed_tests.get(test_name, (".", ""))
        problems.append(Problem(
            tool="pytest-cov",
            rule_id="HYPO-FLAKY",
            category="PROPERTY",
            severity="warning",
            file=file_path,
            line=0,
            column=0,
            message=f"Hypothesis flaky test detected: {test_name} — result changes between runs",
            suggestion="Use @settings(deriving=...) or make state management deterministic",
        ))

    # ── 3. Coverage Warnings (low branch coverage) ────────────────────────
    # Format: "file.py     50     10    80%   12-15, 20"
    # Only warn on files where coverage < threshold (default 70%)
    _COV_LINE_RE = re.compile(
        r"^(\S+\.py)\s+\d+\s+\d+\s+(\d+)%", re.MULTILINE
    )
    _COV_THRESHOLD = 70

    for m in _COV_LINE_RE.finditer(output):
        file_path, cov_pct_str = m.groups()
        cov_pct = int(cov_pct_str)
        if cov_pct < _COV_THRESHOLD:
            severity = "critical" if cov_pct < 50 else "warning"
            problems.append(Problem(
                tool="pytest-cov",
                rule_id="COV-LOW",
                category="COVERAGE",
                severity=severity,
                file=file_path,
                line=0,
                column=0,
                message=f"Branch coverage {cov_pct}% < {_COV_THRESHOLD}% threshold",
                suggestion="Add tests for uncovered branches",
            ))

    # ── 4. General test failures (non-hypothesis) ─────────────────────────
    # Agar hypothesis failures already parse nahi hue toh generic failures
    if not problems and result.return_code not in (0, 5):  # 5 = no tests collected
        for m in _PYTEST_FAILED_RE.finditer(output):
            file_path, test_name, error = m.groups()
            if "hypothesis" in error.lower():
                continue  # Already handled above
            problems.append(Problem(
                tool="pytest-cov",
                rule_id="TEST-FAIL",
                category="TEST",
                severity="critical",
                file=file_path.strip(),
                line=0,
                column=0,
                message=f"Test failed: {test_name} — {error.strip()[:120]}",
            ))

    return problems


def _parse_rapidcheck(result: ToolResult) -> list[Problem]:
    """
    RapidCheck output parse karo — C++/CUDA property-based testing.

    RapidCheck output format (stdout):
      [LYNCUS] RapidCheck: 2 properties passed (1000 examples each)   ← success
      [LYNCUS] RapidCheck: identity test FAILED                        ← failure
      Falsifying example: ...                                           ← counterexample
      [LYNCUS] RapidCheck: link failed — rapidcheck library not found  ← install hint

    rc::check() output:
      Using configuration: seed=12345
      identity property: OK, passed 1000 tests
      commutative addition: FAILED, after 42 tests
          Counterexample: (a = 3, b = -1)
    """
    output = result.stdout + "\n" + result.stderr
    problems: list[Problem] = []

    # Link failure — rapidcheck library install nahi hai
    if "link failed" in output.lower() or "rapidcheck library not found" in output.lower():
        problems.append(Problem(
            tool=result.tool_name,
            rule_id="RC-NOT-LINKED",
            category="PROPERTY",
            severity="info",
            file=".",
            line=0,
            column=0,
            message="RapidCheck header found but library not linked — install rapidcheck library",
            suggestion=(
                "vcpkg install rapidcheck / apt-get install librapidcheck-dev / "
                "brew install rapidcheck"
            ),
        ))
        return problems

    # Runner not found — auto-create zaroor hai
    if "runner not found" in output.lower():
        return []  # Preview me handle hota hai, scan mein silent skip

    # Property failures — "FAILED" in rc::check output
    _RC_FAIL_RE = re.compile(
        r"([\w\s]+): FAILED,? after (\d+) tests?", re.IGNORECASE
    )
    _RC_COUNTEREX_RE = re.compile(
        r"(?:Counterexample|Falsifying example)[:\s]+(.+)", re.IGNORECASE
    )

    for m in _RC_FAIL_RE.finditer(output):
        prop_name = m.group(1).strip()
        tests_run = int(m.group(2))

        # Counterexample dhundo
        counterex = _RC_COUNTEREX_RE.search(output, m.end())
        counterex_str = counterex.group(1).strip()[:100] if counterex else "unknown"

        problems.append(Problem(
            tool=result.tool_name,
            rule_id="RC-PROPERTY-FAIL",
            category="PROPERTY",
            severity="critical",
            file=".",
            line=0,
            column=0,
            message=(
                f"RapidCheck: property '{prop_name}' failed after {tests_run} examples. "
                f"Counterexample: {counterex_str}"
            ),
            suggestion="Fix the property invariant or the production code it tests",
        ))

    # Lyncus [FAILED] markers
    _LYNCUS_FAIL_RE = re.compile(
        r"\[LYNCUS\] RapidCheck: (.+?) (?:test )?FAILED", re.IGNORECASE
    )
    for m in _LYNCUS_FAIL_RE.finditer(output):
        prop_name = m.group(1).strip()
        if not any(p.rule_id == "RC-PROPERTY-FAIL" and prop_name in p.message
                   for p in problems):
            problems.append(Problem(
                tool=result.tool_name,
                rule_id="RC-PROPERTY-FAIL",
                category="PROPERTY",
                severity="critical",
                file=".",
                line=0,
                column=0,
                message=f"RapidCheck: '{prop_name}' property failed",
                suggestion="Check the property invariant and fix the underlying bug",
            ))

    return problems


def _parse_pip_audit(result: ToolResult) -> list[Problem]:
    """pip-audit output parse karo."""
    problems = []
    try:
        data = json.loads(result.stdout)
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                problems.append(
                    Problem(
                        tool="pip-audit",
                        rule_id=vuln.get("id", "CVE"),
                        category="SECURITY",
                        severity="critical",
                        file="requirements.txt",
                        line=0,
                        column=0,
                        message=f"{dep.get('name')} {dep.get('version')}: {vuln.get('description', '')}",
                        suggestion=f"Fix version: {', '.join(vuln.get('fix_versions', []))}",
                    )
                )
    except (json.JSONDecodeError, KeyError):
        pass
    return problems


def _parse_mutmut(result: ToolResult) -> list[Problem]:
    """Summarize mutmut's exported CI statistics for the unified report."""
    try:
        stats = json.loads(result.stdout)
    except json.JSONDecodeError:
        detail = result.stderr.strip().splitlines()[-1:]
        message = detail[0] if detail else "Mutmut did not produce valid CI statistics"
        # "No module named" ya "no tests" type errors — informational, warning nahi
        stderr_lower = result.stderr.lower()
        is_env_issue = any(
            phrase in stderr_lower
            for phrase in ("no module named", "no tests", "no mutants", "not found")
        )
        severity = "info" if is_env_issue else "warning"
        return [
            Problem(
                tool="mutmut",
                rule_id="MUTMUT-RUN-FAILED",
                category="FAKE-TEST",
                severity=severity,
                file="mutants/mutmut-cicd-stats.json",
                line=0,
                column=0,
                message=message,
            )
        ]
    if not isinstance(stats, dict):
        return [
            Problem(
                tool="mutmut",
                rule_id="MUTMUT-RUN-FAILED",
                category="FAKE-TEST",
                severity="warning",
                file="mutants/mutmut-cicd-stats.json",
                line=0,
                column=0,
                message="Mutmut CI statistics must be a JSON object",
            )
        ]

    def count(name: str) -> int:
        value = stats.get(name, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    killed = count("killed")
    survived = count("survived")
    suspicious = count("suspicious")
    timed_out = count("timeout")
    skipped = count("skipped")
    tested = max(count("total") - skipped, 0)
    score = ((killed + timed_out) / tested * 100) if tested else 0.0
    problems = [
        Problem(
            tool="mutmut",
            rule_id="MUTATION-SCORE",
            category="FAKE-TEST",
            severity="info",
            file="mutants/mutmut-cicd-stats.json",
            line=0,
            column=0,
            message=(
                f"Mutation score: {score:.1f}% ({killed} killed, "
                f"{survived} survived, {suspicious} suspicious, "
                f"{timed_out} timed out; {count('no_tests')} without tests, "
                f"{skipped} skipped)"
            ),
        )
    ]
    if not result.success:
        problems.append(
            Problem(
                tool="mutmut",
                rule_id="MUTMUT-RUN-FAILED",
                category="FAKE-TEST",
                severity="warning",
                file="mutants/mutmut-cicd-stats.json",
                line=0,
                column=0,
                message="Mutmut reported a non-zero exit status",
            )
        )
    return problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JAVASCRIPT / TYPESCRIPT PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_eslint(result: ToolResult) -> list[Problem]:
    problems = []
    from Lyncus.languages.js_checks import get_eslint_category, get_eslint_severity

    try:
        data = json.loads(result.stdout)
        for file_result in data:
            file_path = file_result.get("filePath", "")
            for msg in file_result.get("messages", []):
                rule_id = msg.get("ruleId") or "ESLINT"
                problems.append(
                    Problem(
                        tool="eslint",
                        rule_id=rule_id,
                        category=get_eslint_category(rule_id),
                        severity=get_eslint_severity(msg.get("severity", 1)),
                        file=file_path,
                        line=msg.get("line", 0),
                        column=msg.get("column", 0),
                        message=msg.get("message", ""),
                    )
                )
    except (json.JSONDecodeError, KeyError):
        pass
    return problems


def _parse_tsc(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.js_checks import parse_tsc_output

    return [
        Problem(
            tool="tsc",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_tsc_output(result.stdout + result.stderr)
    ]


def _parse_ts_prune(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.js_checks import parse_ts_prune_output

    return [
        Problem(
            tool="ts-prune",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_ts_prune_output(result.stdout)
    ]


def _parse_npm_audit(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.js_checks import parse_npm_audit_json

    return [
        Problem(
            tool="npm-audit",
            rule_id=f"NPM-{i.get('cve', 'VULN')}",
            category="SECURITY",
            severity=i["severity"],
            file="package.json",
            line=0,
            column=0,
            message=i["description"],
            suggestion=f"Fix version: {i.get('fixed_in', 'N/A')}",
        )
        for i in parse_npm_audit_json(result.stdout)
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUST PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_clippy(result: ToolResult) -> list[Problem]:
    problems = []
    from Lyncus.languages.rust_checks import get_clippy_category, get_clippy_severity

    try:
        for line in (result.stdout + result.stderr).splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            reason = obj.get("reason", "")
            if reason != "compiler-message":
                continue
            msg = obj.get("message", {})
            level = msg.get("level", "warning")
            if level in ("note", "help", ""):
                continue
            spans = msg.get("spans", [])
            if not spans:
                continue
            span = spans[0]
            lint = msg.get("code", {}) or {}
            lint_name = lint.get("code", "") or ""
            problems.append(
                Problem(
                    tool="cargo-clippy",
                    rule_id=lint_name or "CLIPPY",
                    category=get_clippy_category(lint_name),
                    severity=get_clippy_severity(level),
                    file=span.get("file_name", ""),
                    line=span.get("line_start", 0),
                    column=span.get("column_start", 0),
                    message=msg.get("message", ""),
                )
            )
    except Exception:
        pass
    return problems


def _parse_cargo_audit(result: ToolResult) -> list[Problem]:
    problems = []
    from Lyncus.languages.rust_checks import get_audit_severity

    try:
        data = json.loads(result.stdout)
        for vuln in data.get("vulnerabilities", {}).get("list", []):
            advisory = vuln.get("advisory", {})
            pkg = vuln.get("package", {})
            cvss = advisory.get("cvss", None)
            sev_str = advisory.get("severity", "medium")
            problems.append(
                Problem(
                    tool="cargo-audit",
                    rule_id=advisory.get("id", "RUSTSEC"),
                    category="SECURITY",
                    severity=get_audit_severity(float(cvss) if cvss else None, sev_str),
                    file="Cargo.toml",
                    line=0,
                    column=0,
                    message=f"{pkg.get('name')} {pkg.get('version')}: {advisory.get('title', '')}",
                    suggestion=f"Patched in: {advisory.get('patched_versions', ['N/A'])}",
                )
            )
    except (KeyError, TypeError, ValueError):
        pass
    return problems


def _parse_cargo_machete(result: ToolResult) -> list[Problem]:
    problems = []
    for raw_line in (result.stdout + result.stderr).splitlines():
        dependency, separator, _ = raw_line.partition(" --")
        if not separator:
            continue
        dep = dependency.strip().strip('"')
        if not dep:
            continue
        problems.append(
            Problem(
                tool="cargo-machete",
                rule_id="UNUSED-DEP",
                category="DEAD-CODE",
                severity="warning",
                file="Cargo.toml",
                line=0,
                column=0,
                message=f"Unused dependency: '{dep}' — remove it from Cargo.toml",
            )
        )
    return problems


# GO PARSERS


def _parse_staticcheck(result: ToolResult) -> list[Problem]:
    problems = []
    # JSON format try karo pehle
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            problem = _parse_staticcheck_text(line)
        else:
            problem = _parse_staticcheck_json(obj)
        if problem:
            problems.append(problem)
    return problems


def _parse_staticcheck_json(obj: dict[str, Any]) -> Problem:
    from Lyncus.languages.go_checks import get_staticcheck_category, get_staticcheck_severity

    code = obj.get("code", "")
    position = obj.get("location", {})
    return Problem(
        tool="staticcheck",
        rule_id=code,
        category=get_staticcheck_category(code),
        severity=get_staticcheck_severity(code),
        file=position.get("file", ""),
        line=position.get("line", 0),
        column=position.get("column", 0),
        message=obj.get("message", ""),
    )


def _parse_staticcheck_text(line: str) -> Problem | None:
    location, separator, finding = line.rpartition(": ")
    if not separator:
        return None
    file_line, separator, coordinates = location.rpartition(":")
    message, separator, code = finding.rpartition(" (")
    if not separator or not code.endswith(")") or not code[:-1].isalnum():
        return None
    file, line_separator, line_number = file_line.rpartition(":")
    if not line_separator or not line_number.isdigit() or not coordinates.isdigit():
        return None
    from Lyncus.languages.go_checks import get_staticcheck_category, get_staticcheck_severity

    code = code[:-1]
    return Problem(
        tool="staticcheck",
        rule_id=code,
        category=get_staticcheck_category(code),
        severity=get_staticcheck_severity(code),
        file=file,
        line=int(line_number),
        column=int(coordinates),
        message=message,
    )


def _parse_gosec(result: ToolResult) -> list[Problem]:
    problems = []
    from Lyncus.languages.go_checks import get_gosec_info, get_gosec_severity

    try:
        data = json.loads(result.stdout)
        for issue in data.get("Issues", []) or []:
            rule_id = issue.get("rule_id", "G000")
            cat, desc = get_gosec_info(rule_id)
            problems.append(
                Problem(
                    tool="gosec",
                    rule_id=rule_id,
                    category=cat,
                    severity=get_gosec_severity(issue.get("severity", "MEDIUM")),
                    file=issue.get("file", ""),
                    line=int(issue.get("line", 0)),
                    column=int(issue.get("column", 0)),
                    message=issue.get("details", desc),
                )
            )
    except (KeyError, TypeError, ValueError):
        pass
    return problems


def _parse_golangci(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.go_checks import parse_golangci_json

    return [
        Problem(
            tool="golangci-lint",
            rule_id=f"GL-{i['linter'].upper()}",
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["text"],
        )
        for i in parse_golangci_json(result.stdout)
    ]


def _parse_go_vet(result: ToolResult) -> list[Problem]:
    problems = []
    for raw_line in result.stderr.splitlines():
        if raw_line.startswith("#"):
            continue
        file_line_col, separator, msg = raw_line.rpartition(": ")
        if not separator:
            continue
        file_line, separator, col = file_line_col.rpartition(":")
        if not separator or not col.isdigit():
            continue
        file, separator, line = file_line.rpartition(":")
        if not separator or not line.isdigit():
            continue
        problems.append(
            Problem(
                tool="go-vet",
                rule_id="GO-VET",
                category="BUGPRONE",
                severity="critical",
                file=file,
                line=int(line),
                column=int(col),
                message=msg.strip(),
            )
        )
    return problems


def _parse_cppcheck(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.cpp_checks import parse_cppcheck_xml

    raw = result.stderr
    if "<results" in raw or "<?xml" in raw:
        issues = parse_cppcheck_xml(raw)
    else:
        issues = _parse_cppcheck_text(raw)
    return [
        Problem(
            tool="cppcheck",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in issues
        if not _is_third_party_cpp(i["file"])
    ]


def _parse_cppcheck_text(output: str) -> list[dict[str, Any]]:
    severity_map = {
        "error": "critical",
        "warning": "warning",
        "style": "info",
        "performance": "info",
    }
    issues = []
    for raw_line in output.splitlines():
        location, separator, finding = raw_line.partition("]: ")
        if not separator or not location.startswith("["):
            continue
        file, separator, line = location[1:].rpartition(":")
        if not separator or not line.isdigit():
            continue
        severity, separator, message = finding.partition(") ")
        if not separator or not severity.startswith("("):
            continue
        issues.append(
            {
                "file": file.strip(),
                "line": int(line),
                "column": 0,
                "severity": severity_map.get(severity[1:].lower(), "info"),
                "rule_id": "CPPCHECK",
                "message": message.strip(),
                "category": "QUALITY",
            }
        )
    return issues


def _parse_clang_tidy(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.cpp_checks import parse_clang_tidy_output

    return [
        Problem(
            tool="clang-tidy",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_clang_tidy_output(result.stdout + result.stderr)
        if not _is_third_party_cpp(i["file"])
    ]


def _parse_flawfinder(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.cpp_checks import parse_flawfinder_output

    return [
        Problem(
            tool="flawfinder",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_flawfinder_output(result.stdout)
        if not _is_third_party_cpp(i["file"])
    ]


def _parse_lizard(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.cpp_checks import parse_lizard_output

    language = result.language  # cpp / cuda / python etc.

    return [
        Problem(
            tool="lizard",
            rule_id=i["rule_id"],
            category=i["category"],
            severity="info" if language in {"cpp", "cuda"} else i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_lizard_output(result.stdout)
        if not _is_third_party_cpp(i["file"])
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# C# PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_dotnet_build(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.csharp_checks import parse_dotnet_build_output

    return [
        Problem(
            tool="dotnet-build",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_dotnet_build_output(result.stdout + result.stderr)
    ]


def _parse_dotnet_format(result: ToolResult) -> list[Problem]:
    """dotnet format --verify-no-changes output parse karo."""
    problems = []
    for raw_line in (result.stdout + result.stderr).splitlines():
        file, separator, _ = raw_line.rpartition(" formatted.")
        if not separator:
            continue
        problems.append(
            Problem(
                tool="dotnet-format",
                rule_id="CS-FORMAT",
                category="STYLE",
                severity="info",
                file=file.strip(),
                line=0,
                column=0,
                message="Formatting required — run dotnet format",
            )
        )
    return problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JAVA PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_checkstyle(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.java_checks import parse_checkstyle_xml

    return [
        Problem(
            tool="checkstyle",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_checkstyle_xml(result.stdout + result.stderr)
    ]


def _parse_spotbugs(result: ToolResult) -> list[Problem]:
    """SpotBugs XML file se parse karo."""
    from pathlib import Path

    issues = []
    from Lyncus.languages.java_checks import parse_spotbugs_xml

    if result.temporary_directory:
        report_path = Path(result.temporary_directory.name) / "spotbugs_out.xml"
        if report_path.is_file() and not report_path.is_symlink():
            issues.extend(parse_spotbugs_xml(str(report_path)))
    return [
        Problem(
            tool="spotbugs",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in issues
    ]


def _parse_pmd(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.java_checks import parse_pmd_xml

    return [
        Problem(
            tool="pmd",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_pmd_xml(result.stdout)
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUBY PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_rubocop(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.ruby_checks import parse_rubocop_json

    return [
        Problem(
            tool="rubocop",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_rubocop_json(result.stdout)
    ]


def _parse_brakeman(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.ruby_checks import parse_brakeman_json

    return [
        Problem(
            tool="brakeman",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_brakeman_json(result.stdout)
    ]


def _parse_debride(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.ruby_checks import parse_debride_output

    return [
        Problem(
            tool="debride",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_debride_output(result.stdout)
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHP PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_phpcs(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.php_checks import parse_phpcs_json

    return [
        Problem(
            tool="phpcs",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_phpcs_json(result.stdout)
    ]


def _parse_phpstan(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.php_checks import parse_phpstan_json

    return [
        Problem(
            tool="phpstan",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_phpstan_json(result.stdout)
    ]


def _parse_psalm(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.php_checks import parse_psalm_json

    return [
        Problem(
            tool="psalm",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_psalm_json(result.stdout)
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KOTLIN / SWIFT / DART PARSERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_detekt(result: ToolResult) -> list[Problem]:
    from pathlib import Path

    from Lyncus.languages.kotlin_checks import parse_detekt_xml

    issues = []
    if result.temporary_directory:
        report_path = Path(result.temporary_directory.name) / "detekt_report.xml"
        if report_path.is_file() and not report_path.is_symlink():
            issues.extend(parse_detekt_xml(str(report_path)))
    return [
        Problem(
            tool="detekt",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in issues
    ]


def _parse_ktlint(result: ToolResult) -> list[Problem]:
    from pathlib import Path

    from Lyncus.languages.kotlin_checks import parse_ktlint_json

    raw = result.stdout
    if result.temporary_directory:
        report_path = Path(result.temporary_directory.name) / "ktlint_report.json"
        if report_path.is_file() and not report_path.is_symlink():
            raw = report_path.read_text(encoding="utf-8")
    return [
        Problem(
            tool="ktlint",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_ktlint_json(raw)
    ]


def _parse_swiftlint(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.swift_checks import parse_swiftlint_json

    return [
        Problem(
            tool="swiftlint",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_swiftlint_json(result.stdout)
    ]


def _parse_dart_analyze(result: ToolResult) -> list[Problem]:
    from Lyncus.languages.dart_checks import parse_dart_analyze_output

    return [
        Problem(
            tool="dart-analyze",
            rule_id=i["rule_id"],
            category=i["category"],
            severity=i["severity"],
            file=i["file"],
            line=i["line"],
            column=i["column"],
            message=i["message"],
        )
        for i in parse_dart_analyze_output(result.stdout + result.stderr)
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SANITIZER PARSERS — ASan / UBSan / CSan / Compute-Sanitizer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ASan error patterns — compile errors aur runtime errors dono
_ASAN_RUNTIME_RE = re.compile(
    r"=+\d+=+ERROR: AddressSanitizer: (\S+) on .*?address.*?$", re.MULTILINE
)
_ASAN_LOCATION_RE = re.compile(r"#\d+ 0x[0-9a-f]+ in \S+ (.+):(\d+)")
_ASAN_COMPILE_RE = re.compile(r"(.+):(\d+):(\d+): (error|note|warning): (.+)", re.MULTILINE)

# UBSan patterns
_UBSAN_RE = re.compile(r"(.+):(\d+):(\d+): runtime error: (.+)")

# Compute-Sanitizer (NVIDIA) patterns
_COMPUTE_SAN_RE = re.compile(
    r"========= (?:CUDA-MEMCHECK|compute-sanitizer).*?"
    r"========= (.+?) at 0x[0-9a-f]+ in (.+?)(?:\[(\d+)\])?$",
    re.MULTILINE | re.DOTALL,
)
_COMPUTE_ERROR_RE = re.compile(r"========= (.+)")


def _parse_sanitizer_compile_errors(
    output: str, tool: str, language: str
) -> list[Problem]:
    """Compile-time errors (clang++ failed) parse karo."""
    problems = []
    for m in _ASAN_COMPILE_RE.finditer(output):
        file, line, col, level, msg = m.groups()
        # Skip system headers aur notes
        if file.startswith("/usr/") or file.startswith("/Library/") or level == "note":
            continue
        problems.append(Problem(
            tool=tool,
            rule_id=f"{tool.upper()}-COMPILE",
            category="QUALITY",
            severity="critical" if level == "error" else "warning",
            file=file.strip(),
            line=int(line),
            column=int(col),
            message=f"[Compile] {msg.strip()}",
        ))
    return problems


def _parse_asan(result: ToolResult) -> list[Problem]:
    """
    AddressSanitizer output parse karo.
    Dono cases handle karte hain:
      1. Compile error — clang++ ne compile nahi kiya
      2. Runtime error — binary chala lekin ASan ne error pakda
    """
    output = result.stdout + "\n" + result.stderr
    tool = result.tool_name  # asan-cpp / asan-cuda / asan-rust

    # Pehle compile errors check karo
    compile_problems = _parse_sanitizer_compile_errors(output, tool, result.language)
    if compile_problems:
        return compile_problems

    problems = []

    # Runtime errors — "ERROR: AddressSanitizer: heap-buffer-overflow" etc.
    for m in _ASAN_RUNTIME_RE.finditer(output):
        error_type = m.group(1)  # heap-buffer-overflow / use-after-free / stack-overflow etc.

        # Uske baad pehla non-system stack frame location dhundo
        location_match = _ASAN_LOCATION_RE.search(output, m.end())
        file, line, col = "unknown", 0, 0
        if location_match:
            raw_file = location_match.group(1).strip()
            if not raw_file.startswith("/usr/") and not raw_file.startswith("/Library/"):
                file = raw_file
                line = int(location_match.group(2))

        severity = "critical" if error_type in {
            "heap-buffer-overflow", "stack-buffer-overflow",
            "heap-use-after-free", "use-after-poison",
            "global-buffer-overflow", "stack-use-after-scope",
        } else "warning"

        problems.append(Problem(
            tool=tool,
            rule_id=f"ASAN-{error_type.upper().replace('-', '_')}",
            category="SECURITY",
            severity=severity,
            file=file,
            line=line,
            column=col,
            message=f"AddressSanitizer: {error_type.replace('-', ' ')} detected",
        ))

    # Leak sanitizer output (ASAN_OPTIONS=detect_leaks=1)
    if "LeakSanitizer: detected memory leaks" in output:
        # Pehla non-system allocation location
        leak_loc = _ASAN_LOCATION_RE.search(output)
        file = leak_loc.group(1) if leak_loc else "unknown"
        line = int(leak_loc.group(2)) if leak_loc else 0
        problems.append(Problem(
            tool=tool,
            rule_id="ASAN-MEMORY_LEAK",
            category="SECURITY",
            severity="warning",
            file=file,
            line=line,
            column=0,
            message="AddressSanitizer: memory leak detected — LeakSanitizer report",
        ))

    return problems


def _parse_ubsan(result: ToolResult) -> list[Problem]:
    """
    UndefinedBehaviorSanitizer output parse karo.
    Format: file:line:col: runtime error: <description>
    """
    output = result.stdout + "\n" + result.stderr
    tool = result.tool_name  # ubsan-cpp / ubsan-cuda / ubsan-rust

    # Compile errors pehle
    compile_problems = _parse_sanitizer_compile_errors(output, tool, result.language)
    if compile_problems:
        return compile_problems

    problems = []
    seen: set[tuple[str, int, str]] = set()

    for m in _UBSAN_RE.finditer(output):
        file, line_str, col_str, msg = m.groups()
        # System headers skip
        if file.startswith("/usr/") or file.startswith("/Library/"):
            continue
        key = (file, int(line_str), msg)
        if key in seen:
            continue
        seen.add(key)

        # UB type se severity decide karo
        msg_lower = msg.lower()
        severity = "critical" if any(kw in msg_lower for kw in {
            "null pointer", "null dereference", "division by zero",
            "load of null", "store to null",
        }) else "warning"

        # Rule ID — UB type se banao
        rule_fragment = msg.split(":")[0].strip().upper().replace(" ", "_")[:30]

        problems.append(Problem(
            tool=tool,
            rule_id=f"UBSAN-{rule_fragment}",
            category="QUALITY",
            severity=severity,
            file=file.strip(),
            line=int(line_str),
            column=int(col_str),
            message=f"UndefinedBehavior: {msg.strip()}",
        ))

    return problems


def _parse_msan(result: ToolResult) -> list[Problem]:
    """
    MemorySanitizer output parse karo.
    MSan format: ==PID==WARNING: MemorySanitizer: use-of-uninitialized-value
                   #0 0x... in function_name file.cpp:line
    Yeh valgrind ka primary feature replace karta hai — uninitialized reads.
    """
    output = result.stdout + "\n" + result.stderr
    tool = result.tool_name  # msan-cpp / msan-cuda / msan-rust

    compile_problems = _parse_sanitizer_compile_errors(output, tool, result.language)
    if compile_problems:
        return compile_problems

    problems = []
    seen: set[tuple[str, int]] = set()

    # MSan runtime error pattern
    _MSAN_ERROR_RE = re.compile(
        r"==\d+==WARNING: MemorySanitizer: ([\w-]+)", re.MULTILINE
    )
    _MSAN_FRAME_RE = re.compile(
        r"#\d+ 0x[0-9a-f]+ in \S+ ([^:]+):(\d+)"
    )

    for m in _MSAN_ERROR_RE.finditer(output):
        error_type = m.group(1)  # use-of-uninitialized-value / etc.
        loc = _MSAN_FRAME_RE.search(output, m.end())
        file, line = "unknown", 0
        if loc:
            raw_file = loc.group(1).strip()
            if not raw_file.startswith("/usr/") and not raw_file.startswith("/Library/"):
                file = raw_file
                line = int(loc.group(2))
        key = (file, line)
        if key in seen:
            continue
        seen.add(key)
        problems.append(Problem(
            tool=tool,
            rule_id=f"MSAN-{error_type.upper().replace('-', '_')}",
            category="SECURITY",
            severity="critical",  # Uninitialized reads = always serious
            file=file,
            line=line,
            column=0,
            message=f"MemorySanitizer: {error_type.replace('-', ' ')} — valgrind-class bug detected",
        ))

    return problems


def _parse_tsan(result: ToolResult) -> list[Problem]:
    """
    ThreadSanitizer output parse karo.
    TSan format: WARNING: ThreadSanitizer: data race (pid=PID)
    """
    output = result.stdout + "\n" + result.stderr
    tool = result.tool_name  # tsan-cpp

    compile_problems = _parse_sanitizer_compile_errors(output, tool, result.language)
    if compile_problems:
        return compile_problems

    problems = []
    seen: set[tuple[str, int]] = set()

    _TSAN_ERROR_RE = re.compile(
        r"WARNING: ThreadSanitizer: ([\w\s-]+?) \(pid=\d+\)", re.MULTILINE
    )
    _TSAN_FRAME_RE = re.compile(
        r"#\d+ \S+ ([^:]+\.(?:cpp|cc|cxx|c|h|hpp)):(\d+)"
    )

    for m in _TSAN_ERROR_RE.finditer(output):
        error_type = m.group(1).strip()
        loc = _TSAN_FRAME_RE.search(output, m.end())
        file, line = "unknown", 0
        if loc:
            raw_file = loc.group(1).strip()
            if not raw_file.startswith("/usr/"):
                file = raw_file
                line = int(loc.group(2))
        key = (file, line)
        if key in seen:
            continue
        seen.add(key)
        rule_fragment = re.sub(r"[^A-Z0-9_]", "_", error_type.upper())[:30]
        problems.append(Problem(
            tool=tool,
            rule_id=f"TSAN-{rule_fragment}",
            category="SECURITY",
            severity="critical",  # Data races = always critical
            file=file,
            line=line,
            column=0,
            message=f"ThreadSanitizer: {error_type} detected",
        ))

    return problems


def _parse_compsan(result: ToolResult) -> list[Problem]:
    """
    Combined ASan+UBSan output parse karo.
    Dono parsers se problems collect karo — dedup karo same location pe.
    """
    # ASan aur UBSan dono parse karte hain combined output se
    asan_result = type(result)(  # ToolResult ki copy — tool_name change karke
        tool_name=f"asan-{result.language}",
        language=result.language,
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        return_code=result.return_code,
        skipped=result.skipped,
    )
    ubsan_result = type(result)(
        tool_name=f"ubsan-{result.language}",
        language=result.language,
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        return_code=result.return_code,
        skipped=result.skipped,
    )
    asan_problems = _parse_asan(asan_result)
    ubsan_problems = _parse_ubsan(ubsan_result)

    # Dedup by (file, line, rule_id)
    seen: set[tuple[str, int, str]] = set()
    combined: list[Problem] = []
    for p in asan_problems + ubsan_problems:
        key = (p.file, p.line, p.rule_id)
        if key not in seen:
            seen.add(key)
            p.tool = result.tool_name  # compsan-cpp / compsan-rust
            combined.append(p)
    return combined


def _parse_compute_sanitizer(result: ToolResult) -> list[Problem]:
    """
    NVIDIA Compute Sanitizer output parse karo.
    Tool: compute-sanitizer --tool memcheck
    Errors: GPU memory access violations, race conditions, OOB
    """
    output = result.stdout + "\n" + result.stderr
    problems = []
    seen: set[str] = set()

    # "========= ERROR 1" style blocks
    error_blocks = re.split(r"={8,}", output)
    for block in error_blocks:
        block = block.strip()
        if not block or block.startswith("Rerun with"):
            continue

        # Error type line
        error_lines = [line for line in block.splitlines() if line.strip() and not line.startswith("===")]
        if not error_lines:
            continue

        error_msg = error_lines[0].strip()
        if not error_msg or "passed" in error_msg.lower() or "process" in error_msg.lower():
            continue

        # File/line location — "at 0x... in funcname (file.cu:123)"
        loc_match = re.search(r"in \S+ \((.+?):(\d+)\)", block)
        file = loc_match.group(1).strip() if loc_match else "unknown.cu"
        line = int(loc_match.group(2)) if loc_match else 0

        # Severity
        msg_lower = error_msg.lower()
        severity = "critical" if any(kw in msg_lower for kw in {
            "out of bounds", "invalid", "illegal", "race condition",
            "uninitialized", "misaligned",
        }) else "warning"

        key = f"{file}:{line}:{error_msg[:40]}"
        if key in seen:
            continue
        seen.add(key)

        # Rule ID
        rule_fragment = re.sub(r"[^A-Z0-9_]", "_", error_msg.upper()[:30])

        problems.append(Problem(
            tool="compute-sanitizer",
            rule_id=f"CUDA-{rule_fragment}",
            category="SECURITY",
            severity=severity,
            file=file,
            line=line,
            column=0,
            message=f"Compute Sanitizer: {error_msg}",
        ))

    return problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GENERIC FALLBACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# C++ / generic third-party path filter
# build\vcpkg_installed, third_party, extern, vendor etc. skip karo
_CPP_SKIP_PATH_SEGMENTS = {
    "vcpkg_installed", "vcpkg", "third_party", "thirdparty",
    "extern", "external", "vendor", "deps", "dependencies",
    "site-packages", "dist-packages",
    "venv", ".venv", "venv-win", "venv-linux", "venv-mac",
    "node_modules", ".cache",
}


def _is_third_party_cpp(filepath: str) -> bool:
    """Path ke andar koi third-party/build segment ho toh True."""
    normalized = filepath.replace("\\", "/")
    # build/vcpkg_installed special case
    if "vcpkg_installed" in normalized:
        return True
    parts = set(normalized.split("/"))
    return bool(parts & _CPP_SKIP_PATH_SEGMENTS)


def _parse_generic(result: ToolResult) -> list[Problem]:
    """Generic fallback — file:line:col: message format."""
    problems = []
    output = result.stdout + "\n" + result.stderr
    skip_dirs = {
        "node_modules", "__pycache__", ".git", "target", "vendor",
        "vcpkg_installed", "build", "third_party", "extern", "external",
    }
    # pytest/test runner summary lines — false positives hain, skip karo
    _SKIP_PREFIXES = ("=", "-", "*", "PASSED", "FAILED", "ERROR", "collected", "passed", "failed")
    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped[0] in "=-*" or stripped.startswith(_SKIP_PREFIXES):
            continue
        fields = raw_line.rsplit(":", 3)
        if len(fields) == 4 and fields[1].isdigit() and fields[2].isdigit():
            file, line, col, msg = fields
        else:
            fields = raw_line.rsplit(":", 2)
            if len(fields) != 3 or not fields[1].isdigit():
                continue
            file, line, msg = fields
            col = None
        file = file.strip()
        if any(d in file for d in skip_dirs):
            continue
        if not file or "note:" in msg.lower():
            continue
        problems.append(
            Problem(
                tool=result.tool_name,
                rule_id=result.tool_name.upper(),
                category="QUALITY",
                severity="warning",
                file=file,
                line=int(line),
                column=int(col or 0),
                message=msg.strip(),
            )
        )
    return problems


def _parse_test_runner(result: ToolResult) -> list[Problem]:
    """Turn a project test command failure into one actionable finding."""
    if result.skipped or result.return_code == 0:
        return []
    output = (result.stderr or result.stdout).strip()
    message = next((line.strip() for line in output.splitlines() if line.strip()), "Tests failed")
    return [
        Problem(
            tool=result.tool_name,
            rule_id="TESTFAIL",
            category="TEST",
            severity="critical",
            file=".",
            line=0,
            column=0,
            message=message[:500],
        )
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PARSER REGISTRY — tool name → parser function
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARSERS: dict[str, Callable[[ToolResult], list[Problem]]] = {
    # Python
    "ruff": _parse_ruff,
    "mypy": _parse_mypy,
    "bandit": _parse_bandit,
    "vulture": _parse_vulture,
    "radon": _parse_radon,
    "pip-audit": _parse_pip_audit,
    "mutmut": _parse_mutmut,
    # pytest-cov + Hypothesis (1000 examples per test)
    "pytest-cov": _parse_pytest_cov,
    # JS / TS
    "eslint": _parse_eslint,
    "tsc": _parse_tsc,
    "ts-prune": _parse_ts_prune,
    "npm-audit": _parse_npm_audit,
    # Rust
    "cargo-clippy": _parse_clippy,
    "cargo-audit": _parse_cargo_audit,
    "cargo-machete": _parse_cargo_machete,
    # Go
    "staticcheck": _parse_staticcheck,
    "gosec": _parse_gosec,
    "golangci-lint": _parse_golangci,
    "go-vet": _parse_go_vet,
    # C++
    "cppcheck": _parse_cppcheck,
    "clang-tidy": _parse_clang_tidy,
    "clang-tidy-cuda": _parse_clang_tidy,
    "flawfinder": _parse_flawfinder,
    "lizard": _parse_lizard,
    # C#
    "dotnet-build": _parse_dotnet_build,
    "roslyn-analyzer": _parse_dotnet_build,
    "dotnet-format": _parse_dotnet_format,
    # Java
    "checkstyle": _parse_checkstyle,
    "spotbugs": _parse_spotbugs,
    "pmd": _parse_pmd,
    # Ruby
    "rubocop": _parse_rubocop,
    "brakeman": _parse_brakeman,
    "debride": _parse_debride,
    # PHP
    "phpcs": _parse_phpcs,
    "phpstan": _parse_phpstan,
    "psalm": _parse_psalm,
    # Kotlin
    "detekt": _parse_detekt,
    "ktlint": _parse_ktlint,
    # Swift
    "swiftlint": _parse_swiftlint,
    # Dart
    "dart-analyze": _parse_dart_analyze,
    "flutter-analyze": _parse_dart_analyze,
    # ── Sanitizers ────────────────────────────────────────────────────────────
    # C++ sanitizers — valgrind replaced by MSan+TSan
    "asan-cpp":         _parse_asan,
    "ubsan-cpp":        _parse_ubsan,
    "msan-cpp":         _parse_msan,   # Valgrind replacement — uninitialized reads
    "tsan-cpp":         _parse_tsan,   # Thread safety — data races
    "compsan-cpp":      _parse_compsan,  # Combined ASan+UBSan for C++
    # RapidCheck — C++/CUDA property-based testing (1000 examples)
    "rapidcheck":       _parse_rapidcheck,
    "rapidcheck-cuda":  _parse_rapidcheck,
    # CUDA sanitizers
    "asan-cuda":        _parse_asan,
    "ubsan-cuda":       _parse_ubsan,
    "msan-cuda":        _parse_msan,
    "compute-sanitizer":_parse_compute_sanitizer,
    # Rust sanitizers
    "asan-rust":        _parse_asan,
    "ubsan-rust":       _parse_ubsan,
    "msan-rust":        _parse_msan,
    "compsan-rust":     _parse_compsan,  # Combined ASan+UBSan for Rust
}
