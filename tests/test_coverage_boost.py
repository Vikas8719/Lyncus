"""
Coverage Boost Tests — 0% aur low-coverage modules ko 80%+ pe laana.
Covers: go_checks, rust_checks, js_checks, java_checks, kotlin_checks,
        swift_checks, dart_checks, languages/__init__.py, reporter.py, install_deps.py
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# languages/__init__.py  (8% → 90%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestLanguagesInit:
    def test_runner_resolves_module_roots_from_nested_source_files(self, tmp_path):
        from Lyncus.core.runner import resolve_project_root

        go_root = tmp_path / "go-project"
        go_source = go_root / "cmd" / "nested" / "main.go"
        go_source.parent.mkdir(parents=True)
        (go_root / "go.mod").write_text("module example\n")
        go_source.write_text("package main\n")

        rust_root = tmp_path / "rust-project"
        rust_source = rust_root / "src" / "nested" / "main.rs"
        rust_source.parent.mkdir(parents=True)
        (rust_root / "Cargo.toml").write_text('[package]\nname = "example"\n')
        rust_source.write_text("fn main() {}\n")

        go_result = resolve_project_root("go", str(go_source))
        rust_result = resolve_project_root("rust", str(rust_source))
        python_result = resolve_project_root("python", str(tmp_path))

        assert go_result == str(go_root), f"Go root should be {go_root}, got {go_result}"
        assert rust_result == str(rust_root), f"Rust root should be {rust_root}, got {rust_result}"
        assert python_result == str(tmp_path), f"Python root should be {tmp_path}, got {python_result}"

    def test_get_tools_python(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("python")
        assert len(tools) > 0, "Python tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "ruff" in names, "Python tools mein ruff hona chahiye"

    def test_get_tools_rust(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("rust")
        assert len(tools) > 0, "Rust tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "cargo-clippy" in names, "Rust tools mein cargo-clippy hona chahiye"

    def test_get_tools_go(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("go")
        assert len(tools) > 0, "Go tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "staticcheck" in names, "Go tools mein staticcheck hona chahiye"

    def test_get_tools_javascript(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("javascript")
        assert len(tools) > 0, "JavaScript tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "eslint" in names, "JavaScript tools mein eslint hona chahiye"

    def test_get_tools_typescript(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("typescript")
        # typescript_only tools bhi include honi chahiye
        names = [t.name for t in tools]
        assert "tsc" in names

    def test_get_tools_java(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("java")
        assert len(tools) > 0, "Java tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "checkstyle" in names, "Java tools mein checkstyle hona chahiye"

    def test_get_tools_kotlin(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("kotlin")
        assert len(tools) > 0, "Kotlin tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "detekt" in names, "Kotlin tools mein detekt hona chahiye"

    def test_get_tools_swift(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("swift")
        assert len(tools) > 0, "Swift tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "swiftlint" in names, "Swift tools mein swiftlint hona chahiye"

    def test_get_tools_dart(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("dart")
        assert len(tools) > 0, "Dart tools list empty nahi honi chahiye"
        names = [t.name for t in tools]
        assert "dart-analyze" in names, "Dart tools mein dart-analyze hona chahiye"

    def test_get_tools_unknown_returns_empty(self):
        from Lyncus.languages import get_tools_for_language

        tools = get_tools_for_language("brainfuck")
        assert tools == []

    def test_get_install_commands_python(self):
        from Lyncus.languages import get_install_commands_for_language

        cmds = get_install_commands_for_language("python")
        assert isinstance(cmds, dict)
        assert len(cmds) > 0

    def test_get_install_commands_unknown(self):
        from Lyncus.languages import get_install_commands_for_language

        cmds = get_install_commands_for_language("cobol")
        assert cmds == {}

    def test_get_install_commands_rust(self):
        from Lyncus.languages import get_install_commands_for_language

        cmds = get_install_commands_for_language("rust")
        assert "cargo-clippy" in cmds

    def test_get_install_commands_go(self):
        from Lyncus.languages import get_install_commands_for_language

        cmds = get_install_commands_for_language("go")
        assert "staticcheck" in cmds


# ══════════════════════════════════════════════════════════════════════════════
# go_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestGoChecks:
    def test_get_go_tools_all(self):
        from Lyncus.languages.go_checks import get_go_tools

        tools = get_go_tools()
        names = [t.name for t in tools]
        assert "go-vet" in names
        assert "staticcheck" in names
        assert "gosec" in names
        assert "golangci-lint" in names

    def test_get_go_tools_filter_security(self):
        from Lyncus.languages.go_checks import get_go_tools

        tools = get_go_tools(only="security")
        assert all(t.check_type == "security" for t in tools)
        names = [t.name for t in tools]
        assert "gosec" in names

    def test_get_go_tools_filter_quality(self):
        from Lyncus.languages.go_checks import get_go_tools

        tools = get_go_tools(only="quality")
        assert all(t.check_type == "quality" for t in tools)

    def test_get_go_tools_skip_slow(self):
        from Lyncus.languages.go_checks import get_go_tools

        tools = get_go_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "golangci-lint" not in names
        assert "go-test-coverage" not in names

    def test_get_staticcheck_category(self):
        from Lyncus.languages.go_checks import get_staticcheck_category

        assert get_staticcheck_category("SA1001") == "QUALITY"
        assert get_staticcheck_category("ST1001") == "STYLE"
        assert get_staticcheck_category("U1000") == "DEADCODE"
        assert get_staticcheck_category("QF1001") == "QUICKFIX"
        assert get_staticcheck_category("S1001") == "SIMPLIFY"
        assert get_staticcheck_category("UNKNOWN") == "QUALITY"  # default

    def test_get_staticcheck_severity(self):
        from Lyncus.languages.go_checks import get_staticcheck_severity

        assert get_staticcheck_severity("U1000") == "warning"
        assert get_staticcheck_severity("SA1001") == "critical"
        assert get_staticcheck_severity("SA2001") == "warning"
        assert get_staticcheck_severity("ST1001") == "info"

    def test_get_gosec_info_known(self):
        from Lyncus.languages.go_checks import get_gosec_info

        cat, desc = get_gosec_info("G101")
        assert cat == "SECURITY"
        assert "credentials" in desc.lower()

    def test_get_gosec_info_unknown(self):
        from Lyncus.languages.go_checks import get_gosec_info

        cat, desc = get_gosec_info("G999")
        assert cat == "SECURITY"
        assert "G999" in desc

    def test_get_gosec_severity(self):
        from Lyncus.languages.go_checks import get_gosec_severity

        assert get_gosec_severity("HIGH") == "critical"
        assert get_gosec_severity("MEDIUM") == "warning"
        assert get_gosec_severity("LOW") == "info"
        assert get_gosec_severity("unknown") == "warning"

    def test_parse_golangci_json_valid(self):
        from Lyncus.languages.go_checks import parse_golangci_json

        data = {
            "Issues": [
                {
                    "FromLinter": "gosec",
                    "Text": "SQL injection risk",
                    "Pos": {"Filename": "main.go", "Line": 42, "Column": 5},
                    "Severity": "error",
                }
            ]
        }
        issues = parse_golangci_json(json.dumps(data))
        assert len(issues) == 1
        assert issues[0]["file"] == "main.go"
        assert issues[0]["line"] == 42
        assert issues[0]["severity"] == "critical"
        assert issues[0]["category"] == "SECURITY"

    def test_parse_golangci_json_deadcode_linter(self):
        from Lyncus.languages.go_checks import parse_golangci_json

        data = {
            "Issues": [
                {
                    "FromLinter": "deadcode",
                    "Text": "unused function",
                    "Pos": {"Filename": "utils.go", "Line": 10, "Column": 1},
                    "Severity": "warning",
                }
            ]
        }
        issues = parse_golangci_json(json.dumps(data))
        assert issues[0]["category"] == "DEADCODE"

    def test_parse_golangci_json_empty(self):
        from Lyncus.languages.go_checks import parse_golangci_json

        issues = parse_golangci_json('{"Issues": []}')
        assert issues == []

    def test_parse_golangci_json_invalid(self):
        from Lyncus.languages.go_checks import parse_golangci_json

        issues = parse_golangci_json("not json at all")
        assert issues == []

    def test_parse_golangci_json_null_issues(self):
        from Lyncus.languages.go_checks import parse_golangci_json

        issues = parse_golangci_json('{"Issues": null}')
        assert issues == []

    def test_find_go_mod_direct(self):
        from Lyncus.languages.go_checks import find_go_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "go.mod").write_text("module example.com/myapp\ngo 1.22\n")
            result = find_go_mod(tmpdir)
            assert result == tmpdir

    def test_find_go_mod_parent(self):
        from Lyncus.languages.go_checks import find_go_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "go.mod").write_text("module example\ngo 1.22\n")
            sub = Path(tmpdir) / "cmd" / "main.go"
            sub.parent.mkdir()
            sub.write_text("package main")
            result = find_go_mod(str(sub))
            assert result == tmpdir

    def test_find_go_mod_recursive(self):
        from Lyncus.languages.go_checks import find_go_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subproject"
            subdir.mkdir()
            (subdir / "go.mod").write_text("module sub\ngo 1.22\n")
            result = find_go_mod(tmpdir)
            assert result is not None

    def test_find_go_mod_not_found(self):
        from Lyncus.languages.go_checks import find_go_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_go_mod(tmpdir)
            assert result is None

    def test_get_install_commands(self):
        from Lyncus.languages.go_checks import get_install_commands

        cmds = get_install_commands()
        assert "staticcheck" in cmds
        assert "gosec" in cmds

    def test_golangci_severity_default(self):
        from Lyncus.languages.go_checks import _golangci_severity

        assert _golangci_severity("") == "warning"
        assert _golangci_severity("error") == "critical"

    def test_golangci_category_quality(self):
        from Lyncus.languages.go_checks import _golangci_category

        assert _golangci_category("revive") == "QUALITY"
        assert _golangci_category("staticcheck") == "SECURITY"
        assert _golangci_category("unused") == "DEADCODE"


# ══════════════════════════════════════════════════════════════════════════════
# rust_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestRustChecks:
    def test_get_rust_tools_all(self):
        from Lyncus.languages.rust_checks import get_rust_tools

        tools = get_rust_tools()
        names = [t.name for t in tools]
        assert "cargo-clippy" in names
        assert "cargo-audit" in names
        assert "rustfmt" in names

    def test_get_rust_tools_filter_security(self):
        from Lyncus.languages.rust_checks import get_rust_tools

        tools = get_rust_tools(only="security")
        assert all(t.check_type == "security" for t in tools)

    def test_get_rust_tools_filter_quality(self):
        from Lyncus.languages.rust_checks import get_rust_tools

        tools = get_rust_tools(only="quality")
        assert all(t.check_type == "quality" for t in tools)
        names = [t.name for t in tools]
        assert "cargo-clippy" in names

    def test_get_rust_tools_skip_slow(self):
        from Lyncus.languages.rust_checks import get_rust_tools

        tools = get_rust_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "cargo-tarpaulin" not in names
        assert "cargo-mutants" not in names

    def test_get_clippy_category(self):
        from Lyncus.languages.rust_checks import get_clippy_category

        assert get_clippy_category("clippy::correctness::something") == "BUGPRONE"
        assert get_clippy_category("clippy::perf::something") == "PERF"
        assert get_clippy_category("clippy::style::something") == "STYLE"
        assert get_clippy_category("unused::var") == "DEADCODE"
        assert get_clippy_category("clippy::complexity::something") == "COMPLEXITY"
        assert get_clippy_category("unknown_lint") == "QUALITY"

    def test_get_clippy_severity(self):
        from Lyncus.languages.rust_checks import get_clippy_severity

        assert get_clippy_severity("error") == "critical"
        assert get_clippy_severity("warning") == "warning"
        assert get_clippy_severity("note") == "info"
        assert get_clippy_severity("help") == "info"
        assert get_clippy_severity("unknown") == "warning"

    def test_get_audit_severity_from_cvss(self):
        from Lyncus.languages.rust_checks import get_audit_severity

        assert get_audit_severity(9.5, "low") == "critical"
        assert get_audit_severity(7.0, "low") == "critical"
        assert get_audit_severity(5.0, "low") == "warning"
        assert get_audit_severity(2.0, "low") == "info"

    def test_get_audit_severity_from_advisory(self):
        from Lyncus.languages.rust_checks import get_audit_severity

        assert get_audit_severity(None, "critical") == "critical"
        assert get_audit_severity(None, "high") == "critical"
        assert get_audit_severity(None, "medium") == "warning"
        assert get_audit_severity(None, "low") == "info"
        assert get_audit_severity(None, "unknown_level") == "warning"

    def test_parse_rustfmt_diff(self):
        from Lyncus.languages.rust_checks import parse_rustfmt_diff

        output = "Diff in src/main.rs at line 42:\nDiff in src/lib.rs at line 10:\n"
        issues = parse_rustfmt_diff(output)
        assert len(issues) == 2
        assert issues[0]["file"] == "src/main.rs"
        assert issues[0]["line"] == 42
        assert issues[1]["line"] == 10

    def test_parse_rustfmt_diff_empty(self):
        from Lyncus.languages.rust_checks import parse_rustfmt_diff

        issues = parse_rustfmt_diff("")
        assert issues == []

    def test_parse_rustfmt_diff_invalid_line(self):
        from Lyncus.languages.rust_checks import parse_rustfmt_diff

        # Line without " at line " should be skipped
        output = "Some random output\nDiff in file.rs at line notanumber:\n"
        issues = parse_rustfmt_diff(output)
        assert len(issues) == 1
        assert issues[0]["line"] == 0

    def test_parse_tarpaulin_coverage(self):
        from Lyncus.languages.rust_checks import parse_tarpaulin_coverage

        output = "85.42% coverage, 1200/1405 lines covered"
        result = parse_tarpaulin_coverage(output)
        assert result is not None, "Coverage percentage parse nahi hua — regex check karo"
        assert abs(result - 85.42) < 0.01, f"Expected ~85.42, got {result}"

    def test_parse_tarpaulin_coverage_not_found(self):
        from Lyncus.languages.rust_checks import parse_tarpaulin_coverage

        result = parse_tarpaulin_coverage("No coverage data found")
        assert result is None

    def test_find_cargo_toml_direct(self):
        from Lyncus.languages.rust_checks import find_cargo_toml

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Cargo.toml").write_text('[package]\nname = "myapp"\n')
            result = find_cargo_toml(tmpdir)
            assert result == tmpdir

    def test_find_cargo_toml_parent(self):
        from Lyncus.languages.rust_checks import find_cargo_toml

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Cargo.toml").write_text('[package]\nname="x"\n')
            src_file = Path(tmpdir) / "src" / "main.rs"
            src_file.parent.mkdir()
            src_file.write_text("fn main() {}")
            result = find_cargo_toml(str(src_file))
            assert result == tmpdir

    def test_find_cargo_toml_not_found(self):
        from Lyncus.languages.rust_checks import find_cargo_toml

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_cargo_toml(tmpdir)
            assert result is None

    def test_get_install_commands(self):
        from Lyncus.languages.rust_checks import get_install_commands

        cmds = get_install_commands()
        assert "cargo-clippy" in cmds
        assert "cargo-audit" in cmds


# ══════════════════════════════════════════════════════════════════════════════
# js_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestJsChecks:
    def test_get_js_tools_all(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools()
        names = [t.name for t in tools]
        assert "eslint" in names
        assert "npm-audit" in names

    def test_get_js_tools_no_typescript(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(is_typescript=False)
        names = [t.name for t in tools]
        assert "tsc" not in names
        assert "ts-prune" not in names

    def test_get_js_tools_with_typescript(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(is_typescript=True)
        names = [t.name for t in tools]
        assert "tsc" in names
        assert "ts-prune" in names

    def test_get_js_tools_filter_security(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(only="security")
        assert all(t.check_type == "security" for t in tools)
        names = [t.name for t in tools]
        assert "npm-audit" in names

    def test_get_js_tools_skip_slow(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "stryker-js" not in names
        assert "c8" not in names

    def test_get_eslint_category(self):
        from Lyncus.languages.js_checks import get_eslint_category

        assert get_eslint_category("no-unused-vars") == "DEADCODE"
        assert get_eslint_category("no-eval") == "SECURITY"
        assert get_eslint_category("no-undef") == "QUALITY"
        assert get_eslint_category("eqeqeq") == "BUGPRONE"
        assert get_eslint_category("react/jsx-key") == "QUALITY"
        assert get_eslint_category("@typescript-eslint/no-explicit-any") == "TYPES"
        assert get_eslint_category(None) == "QUALITY"
        assert get_eslint_category("some-unknown-rule") == "QUALITY"

    def test_get_eslint_severity(self):
        from Lyncus.languages.js_checks import get_eslint_severity

        assert get_eslint_severity(2) == "critical"
        assert get_eslint_severity(1) == "warning"
        assert get_eslint_severity(0) == "warning"

    def test_parse_npm_audit_json_valid(self):
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "lodash": {
                    "severity": "high",
                    "via": [
                        {
                            "title": "Prototype Pollution",
                            "cve": "CVE-2021-1234",
                            "url": "https://advisory.example.com/1",
                        }
                    ],
                    "fixAvailable": {"version": "4.17.21"},
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert len(vulns) == 1
        assert vulns[0]["severity"] == "critical"
        assert vulns[0]["package"] == "lodash"
        assert vulns[0]["cve"] == "CVE-2021-1234"

    def test_parse_npm_audit_json_transitive_only_skipped(self):
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "transitive-pkg": {
                    "severity": "moderate",
                    "via": ["direct-dep"],  # string, not dict → transitive
                    "fixAvailable": False,
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert vulns == []

    def test_parse_npm_audit_json_empty(self):
        from Lyncus.languages.js_checks import parse_npm_audit_json

        vulns = parse_npm_audit_json('{"vulnerabilities": {}}')
        assert vulns == []

    def test_parse_npm_audit_json_invalid(self):
        from Lyncus.languages.js_checks import parse_npm_audit_json

        vulns = parse_npm_audit_json("broken json {{{")
        assert vulns == []

    def test_parse_tsc_output(self):
        from Lyncus.languages.js_checks import parse_tsc_output

        output = (
            "src/app.ts(10,5): error TS2345: Argument of type 'string' is not assignable\n"
            "src/utils.ts(42,1): warning TS6133: 'x' is declared but its value is never read\n"
        )
        issues = parse_tsc_output(output)
        assert len(issues) == 2
        assert issues[0]["severity"] == "critical"
        assert issues[0]["rule_id"] == "TS2345"
        assert issues[0]["category"] == "TYPE"
        assert issues[1]["severity"] == "warning"
        assert issues[1]["line"] == 42

    def test_parse_tsc_output_empty(self):
        from Lyncus.languages.js_checks import parse_tsc_output

        issues = parse_tsc_output("")
        assert issues == []

    def test_parse_ts_prune_output(self):
        from Lyncus.languages.js_checks import parse_ts_prune_output

        output = "src/helpers.ts:23 - unusedHelper\nsrc/types.ts:5 - MyType (used in module)\n"
        issues = parse_ts_prune_output(output)
        assert len(issues) == 1
        assert issues[0]["message"] == "Unused export: 'unusedHelper'"
        assert issues[0]["category"] == "DEADCODE"

    def test_parse_ts_prune_output_empty(self):
        from Lyncus.languages.js_checks import parse_ts_prune_output

        issues = parse_ts_prune_output("")
        assert issues == []

    def test_parse_depcheck_json_unused(self):
        from Lyncus.languages.js_checks import parse_depcheck_json

        data = {
            "dependencies": ["lodash", "moment"],
            "missing": {},
        }
        issues = parse_depcheck_json(json.dumps(data))
        assert len(issues) == 2
        assert all(i["severity"] == "warning" for i in issues)
        assert all(i["category"] == "DEADCODE" for i in issues)

    def test_parse_depcheck_json_missing(self):
        from Lyncus.languages.js_checks import parse_depcheck_json

        data = {
            "dependencies": [],
            "missing": {"axios": ["src/api.ts"]},
        }
        issues = parse_depcheck_json(json.dumps(data))
        assert len(issues) == 1
        assert issues[0]["severity"] == "critical"
        assert issues[0]["category"] == "QUALITY"

    def test_parse_depcheck_json_invalid(self):
        from Lyncus.languages.js_checks import parse_depcheck_json

        issues = parse_depcheck_json("not json")
        assert issues == []

    def test_find_package_json_direct(self):
        from Lyncus.languages.js_checks import find_package_json

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text('{"name":"app"}')
            result = find_package_json(tmpdir)
            assert result == tmpdir

    def test_find_package_json_not_found(self):
        from Lyncus.languages.js_checks import find_package_json

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_package_json(tmpdir)
            assert result is None

    def test_find_package_json_file_parent(self):
        from Lyncus.languages.js_checks import find_package_json

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text('{"name":"x"}')
            src = Path(tmpdir) / "index.js"
            src.write_text("console.log('hi')")
            result = find_package_json(str(src))
            assert result == tmpdir

    def test_is_typescript_project_tsconfig(self):
        from Lyncus.languages.js_checks import is_typescript_project

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "tsconfig.json").write_text("{}")
            assert is_typescript_project(tmpdir) is True

    def test_is_typescript_project_no_ts(self):
        from Lyncus.languages.js_checks import is_typescript_project

        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_typescript_project(tmpdir) is False

    def test_get_install_commands(self):
        from Lyncus.languages.js_checks import get_install_commands

        cmds = get_install_commands()
        assert "eslint" in cmds
        assert "npm-audit" in cmds


# ══════════════════════════════════════════════════════════════════════════════
# java_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestJavaChecks:
    def test_get_java_tools_all(self):
        from Lyncus.languages.java_checks import get_java_tools

        tools = get_java_tools()
        names = [t.name for t in tools]
        assert "checkstyle" in names
        assert "spotbugs" in names
        assert "pmd" in names

    def test_get_java_tools_filter_security(self):
        from Lyncus.languages.java_checks import get_java_tools

        tools = get_java_tools(only="security")
        assert all(t.check_type == "security" for t in tools)

    def test_get_java_tools_skip_slow(self):
        from Lyncus.languages.java_checks import get_java_tools

        tools = get_java_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "pitest" not in names
        assert "jacoco" not in names

    def test_get_java_tools_maven_only(self):
        from Lyncus.languages.java_checks import get_java_tools

        tools = get_java_tools(build_system="maven")
        for t in tools:
            assert t.build_tool in ("maven", "any")

    def test_parse_checkstyle_xml_valid(self):
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<?xml version="1.0"?>
<checkstyle version="10.17">
  <file name="src/Main.java">
    <error line="5" column="1" severity="error"
           message="Missing a Javadoc comment."
           source="com.puppycrawl.tools.checkstyle.checks.javadoc.JavadocMethodCheck"/>
    <error line="12" column="3" severity="warning"
           message="Line is too long (130 chars)."
           source="com.puppycrawl.tools.checkstyle.checks.design.SomeCheck"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert len(issues) == 2
        assert issues[0]["severity"] == "critical"
        assert issues[0]["line"] == 5
        assert issues[1]["severity"] == "warning"
        assert issues[1]["line"] == 12

    def test_parse_checkstyle_xml_category_mapping(self):
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<checkstyle>
  <file name="X.java">
    <error line="1" severity="warning" message="m"
           source="com.puppycrawl.tools.checkstyle.checks.imports.ImportControl"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert issues[0]["category"] == "IMPORTS"

    def test_parse_checkstyle_xml_invalid(self):
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        issues = parse_checkstyle_xml("not xml at all <<<")
        assert issues == []

    def test_parse_checkstyle_xml_empty(self):
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        issues = parse_checkstyle_xml("<checkstyle></checkstyle>")
        assert issues == []

    def test_parse_pmd_xml_valid(self):
        from Lyncus.languages.java_checks import parse_pmd_xml

        xml = """<?xml version="1.0"?>
<pmd>
  <file name="src/Auth.java">
    <violation beginline="30" begincolumn="5" priority="1"
               rule="SystemPrintln" ruleset="Best Practices">
      Avoid using System.out.println
    </violation>
    <violation beginline="50" begincolumn="10" priority="5"
               rule="UnusedImport" ruleset="Unnecessary">
      Unused import
    </violation>
  </file>
</pmd>"""
        issues = parse_pmd_xml(xml)
        assert len(issues) == 2
        assert issues[0]["severity"] == "critical"  # priority 1
        assert issues[1]["severity"] == "info"  # priority 5
        assert issues[1]["category"] == "DEADCODE"

    def test_parse_pmd_xml_invalid(self):
        from Lyncus.languages.java_checks import parse_pmd_xml

        issues = parse_pmd_xml("<<< broken >>>")
        assert issues == []

    def test_parse_jacoco_xml(self):
        from Lyncus.languages.java_checks import parse_jacoco_xml

        xml_content = """<?xml version="1.0"?>
<report name="MyApp">
  <counter type="INSTRUCTION" missed="100" covered="900"/>
  <counter type="BRANCH" missed="20" covered="80"/>
  <counter type="LINE" missed="50" covered="450"/>
  <counter type="METHOD" missed="5" covered="45"/>
</report>"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml_content)
            tmp = f.name
        try:
            result = parse_jacoco_xml(tmp)
            assert result["instruction_coverage"] is not None, (
                "instruction_coverage None nahi honi chahiye — XML parsing check karo"
            )
            assert abs(result["instruction_coverage"] - 90.0) < 0.1, (
                f"Expected ~90.0%, got {result['instruction_coverage']}"
            )
            assert result["branch_coverage"] is not None, (
                "branch_coverage None nahi honi chahiye"
            )
            assert abs(result["branch_coverage"] - 80.0) < 0.1, (
                f"Expected ~80.0%, got {result['branch_coverage']}"
            )
            assert result["line_coverage"] is not None, (
                "line_coverage None nahi honi chahiye"
            )
        finally:
            os.unlink(tmp)

    def test_parse_jacoco_xml_not_found(self):
        from Lyncus.languages.java_checks import parse_jacoco_xml

        result = parse_jacoco_xml("/nonexistent/path/jacoco.xml")
        assert result["instruction_coverage"] is None

    def test_detect_build_system_maven(self):
        from Lyncus.languages.java_checks import detect_build_system

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pom.xml").write_text("<project/>")
            result = detect_build_system(tmpdir)
            assert result == "maven"

    def test_detect_build_system_gradle(self):
        from Lyncus.languages.java_checks import detect_build_system

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "build.gradle").write_text("plugins {}")
            result = detect_build_system(tmpdir)
            assert result == "gradle"

    def test_detect_build_system_none(self):
        from Lyncus.languages.java_checks import detect_build_system

        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_build_system(tmpdir)
            assert result is None

    def test_find_java_files(self):
        from Lyncus.languages.java_checks import find_java_files

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Main.java").write_text("public class Main {}")
            target = Path(tmpdir) / "target"
            target.mkdir()
            (target / "Generated.java").write_text("// generated")
            files = find_java_files(tmpdir)
            assert any("Main.java" in f for f in files)
            assert not any("Generated.java" in f for f in files)

    def test_is_java_file(self):
        from Lyncus.languages.java_checks import is_java_file

        assert is_java_file("src/Main.java") is True
        assert is_java_file("src/App.kt") is True
        assert is_java_file("src/main.py") is False

    def test_spotbugs_severity(self):
        from Lyncus.languages.java_checks import _spotbugs_severity

        assert _spotbugs_severity(1) == "critical"
        assert _spotbugs_severity(2) == "warning"
        assert _spotbugs_severity(3) == "info"

    def test_spotbugs_category(self):
        from Lyncus.languages.java_checks import _spotbugs_category

        assert _spotbugs_category("SECURITY") == "SECURITY"
        assert _spotbugs_category("PERFORMANCE") == "PERF"
        assert _spotbugs_category("CORRECTNESS") == "BUGPRONE"
        assert _spotbugs_category("UNKNOWN") == "QUALITY"

    def test_pmd_severity_mapping(self):
        from Lyncus.languages.java_checks import _pmd_severity

        assert _pmd_severity(1) == "critical"
        assert _pmd_severity(2) == "critical"
        assert _pmd_severity(3) == "warning"
        assert _pmd_severity(4) == "info"
        assert _pmd_severity(5) == "info"

    def test_get_install_commands(self):
        from Lyncus.languages.java_checks import get_install_commands

        cmds = get_install_commands()
        assert "checkstyle" in cmds
        assert "pmd" in cmds

    def test_find_java_root(self):
        from Lyncus.languages.java_checks import find_java_root

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pom.xml").write_text("<project/>")
            result = find_java_root(tmpdir)
            assert result == tmpdir

    def test_find_java_root_not_found(self):
        from Lyncus.languages.java_checks import find_java_root

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_java_root(tmpdir)
            assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# kotlin_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestKotlinChecks:
    def test_get_kotlin_tools_all(self):
        from Lyncus.languages.kotlin_checks import get_kotlin_tools

        tools = get_kotlin_tools()
        names = [t.name for t in tools]
        assert "detekt" in names
        assert "ktlint" in names

    def test_get_kotlin_tools_filter_quality(self):
        from Lyncus.languages.kotlin_checks import get_kotlin_tools

        tools = get_kotlin_tools(only="quality")
        assert all(t.check_type == "quality" for t in tools)

    def test_get_kotlin_tools_skip_slow(self):
        from Lyncus.languages.kotlin_checks import get_kotlin_tools

        tools = get_kotlin_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "android-lint" not in names

    def test_parse_detekt_xml(self):
        from Lyncus.languages.kotlin_checks import parse_detekt_xml

        xml_content = """<?xml version="1.0"?>
<checkstyle>
  <file name="src/Main.kt">
    <error line="10" column="5" severity="error"
           message="Function too complex"
           source="detekt.complexity.CyclomaticComplexMethod"/>
    <error line="20" column="1" severity="warning"
           message="Unused import"
           source="detekt.style.UnusedImports"/>
  </file>
</checkstyle>"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml_content)
            tmp = f.name
        try:
            issues = parse_detekt_xml(tmp)
            assert len(issues) == 2
            assert issues[0]["severity"] == "critical"
            assert issues[0]["category"] == "COMPLEXITY"
            assert issues[1]["category"] == "STYLE"
        finally:
            os.unlink(tmp)

    def test_parse_detekt_xml_not_found(self):
        from Lyncus.languages.kotlin_checks import parse_detekt_xml

        # Non-existent file — should return empty list, not crash
        issues = parse_detekt_xml("/nonexistent/path/to/detekt.xml")
        assert issues == []

    def test_parse_ktlint_json(self):
        from Lyncus.languages.kotlin_checks import parse_ktlint_json

        data = [
            {
                "file": "src/Main.kt",
                "errors": [
                    {"line": 5, "col": 1, "rule": "indent", "message": "Unexpected indentation"},
                    {
                        "line": 10,
                        "col": 3,
                        "rule": "no-trailing-spaces",
                        "message": "Trailing space",
                    },
                ],
            }
        ]
        issues = parse_ktlint_json(json.dumps(data))
        assert len(issues) == 2
        assert issues[0]["file"] == "src/Main.kt"
        assert issues[0]["line"] == 5
        assert issues[0]["category"] == "STYLE"

    def test_parse_ktlint_json_invalid(self):
        from Lyncus.languages.kotlin_checks import parse_ktlint_json

        issues = parse_ktlint_json("not json {{")
        assert issues == []

    def test_parse_ktlint_json_empty(self):
        from Lyncus.languages.kotlin_checks import parse_ktlint_json

        issues = parse_ktlint_json("[]")
        assert issues == []

    def test_kotlin_severity(self):
        from Lyncus.languages.kotlin_checks import _kotlin_severity

        assert _kotlin_severity("error") == "critical"
        assert _kotlin_severity("warning") == "warning"
        assert _kotlin_severity("info") == "info"
        assert _kotlin_severity("unknown") == "warning"

    def test_detekt_category(self):
        from Lyncus.languages.kotlin_checks import _detekt_category

        assert _detekt_category("detekt.complexity.Something") == "COMPLEXITY"
        assert _detekt_category("detekt.security.Something") == "SECURITY"
        assert _detekt_category("detekt.performance.Something") == "PERF"
        assert _detekt_category("detekt.naming.Something") == "NAMING"
        assert _detekt_category("detekt.style.Something") == "STYLE"
        assert _detekt_category("detekt.unused.Something") == "DEADCODE"
        assert _detekt_category("detekt.exceptions.Something") == "BUGPRONE"
        assert _detekt_category("detekt.other.Something") == "QUALITY"

    def test_is_kotlin_file(self):
        from Lyncus.languages.kotlin_checks import is_kotlin_file

        assert is_kotlin_file("src/Main.kt") is True
        assert is_kotlin_file("build.gradle.kts") is True
        assert is_kotlin_file("main.java") is False

    def test_find_kotlin_root_gradle(self):
        from Lyncus.languages.kotlin_checks import find_kotlin_root

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "build.gradle.kts").write_text("plugins {}")
            result = find_kotlin_root(tmpdir)
            assert result == tmpdir

    def test_find_kotlin_root_not_found(self):
        from Lyncus.languages.kotlin_checks import find_kotlin_root

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_kotlin_root(tmpdir)
            assert result is None

    def test_get_install_commands(self):
        from Lyncus.languages.kotlin_checks import get_install_commands

        cmds = get_install_commands()
        assert "detekt" in cmds
        assert "ktlint" in cmds


# ══════════════════════════════════════════════════════════════════════════════
# swift_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestSwiftChecks:
    def test_get_swift_tools_all(self):
        from Lyncus.languages.swift_checks import get_swift_tools

        tools = get_swift_tools()
        names = [t.name for t in tools]
        assert "swiftlint" in names
        assert "periphery" in names

    def test_get_swift_tools_filter_quality(self):
        from Lyncus.languages.swift_checks import get_swift_tools

        tools = get_swift_tools(only="quality")
        assert all(t.check_type == "quality" for t in tools)

    def test_get_swift_tools_filter_deadcode(self):
        from Lyncus.languages.swift_checks import get_swift_tools

        tools = get_swift_tools(only="deadcode")
        names = [t.name for t in tools]
        assert "periphery" in names

    def test_get_swift_tools_skip_slow(self):
        from Lyncus.languages.swift_checks import get_swift_tools

        tools = get_swift_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "periphery" not in names

    def test_parse_swiftlint_json(self):
        from Lyncus.languages.swift_checks import parse_swiftlint_json

        data = [
            {
                "file": "/src/Auth.swift",
                "line": 42,
                "character": 5,
                "severity": "Error",
                "rule_id": "force_cast",
                "reason": "Force casts should be avoided",
                "type": "Lint",
            },
            {
                "file": "/src/Utils.swift",
                "line": 10,
                "character": 1,
                "severity": "Warning",
                "rule_id": "trailing_whitespace",
                "reason": "Lines should not have trailing whitespace",
                "type": "Style",
            },
        ]
        issues = parse_swiftlint_json(json.dumps(data))
        assert len(issues) == 2
        assert issues[0]["severity"] == "critical"
        assert issues[0]["rule_id"] == "SW-FORCE_CAST"
        assert issues[0]["category"] == "QUALITY"
        assert issues[1]["severity"] == "warning"
        assert issues[1]["category"] == "STYLE"

    def test_parse_swiftlint_json_invalid(self):
        from Lyncus.languages.swift_checks import parse_swiftlint_json

        issues = parse_swiftlint_json("not json")
        assert issues == []

    def test_parse_swiftlint_json_empty(self):
        from Lyncus.languages.swift_checks import parse_swiftlint_json

        issues = parse_swiftlint_json("[]")
        assert issues == []

    def test_parse_periphery_json(self):
        from Lyncus.languages.swift_checks import parse_periphery_json

        data = [
            {
                "message": "OldHelper is unused",
                "location": {"file": "src/Helpers.swift", "line": 15, "column": 5},
            }
        ]
        issues = parse_periphery_json(json.dumps(data))
        assert len(issues) == 1
        assert issues[0]["category"] == "DEADCODE"
        assert issues[0]["severity"] == "warning"
        assert issues[0]["line"] == 15

    def test_parse_periphery_json_invalid(self):
        from Lyncus.languages.swift_checks import parse_periphery_json

        issues = parse_periphery_json("not json")
        assert issues == []

    def test_swiftlint_category(self):
        from Lyncus.languages.swift_checks import _swiftlint_category

        assert _swiftlint_category("Style") == "STYLE"
        assert _swiftlint_category("Idiomatic") == "STYLE"
        assert _swiftlint_category("Performance") == "PERF"
        assert _swiftlint_category("Metrics") == "COMPLEXITY"
        assert _swiftlint_category("Lint") == "QUALITY"
        assert _swiftlint_category("Unknown") == "QUALITY"

    def test_is_swift_file(self):
        from Lyncus.languages.swift_checks import is_swift_file

        assert is_swift_file("src/Main.swift") is True
        assert is_swift_file("src/main.py") is False

    def test_find_swift_root_package(self):
        from Lyncus.languages.swift_checks import find_swift_root

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Package.swift").write_text("// swift-tools-version:5.10")
            result = find_swift_root(tmpdir)
            assert result == tmpdir

    def test_find_swift_root_not_found(self):
        from Lyncus.languages.swift_checks import find_swift_root

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_swift_root(tmpdir)
            assert result is None

    def test_get_install_commands(self):
        from Lyncus.languages.swift_checks import get_install_commands

        cmds = get_install_commands()
        assert "swiftlint" in cmds
        assert "periphery" in cmds


# ══════════════════════════════════════════════════════════════════════════════
# dart_checks.py  (0% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestDartChecks:
    def test_get_dart_tools_all(self):
        from Lyncus.languages.dart_checks import get_dart_tools

        tools = get_dart_tools()
        names = [t.name for t in tools]
        assert "dart-analyze" in names
        assert "dart-fix" in names

    def test_get_dart_tools_no_flutter(self):
        from Lyncus.languages.dart_checks import get_dart_tools

        tools = get_dart_tools(is_flutter=False)
        names = [t.name for t in tools]
        assert "flutter-analyze" not in names

    def test_get_dart_tools_with_flutter(self):
        from Lyncus.languages.dart_checks import get_dart_tools

        tools = get_dart_tools(is_flutter=True)
        names = [t.name for t in tools]
        assert "flutter-analyze" in names

    def test_get_dart_tools_filter_quality(self):
        from Lyncus.languages.dart_checks import get_dart_tools

        tools = get_dart_tools(only="quality")
        assert all(t.check_type == "quality" for t in tools)

    def test_get_dart_tools_skip_slow(self):
        from Lyncus.languages.dart_checks import get_dart_tools

        tools = get_dart_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "dart-test" not in names

    def test_parse_dart_analyze_output(self):
        from Lyncus.languages.dart_checks import parse_dart_analyze_output

        output = (
            "ERROR|STATIC_WARNING|UNUSED_IMPORT|lib/main.dart|5|1|6|Unused import: 'dart:io'\n"
            "WARNING|HINT|DEPRECATED_MEMBER_USE|lib/app.dart|42|3|10|Member is deprecated\n"
        )
        issues = parse_dart_analyze_output(output)
        assert len(issues) == 2
        assert issues[0]["severity"] == "critical"
        assert issues[0]["file"] == "lib/main.dart"
        assert issues[0]["line"] == 5
        assert issues[0]["category"] == "IMPORTS"
        assert issues[1]["severity"] == "warning"

    def test_parse_dart_analyze_output_empty(self):
        from Lyncus.languages.dart_checks import parse_dart_analyze_output

        issues = parse_dart_analyze_output("")
        assert issues == []

    def test_parse_dart_analyze_output_invalid_format(self):
        from Lyncus.languages.dart_checks import parse_dart_analyze_output

        # Pipe-separated but not enough parts
        issues = parse_dart_analyze_output("ERROR|ONLY_TWO_PARTS\n")
        assert issues == []

    def test_dart_severity(self):
        from Lyncus.languages.dart_checks import _dart_severity

        assert _dart_severity("ERROR") == "critical"
        assert _dart_severity("WARNING") == "warning"
        assert _dart_severity("INFO") == "info"
        assert _dart_severity("HINT") == "warning"  # default

    def test_dart_category(self):
        from Lyncus.languages.dart_checks import _dart_category

        assert _dart_category("UNUSED_IMPORT") == "IMPORTS"
        assert _dart_category("UNUSED_LOCAL_VARIABLE") == "DEADCODE"
        assert _dart_category("ARGUMENT_TYPE_NOT_ASSIGNABLE") == "TYPE"
        assert _dart_category("NULL_CHECK") == "BUGPRONE"
        assert _dart_category("IMPORT_OF_LEGACY") == "IMPORTS"
        assert _dart_category("SOME_OTHER") == "QUALITY"

    def test_is_dart_file(self):
        from Lyncus.languages.dart_checks import is_dart_file

        assert is_dart_file("lib/main.dart") is True
        assert is_dart_file("lib/main.py") is False

    def test_is_flutter_project_true(self):
        from Lyncus.languages.dart_checks import is_flutter_project

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pubspec.yaml").write_text(
                "name: my_app\nflutter:\n  uses-material-design: true\n"
            )
            assert is_flutter_project(tmpdir) is True

    def test_is_flutter_project_false(self):
        from Lyncus.languages.dart_checks import is_flutter_project

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pubspec.yaml").write_text("name: pure_dart\n")
            assert is_flutter_project(tmpdir) is False

    def test_is_flutter_project_no_pubspec(self):
        from Lyncus.languages.dart_checks import is_flutter_project

        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_flutter_project(tmpdir) is False

    def test_find_dart_root(self):
        from Lyncus.languages.dart_checks import find_dart_root

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pubspec.yaml").write_text("name: app\n")
            result = find_dart_root(tmpdir)
            assert result == tmpdir

    def test_find_dart_root_not_found(self):
        from Lyncus.languages.dart_checks import find_dart_root

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_dart_root(tmpdir)
            assert result is None

    def test_get_install_commands(self):
        from Lyncus.languages.dart_checks import get_install_commands

        cmds = get_install_commands()
        assert "dart-analyze" in cmds
        assert "dart-fix" in cmds


# ══════════════════════════════════════════════════════════════════════════════
# core/reporter.py  (46% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestReporter:
    def _make_problems(self):
        from Lyncus.core.parser import Problem

        return [
            Problem(
                tool="ruff",
                rule_id="E501",
                category="STYLE",
                severity="warning",
                file="src/a.py",
                line=10,
                column=80,
                message="Line too long",
            ),
            Problem(
                tool="bandit",
                rule_id="B201",
                category="SECURITY",
                severity="critical",
                file="src/b.py",
                line=5,
                column=0,
                message="Hardcoded password",
                suggestion="Use env vars",
            ),
            Problem(
                tool="mypy",
                rule_id="M001",
                category="TYPE",
                severity="info",
                file="src/c.py",
                line=1,
                column=0,
                message="Type mismatch",
            ),
        ]

    def test_score_all_clear(self):
        from Lyncus.core.reporter import _score

        assert _score([]) == 100

    def test_score_with_criticals(self):
        from Lyncus.core.parser import Problem
        from Lyncus.core.reporter import _score

        probs = [
            Problem(
                tool="x",
                rule_id="X1",
                category="C",
                severity="critical",
                file="f.py",
                line=1,
                column=0,
                message="m",
            ),
            Problem(
                tool="x",
                rule_id="X2",
                category="C",
                severity="critical",
                file="f.py",
                line=2,
                column=0,
                message="m",
            ),
        ]
        score = _score(probs)
        assert score == 70  # 100 - (2*15)

    def test_score_never_negative(self):
        from Lyncus.core.parser import Problem
        from Lyncus.core.reporter import _score

        probs = [
            Problem(
                tool="x",
                rule_id=f"X{i}",
                category="C",
                severity="critical",
                file="f.py",
                line=i,
                column=0,
                message="m",
            )
            for i in range(20)
        ]
        assert _score(probs) == 0

    def test_score_color(self):
        from Lyncus.core.reporter import _score_color

        assert _score_color(90) == "green"
        assert _score_color(80) == "green"
        assert _score_color(60) == "yellow"
        assert _score_color(50) == "yellow"
        assert _score_color(49) == "red"

    def test_score_emoji(self):
        from Lyncus.core.reporter import _score_emoji

        assert _score_emoji(85) == "🟢"
        assert _score_emoji(60) == "🟡"
        assert _score_emoji(30) == "🔴"

    def test_export_json(self):
        from Lyncus.core.reporter import export_json

        problems = self._make_problems()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.json")
            export_json(problems, "/myproject", "python", 1.5, out)
            assert Path(out).exists()
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
            assert data["language"] == "python"
            assert data["summary"]["critical"] == 1
            assert data["summary"]["warning"] == 1
            assert data["summary"]["info"] == 1
            assert len(data["problems"]) == 3

    def test_export_html(self):
        from Lyncus.core.reporter import export_html

        problems = self._make_problems()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.html")
            export_html(problems, "/myproject", "python", 2.0, out)
            content = Path(out).read_text(encoding="utf-8")
            assert "Lyncus" in content
            assert "CRITICAL" in content or "critical" in content

    def test_export_html_empty(self):
        from Lyncus.core.reporter import export_html

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "empty.html")
            export_html([], "/myproject", "python", 0.5, out)
            content = Path(out).read_text(encoding="utf-8")
            assert "100" in content  # perfect score

    def test_print_problems_no_output_when_empty(self):
        from Lyncus.core.reporter import print_problems

        # Should not crash with empty list
        print_problems([])

    def test_print_summary_runs(self):
        from Lyncus.core.reporter import print_summary

        # Should not raise
        problems = self._make_problems()
        print_summary(problems, scan_time=1.5, files_scanned=10, skipped_tools=["bandit"])

    def test_print_header_runs(self):
        from Lyncus.core.reporter import print_header

        print_header("/project", "python", ["ruff", "mypy"])

    def test_print_problems_with_filter(self):
        from Lyncus.core.reporter import print_problems

        problems = self._make_problems()
        # severity_filter applies — should not crash
        print_problems(problems, severity_filter="critical")
        print_problems(problems, severity_filter="warning")
        print_problems(problems, severity_filter="info")

    def test_print_problems_with_suggestion(self):
        from Lyncus.core.reporter import print_problems

        problems = self._make_problems()
        # Problem with suggestion — _print_group branch
        print_problems(problems, severity_filter="critical")

    def test_make_progress(self):
        from Lyncus.core.reporter import make_progress

        p = make_progress()
        assert p is not None


# ══════════════════════════════════════════════════════════════════════════════
# core/install_deps.py  (52% → 80%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestInstallDepsExtended:
    def test_get_tools_for_all_languages(self):
        from Lyncus.core.install_deps import get_tools_for_language

        # install_deps.py mein "js" hai "javascript" nahi
        for lang in ["python", "rust", "go", "js", "java", "ruby", "php", "cpp", "csharp"]:
            tools = get_tools_for_language(lang)
            assert isinstance(tools, list), f"{lang} ne list return nahi ki"

    def test_tool_dataclass_fields(self):
        from Lyncus.core.install_deps import get_tools_for_language

        tools = get_tools_for_language("python")
        for t in tools:
            assert hasattr(t, "name")
            assert hasattr(t, "install_cmds")

    def test_pick_install_cmd_pip_universal(self):
        from Lyncus.core.install_deps import _pick_install_cmd

        result = _pick_install_cmd(["pip install ruff"])
        assert result == "pip install ruff"

    def test_pick_install_cmd_empty_returns_none(self):
        from Lyncus.core.install_deps import _pick_install_cmd

        result = _pick_install_cmd([])
        assert result is None

    def test_pick_install_cmd_npm(self):
        from Lyncus.core.install_deps import _pick_install_cmd

        result = _pick_install_cmd(["npm install -g eslint"])
        assert result == "npm install -g eslint"

    def test_pick_install_cmd_cargo(self):
        from Lyncus.core.install_deps import _pick_install_cmd

        result = _pick_install_cmd(["cargo install cargo-audit"])
        assert result == "cargo install cargo-audit"

    def test_pick_install_cmd_fallback_first(self):
        from Lyncus.core.install_deps import _pick_install_cmd

        # No known prefix — fallback to first
        result = _pick_install_cmd(["some-random-tool install x", "another-tool"])
        assert result == "some-random-tool install x"

    def test_get_missing_and_available(self):
        from Lyncus.core.install_deps import (
            get_available_tools,
            get_missing_tools,
            get_tools_for_language,
        )

        missing = get_missing_tools("python")
        available = get_available_tools("python")
        total = get_tools_for_language("python")
        assert len(missing) + len(available) == len(total)

    def test_print_doctor_table_python(self):
        from Lyncus.core.install_deps import print_doctor_table

        # Should not crash
        print_doctor_table("python")

    def test_print_doctor_table_all(self):
        from Lyncus.core.install_deps import print_doctor_table

        print_doctor_table("all")

    def test_print_doctor_table_unknown_lang(self):
        from Lyncus.core.install_deps import print_doctor_table

        print_doctor_table("cobol")

    def test_install_missing_dry_run_python(self):
        from Lyncus.core.install_deps import install_missing

        # dry_run=True should not actually install anything
        install_missing("python", dry_run=True)

    def test_install_missing_dry_run_all(self):
        from Lyncus.core.install_deps import install_missing

        install_missing("all", dry_run=True)


# ══════════════════════════════════════════════════════════════════════════════
# languages/python_checks.py  (73% → 85%+)
# ══════════════════════════════════════════════════════════════════════════════


class TestPythonChecksExtended:
    def test_get_python_tools_all(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools()
        names = [t.name for t in tools]
        assert "ruff" in names
        assert "mypy" in names
        assert "bandit" in names
        assert "vulture" in names

    def test_get_python_tools_filter_security(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools(only="security")
        assert all(t.check_type == "security" for t in tools)
        names = [t.name for t in tools]
        assert "bandit" in names

    def test_get_python_tools_filter_deadcode(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools(only="deadcode")
        names = [t.name for t in tools]
        assert "vulture" in names

    def test_get_python_tools_skip_slow(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools(skip_slow=True)
        names = [t.name for t in tools]
        assert "mutmut" not in names

    def test_get_ruff_category(self):
        from Lyncus.languages.python_checks import get_ruff_category

        assert get_ruff_category("E501") == "STYLE"
        assert get_ruff_category("W291") == "STYLE"
        assert get_ruff_category("F401") == "QUALITY"
        assert get_ruff_category("S101") == "SECURITY"
        assert get_ruff_category("B001") == "BUGPRONE"
        assert get_ruff_category("I001") == "IMPORTS"
        assert get_ruff_category("N801") == "NAMING"
        assert get_ruff_category("UP001") == "UPGRADE"
        assert get_ruff_category("ERA001") == "DEADCODE"
        assert get_ruff_category("PERF001") == "PERF"
        assert get_ruff_category("UNKNOWN") == "QUALITY"

    def test_get_ruff_severity(self):
        from Lyncus.languages.python_checks import get_ruff_severity

        assert get_ruff_severity("S101") == "critical"
        assert get_ruff_severity("B001") == "critical"
        assert get_ruff_severity("E9") == "critical"
        assert get_ruff_severity("F401") == "warning"
        assert get_ruff_severity("W291") == "warning"
        assert get_ruff_severity("RUF001") == "info"

    def test_get_mypy_category(self):
        from Lyncus.languages.python_checks import get_mypy_category

        assert get_mypy_category("arg-type") == "TYPE"
        assert get_mypy_category("assignment") == "TYPE"
        assert get_mypy_category("import") == "IMPORTS"
        assert get_mypy_category("name-defined") == "QUALITY"
        assert get_mypy_category("unknown-code") == "TYPE"

    def test_get_bandit_description_known(self):
        from Lyncus.languages.python_checks import get_bandit_description

        desc = get_bandit_description("B307")
        assert "eval" in desc.lower()

    def test_get_bandit_description_unknown(self):
        from Lyncus.languages.python_checks import get_bandit_description

        desc = get_bandit_description("B999")
        assert "B999" in desc

    def test_get_radon_severity(self):
        from Lyncus.languages.python_checks import get_radon_severity

        assert get_radon_severity("A") == "info"
        assert get_radon_severity("B") == "info"
        assert get_radon_severity("C") == "warning"
        assert get_radon_severity("D") == "warning"
        assert get_radon_severity("E") == "critical"
        assert get_radon_severity("F") == "critical"
        assert get_radon_severity("Z") == "info"  # unknown → default

    def test_get_radon_description(self):
        from Lyncus.languages.python_checks import get_radon_description

        desc = get_radon_description("F")
        assert "extreme" in desc.lower() or "complexity" in desc.lower()

    def test_get_vulture_severity(self):
        from Lyncus.languages.python_checks import get_vulture_severity

        assert get_vulture_severity(95) == "critical"
        assert get_vulture_severity(90) == "critical"
        assert get_vulture_severity(80) == "warning"
        assert get_vulture_severity(70) == "warning"
        assert get_vulture_severity(50) == "info"

    def test_get_install_commands(self):
        from Lyncus.languages.python_checks import get_install_commands

        cmds = get_install_commands()
        assert "ruff" in cmds
        assert "mypy" in cmds
        assert "bandit" in cmds

    def test_get_ruff_category_all_prefixes(self):
        """Har RUFF_CATEGORY_MAP prefix ke liye category check karo."""
        from Lyncus.languages.python_checks import get_ruff_category

        # Single-letter prefixes
        assert get_ruff_category("E501") == "STYLE"
        assert get_ruff_category("W503") == "STYLE"
        assert get_ruff_category("F811") == "QUALITY"
        assert get_ruff_category("I001") == "IMPORTS"
        assert get_ruff_category("N803") == "NAMING"
        assert get_ruff_category("B006") == "BUGPRONE"
        assert get_ruff_category("C901") == "COMPLEXITY"
        assert get_ruff_category("S301") == "SECURITY"
        assert get_ruff_category("T201") == "PRINT"
        assert get_ruff_category("Q000") == "QUOTES"
        assert get_ruff_category("D401") == "DOCSTRING"
        # Multi-letter prefixes (longer ones take priority)
        assert get_ruff_category("UP032") == "UPGRADE"
        assert get_ruff_category("RUF001") == "RUFF"
        assert get_ruff_category("ANN201") == "TYPES"
        assert get_ruff_category("ERA001") == "DEADCODE"
        assert get_ruff_category("PL001") == "PYLINT"
        assert get_ruff_category("PT001") == "PYTEST"
        assert get_ruff_category("SIM001") == "SIMPLIFY"
        assert get_ruff_category("TID001") == "TIDY"
        assert get_ruff_category("TCH001") == "TYPECHECK"
        assert get_ruff_category("ARG001") == "UNUSED"
        assert get_ruff_category("PTH001") == "PATHLIB"
        assert get_ruff_category("FLY001") == "FSTRING"
        assert get_ruff_category("PERF001") == "PERF"
        assert get_ruff_category("FURB001") == "REFACTOR"
        assert get_ruff_category("LOG001") == "LOGGING"
        assert get_ruff_category("RET001") == "RETURN"
        # Unknown → QUALITY
        assert get_ruff_category("ZZZ999") == "QUALITY"

    def test_get_ruff_severity_edge_cases(self):
        """get_ruff_severity ke saare branches test karo."""
        from Lyncus.languages.python_checks import get_ruff_severity

        # critical_prefixes: S, B, E9, F8
        assert get_ruff_severity("S501") == "critical"
        assert get_ruff_severity("B999") == "critical"
        assert get_ruff_severity("E901") == "critical"
        assert get_ruff_severity("F841") == "critical"  # F8x → critical
        # warning_prefixes: F, W, N, UP, PL, SIM, RET  (B already critical)
        assert get_ruff_severity("F401") == "warning"
        assert get_ruff_severity("W291") == "warning"
        assert get_ruff_severity("N803") == "warning"
        assert get_ruff_severity("UP001") == "warning"
        assert get_ruff_severity("PL001") == "warning"
        assert get_ruff_severity("SIM001") == "warning"
        assert get_ruff_severity("RET001") == "warning"
        # info fallback
        assert get_ruff_severity("D401") == "info"
        assert get_ruff_severity("ANN201") == "info"

    def test_get_radon_description_all_grades(self):
        """Radon description map ki sab values check karo."""
        from Lyncus.languages.python_checks import get_radon_description

        assert "simple" in get_radon_description("A").lower()
        assert "acceptable" in get_radon_description("B").lower()
        assert "moderate" in get_radon_description("C").lower()
        assert "high" in get_radon_description("D").lower()
        assert "very high" in get_radon_description("E").lower()
        assert "extreme" in get_radon_description("F").lower()
        # Unknown grade → fallback string includes grade
        assert "X" in get_radon_description("X")

    def test_get_python_tools_filter_complexity(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools(only="complexity")
        names = [t.name for t in tools]
        assert "radon" in names
        assert "ruff" not in names

    def test_get_python_tools_filter_deps(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools(only="deps")
        names = [t.name for t in tools]
        assert "pip-audit" in names

    def test_get_python_tools_filter_faketests(self):
        from Lyncus.languages.python_checks import get_python_tools

        tools = get_python_tools(only="faketests")
        names = [t.name for t in tools]
        assert "mutmut" in names

    def test_python_tool_has_expected_attributes(self):
        from Lyncus.languages.python_checks import get_python_tools

        for t in get_python_tools():
            assert t.name
            assert t.command
            assert t.check_type
            assert t.output_format in ("text", "json")
            assert t.description
            assert t.min_version
            assert t.install_cmd


# ══════════════════════════════════════════════════════════════════════════════
# Lyncus/__init__.py — resolve_language  (no tests → 100%)
# ══════════════════════════════════════════════════════════════════════════════


class TestResolveLanguage:
    """resolve_language function ke saare branches aur aliases test karo."""

    def test_direct_canonical_names(self):
        from Lyncus import resolve_language

        for lang in [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "cpp",
            "cuda",
            "csharp",
            "java",
            "ruby",
            "php",
        ]:
            assert resolve_language(lang) == lang

    def test_known_aliases(self):
        from Lyncus import resolve_language

        assert resolve_language("py") == "python"
        assert resolve_language("js") == "javascript"
        assert resolve_language("ts") == "typescript"
        assert resolve_language("c++") == "cpp"
        assert resolve_language("c") == "cpp"
        assert resolve_language("cs") == "csharp"
        assert resolve_language("c#") == "csharp"
        assert resolve_language("dotnet") == "csharp"
        assert resolve_language("rb") == "ruby"
        assert resolve_language("golang") == "go"
        assert resolve_language("rs") == "rust"
        assert resolve_language("node") == "javascript"
        assert resolve_language("nodejs") == "javascript"
        assert resolve_language("cu") == "cuda"
        assert resolve_language("java") == "java"
        assert resolve_language("php") == "php"

    def test_case_insensitive(self):
        from Lyncus import resolve_language

        assert resolve_language("Python") == "python"
        assert resolve_language("PYTHON") == "python"
        assert resolve_language("JS") == "javascript"
        assert resolve_language("Ts") == "typescript"
        assert resolve_language("Go") == "go"
        assert resolve_language("RUST") == "rust"

    def test_unknown_language_returns_lowercased(self):
        from Lyncus import resolve_language

        assert resolve_language("Haskell") == "haskell"
        assert resolve_language("BRAINFUCK") == "brainfuck"
        assert resolve_language("Cobol") == "cobol"

    def test_return_type_is_str(self):
        from Lyncus import resolve_language

        result = resolve_language("py")
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# java_checks.py — parse_spotbugs_xml  (no tests → 100%)
# ══════════════════════════════════════════════════════════════════════════════


class TestParseSpotbugsXml:
    """parse_spotbugs_xml aur helper functions ke tests."""

    def _write_xml(self, xml_content: str) -> str:
        """Temporary XML file likhkar path return karo."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml_content)
            f.flush()
            temp_path = f.name
        return temp_path

    def test_parse_valid_single_bug(self):
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection>
  <BugInstance type="NP_NULL_ON_SOME_PATH" priority="1" category="CORRECTNESS">
    <ShortMessage>Null pointer dereference</ShortMessage>
    <SourceLine sourcepath="src/Main.java" start="42"/>
  </BugInstance>
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            issues = parse_spotbugs_xml(tmp)
            assert len(issues) == 1
            assert issues[0]["severity"] == "critical"
            assert issues[0]["rule_id"] == "SB-NP_NULL_ON_SOME_PATH"
            assert issues[0]["file"] == "src/Main.java"
            assert issues[0]["line"] == 42
            assert issues[0]["category"] == "BUGPRONE"
            assert "Null pointer" in issues[0]["message"]
        finally:
            os.unlink(tmp)

    def test_parse_multiple_bugs(self):
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection>
  <BugInstance type="SQL_INJECTION" priority="1" category="SECURITY">
    <ShortMessage>SQL injection possible</ShortMessage>
    <SourceLine sourcepath="dao/UserDao.java" start="10"/>
  </BugInstance>
  <BugInstance type="DM_NUMBER_CTOR" priority="2" category="PERFORMANCE">
    <ShortMessage>Use static factory instead</ShortMessage>
    <SourceLine sourcepath="util/Helper.java" start="20"/>
  </BugInstance>
  <BugInstance type="MS_MUTABLE_ARRAY" priority="3" category="STYLE">
    <ShortMessage>Mutable static array</ShortMessage>
    <SourceLine sourcepath="util/Constants.java" start="5"/>
  </BugInstance>
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            issues = parse_spotbugs_xml(tmp)
            assert len(issues) == 3
            assert issues[0]["severity"] == "critical"
            assert issues[0]["category"] == "SECURITY"
            assert issues[1]["severity"] == "warning"
            assert issues[1]["category"] == "PERF"
            assert issues[2]["severity"] == "info"
            assert issues[2]["category"] == "STYLE"
        finally:
            os.unlink(tmp)

    def test_parse_bug_without_source_line(self):
        """SourceLine element nahi hai — graceful handling."""
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection>
  <BugInstance type="EQ_COMPARETO_USE_OBJECT_EQUALS" priority="2" category="BAD_PRACTICE">
    <ShortMessage>Class implements Comparable but not equals</ShortMessage>
  </BugInstance>
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            issues = parse_spotbugs_xml(tmp)
            assert len(issues) == 1
            assert issues[0]["file"] == ""
            assert issues[0]["line"] == 0
            assert issues[0]["category"] == "QUALITY"
        finally:
            os.unlink(tmp)

    def test_parse_bug_without_short_message(self):
        """ShortMessage element nahi hai — bug_type fallback."""
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection>
  <BugInstance type="NP_ALWAYS_NULL" priority="2" category="CORRECTNESS">
    <SourceLine sourcepath="Foo.java" start="7"/>
  </BugInstance>
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            issues = parse_spotbugs_xml(tmp)
            assert len(issues) == 1
            # Fallback: message should be the bug type itself
            assert issues[0]["message"] == "NP_ALWAYS_NULL"
        finally:
            os.unlink(tmp)

    def test_parse_invalid_xml(self):
        """Malformed XML — should return empty list."""
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        tmp = self._write_xml("<<< NOT VALID XML >>>")
        try:
            issues = parse_spotbugs_xml(tmp)
            assert issues == []
        finally:
            os.unlink(tmp)

    def test_parse_empty_bug_collection(self):
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection version="4.8">
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            issues = parse_spotbugs_xml(tmp)
            assert issues == []
        finally:
            os.unlink(tmp)

    def test_parse_nonexistent_file(self):
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        issues = parse_spotbugs_xml("/nonexistent/path/spotbugs.xml")
        assert issues == []

    def test_spotbugs_severity_all_priorities(self):
        from Lyncus.languages.java_checks import _spotbugs_severity

        assert _spotbugs_severity(1) == "critical"
        assert _spotbugs_severity(2) == "warning"
        assert _spotbugs_severity(3) == "info"
        assert _spotbugs_severity(4) == "info"  # any non-1, non-2 → info
        assert _spotbugs_severity(0) == "info"

    def test_spotbugs_category_all_known(self):
        from Lyncus.languages.java_checks import _spotbugs_category

        assert _spotbugs_category("CORRECTNESS") == "BUGPRONE"
        assert _spotbugs_category("BAD_PRACTICE") == "QUALITY"
        assert _spotbugs_category("MALICIOUS_CODE") == "SECURITY"
        assert _spotbugs_category("MT_CORRECTNESS") == "BUGPRONE"
        assert _spotbugs_category("PERFORMANCE") == "PERF"
        assert _spotbugs_category("SECURITY") == "SECURITY"
        assert _spotbugs_category("STYLE") == "STYLE"
        assert _spotbugs_category("EXPERIMENTAL") == "QUALITY"
        assert _spotbugs_category("I18N") == "QUALITY"

    def test_spotbugs_category_case_insensitive_lookup(self):
        from Lyncus.languages.java_checks import _spotbugs_category

        # cat_map.get uses category.upper() → lowercase input should work
        assert _spotbugs_category("security") == "SECURITY"
        assert _spotbugs_category("performance") == "PERF"

    def test_spotbugs_category_unknown(self):
        from Lyncus.languages.java_checks import _spotbugs_category

        assert _spotbugs_category("UNKNOWN_CAT") == "QUALITY"

    def test_parse_bug_column_always_zero(self):
        """SpotBugs mein column hamesha 0 hona chahiye."""
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection>
  <BugInstance type="NP_ALWAYS_NULL" priority="2" category="CORRECTNESS">
    <ShortMessage>Null</ShortMessage>
    <SourceLine sourcepath="A.java" start="1"/>
  </BugInstance>
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            issues = parse_spotbugs_xml(tmp)
            assert issues[0]["column"] == 0
        finally:
            os.unlink(tmp)

    def test_parse_bad_priority_value(self):
        """Priority string nahi parse ho sakti — ValueError graceful handle ho."""
        from Lyncus.languages.java_checks import parse_spotbugs_xml

        xml = """<?xml version="1.0"?>
<BugCollection>
  <BugInstance type="NP_NULL" priority="notanumber" category="CORRECTNESS">
    <ShortMessage>Bad priority</ShortMessage>
    <SourceLine sourcepath="X.java" start="1"/>
  </BugInstance>
</BugCollection>"""
        tmp = self._write_xml(xml)
        try:
            # Should either skip this entry or return empty — not crash
            issues = parse_spotbugs_xml(tmp)
            assert isinstance(issues, list)
        finally:
            os.unlink(tmp)


# ══════════════════════════════════════════════════════════════════════════════
# js_checks.py — survived mutations ke liye extra tests
# ══════════════════════════════════════════════════════════════════════════════


class TestJsChecksExtended:
    """js_checks ke survived mutations kill karne ke liye targeted tests."""

    def test_parse_npm_audit_fix_available_dict(self):
        """fixAvailable dict hone par version extract ho."""
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "express": {
                    "severity": "critical",
                    "via": [{"title": "RCE", "cve": "CVE-2024-1", "url": "https://x.com"}],
                    "fixAvailable": {"name": "express", "version": "5.0.0"},
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert len(vulns) == 1
        assert vulns[0]["fixed_in"] == "5.0.0"
        assert vulns[0]["severity"] == "critical"

    def test_parse_npm_audit_fix_available_false(self):
        """fixAvailable False ho to fixed_in empty string."""
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "old-pkg": {
                    "severity": "moderate",
                    "via": [{"title": "XSS", "cve": "CVE-2024-2", "url": "https://y.com"}],
                    "fixAvailable": False,
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert len(vulns) == 1
        assert vulns[0]["fixed_in"] == ""
        assert vulns[0]["severity"] == "warning"

    def test_parse_npm_audit_low_severity(self):
        """low severity → info."""
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "minor-pkg": {
                    "severity": "low",
                    "via": [{"title": "Minor issue", "cve": "", "url": ""}],
                    "fixAvailable": False,
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert vulns[0]["severity"] == "info"

    def test_parse_npm_audit_info_severity(self):
        """info severity → info."""
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "info-pkg": {
                    "severity": "info",
                    "via": [{"title": "Info issue", "cve": "", "url": ""}],
                    "fixAvailable": False,
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert vulns[0]["severity"] == "info"

    def test_parse_npm_audit_description_format(self):
        """description field mein package name aur title ho."""
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "lodash": {
                    "severity": "high",
                    "via": [{"title": "Prototype Pollution", "cve": "CVE-X", "url": ""}],
                    "fixAvailable": False,
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert "lodash" in vulns[0]["description"]
        assert "Prototype Pollution" in vulns[0]["description"]

    def test_parse_npm_audit_multiple_via_entries(self):
        """Ek package ke multiple direct vulnerabilities."""
        from Lyncus.languages.js_checks import parse_npm_audit_json

        data = {
            "vulnerabilities": {
                "multi-vuln": {
                    "severity": "high",
                    "via": [
                        {"title": "CVE-A", "cve": "CVE-A", "url": ""},
                        {"title": "CVE-B", "cve": "CVE-B", "url": ""},
                    ],
                    "fixAvailable": False,
                }
            }
        }
        vulns = parse_npm_audit_json(json.dumps(data))
        assert len(vulns) == 2

    def test_parse_tsc_output_column_parsed(self):
        """tsc output mein column bhi sahi parse ho."""
        from Lyncus.languages.js_checks import parse_tsc_output

        output = "lib/index.ts(5,12): error TS2322: Type 'string' is not assignable to 'number'\n"
        issues = parse_tsc_output(output)
        assert len(issues) == 1
        assert issues[0]["line"] == 5
        assert issues[0]["column"] == 12
        assert issues[0]["rule_id"] == "TS2322"
        assert issues[0]["category"] == "TYPE"

    def test_parse_tsc_output_multiple_errors(self):
        from Lyncus.languages.js_checks import parse_tsc_output

        output = (
            "a.ts(1,1): error TS2345: X\nb.ts(2,3): error TS2322: Y\nc.ts(3,5): warning TS6133: Z\n"
        )
        issues = parse_tsc_output(output)
        assert len(issues) == 3
        assert issues[0]["file"] == "a.ts"
        assert issues[2]["severity"] == "warning"

    def test_parse_ts_prune_used_in_module_filtered(self):
        """'used in module' wali entries skip honin chahiye."""
        from Lyncus.languages.js_checks import parse_ts_prune_output

        output = (
            "src/a.ts:10 - usedFunc (used in module)\n"
            "src/b.ts:20 - unusedFunc\n"
            "src/c.ts:30 - anotherUnused (exported but not used anywhere)\n"
        )
        issues = parse_ts_prune_output(output)
        # sirf non-"used in module" entries aayein
        assert len(issues) == 2
        assert any("unusedFunc" in i["message"] for i in issues)
        assert not any("'usedFunc'" in i["message"] for i in issues)

    def test_parse_ts_prune_line_number(self):
        from Lyncus.languages.js_checks import parse_ts_prune_output

        output = "src/helpers.ts:99 - deadHelper\n"
        issues = parse_ts_prune_output(output)
        assert issues[0]["line"] == 99
        assert issues[0]["column"] == 0

    def test_parse_depcheck_both_unused_and_missing(self):
        """unused aur missing dono ek saath."""
        from Lyncus.languages.js_checks import parse_depcheck_json

        data = {
            "dependencies": ["leftpad", "moment"],
            "missing": {"react": ["src/App.tsx"], "axios": ["src/api.ts"]},
        }
        issues = parse_depcheck_json(json.dumps(data))
        # 2 unused (warning) + 2 missing (critical)
        assert len(issues) == 4
        warnings = [i for i in issues if i["severity"] == "warning"]
        criticals = [i for i in issues if i["severity"] == "critical"]
        assert len(warnings) == 2
        assert len(criticals) == 2

    def test_parse_depcheck_unused_message_format(self):
        from Lyncus.languages.js_checks import parse_depcheck_json

        data = {"dependencies": ["lodash"], "missing": {}}
        issues = parse_depcheck_json(json.dumps(data))
        assert "lodash" in issues[0]["message"]
        assert issues[0]["rule_id"] == "DEPCHECK-UNUSED"
        assert issues[0]["category"] == "DEADCODE"

    def test_parse_depcheck_missing_file_reference(self):
        """missing dependency ka file pehla usage file ho."""
        from Lyncus.languages.js_checks import parse_depcheck_json

        data = {
            "dependencies": [],
            "missing": {"uuid": ["src/utils.ts", "src/api.ts"]},
        }
        issues = parse_depcheck_json(json.dumps(data))
        assert issues[0]["file"] == "src/utils.ts"

    def test_parse_depcheck_missing_no_usages(self):
        """missing dependency ki usages empty list ho."""
        from Lyncus.languages.js_checks import parse_depcheck_json

        data = {
            "dependencies": [],
            "missing": {"empty-dep": []},
        }
        issues = parse_depcheck_json(json.dumps(data))
        assert issues[0]["file"] == "unknown"

    def test_find_package_json_nested(self):
        """Nested directory mein package.json dhundna."""
        from Lyncus.languages.js_checks import find_package_json

        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "packages" / "app"
            subdir.mkdir(parents=True)
            (subdir / "package.json").write_text('{"name":"nested"}')
            result = find_package_json(tmpdir)
            assert result is not None, (
                f"Nested package.json nahi mila — find_package_json recursive nahi kar raha: {tmpdir}"
            )
            assert "packages" in result or "app" in result or result == tmpdir, (
                f"Unexpected path returned: {result}"
            )

    def test_find_package_json_skips_node_modules(self):
        """node_modules ke andar package.json ignore ho."""
        from Lyncus.languages.js_checks import find_package_json

        with tempfile.TemporaryDirectory() as tmpdir:
            nm = Path(tmpdir) / "node_modules" / "some-lib"
            nm.mkdir(parents=True)
            (nm / "package.json").write_text('{"name":"lib"}')
            result = find_package_json(tmpdir)
            # node_modules ke bahar nahi mila — None return ho
            assert result is None

    def test_is_typescript_project_ts_files(self):
        """tsconfig nahi but .ts files hain."""
        from Lyncus.languages.js_checks import is_typescript_project

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src"
            src.mkdir()
            (src / "index.ts").write_text("const x: number = 1;")
            assert is_typescript_project(tmpdir) is True

    def test_is_typescript_project_tsx_files(self):
        """tsconfig nahi but .tsx files hain."""
        from Lyncus.languages.js_checks import is_typescript_project

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "App.tsx").write_text("export default () => <div/>;")
            assert is_typescript_project(tmpdir) is True

    def test_get_js_tools_filter_deadcode(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(only="deadcode")
        names = [t.name for t in tools]
        assert "depcheck" in names

    def test_get_js_tools_filter_coverage(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(only="coverage")
        names = [t.name for t in tools]
        assert "c8" in names

    def test_get_js_tools_filter_faketests(self):
        from Lyncus.languages.js_checks import get_js_tools

        tools = get_js_tools(only="faketests")
        names = [t.name for t in tools]
        assert "stryker-js" in names

    def test_get_eslint_severity_zero(self):
        """ESLint severity 0 → warning (not error)."""
        from Lyncus.languages.js_checks import get_eslint_severity

        assert get_eslint_severity(0) == "warning"
        assert get_eslint_severity(1) == "warning"
        assert get_eslint_severity(2) == "critical"


# ══════════════════════════════════════════════════════════════════════════════
# java_checks.py — checkstyle aur category mutations
# ══════════════════════════════════════════════════════════════════════════════


class TestJavaChecksExtended:
    """Java checkstyle/category survived mutations kill karne ke liye."""

    def test_checkstyle_category_all_keys(self):
        from Lyncus.languages.java_checks import _checkstyle_category

        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.design.Foo") == "QUALITY"
        )
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.coding.Foo") == "QUALITY"
        )
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.imports.Foo") == "IMPORTS"
        )
        assert _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.naming.Foo") == "NAMING"
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.whitespace.Foo") == "STYLE"
        )
        assert _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.blocks.Foo") == "STYLE"
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.javadoc.Foo")
            == "DOCSTRING"
        )
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.metrics.Foo")
            == "COMPLEXITY"
        )
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.regexp.Foo") == "QUALITY"
        )
        assert (
            _checkstyle_category("com.puppycrawl.tools.checkstyle.checks.sizes.Foo") == "COMPLEXITY"
        )

    def test_checkstyle_category_unknown_returns_style(self):
        from Lyncus.languages.java_checks import _checkstyle_category

        assert _checkstyle_category("com.example.unknown.Check") == "STYLE"
        assert _checkstyle_category("") == "STYLE"

    def test_parse_checkstyle_xml_multiple_files(self):
        """Kaafi files ke saath parsing."""
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<checkstyle>
  <file name="src/A.java">
    <error line="1" column="5" severity="error" message="err1"
           source="com.puppycrawl.tools.checkstyle.checks.naming.ClassNameCheck"/>
  </file>
  <file name="src/B.java">
    <error line="10" column="1" severity="warning" message="warn1"
           source="com.puppycrawl.tools.checkstyle.checks.whitespace.TabCheck"/>
    <error line="20" column="2" severity="info" message="info1"
           source="com.puppycrawl.tools.checkstyle.checks.javadoc.JavadocCheck"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert len(issues) == 3
        assert issues[0]["category"] == "NAMING"
        assert issues[1]["category"] == "STYLE"
        assert issues[2]["category"] == "DOCSTRING"

    def test_parse_checkstyle_xml_rule_id_from_source(self):
        """rule_id source class se nikalo."""
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<checkstyle>
  <file name="Foo.java">
    <error line="5" severity="warning" message="m"
           source="com.puppycrawl.tools.checkstyle.checks.design.VisibilityModifierCheck"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert issues[0]["rule_id"] == "CS-VisibilityModifierCheck"

    def test_parse_checkstyle_xml_no_source(self):
        """source attribute na ho to rule_id fallback."""
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<checkstyle>
  <file name="Foo.java">
    <error line="5" severity="warning" message="some message"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert issues[0]["rule_id"] == "CS-CS-STYLE"

    def test_parse_checkstyle_xml_severity_info(self):
        """Java severity 'info' → 'info'."""
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<checkstyle>
  <file name="Foo.java">
    <error line="1" severity="info" message="m" source="x.checks.coding.Foo"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert issues[0]["severity"] == "info"

    def test_parse_checkstyle_xml_severity_ignore(self):
        """Java severity 'ignore' → 'info'."""
        from Lyncus.languages.java_checks import parse_checkstyle_xml

        xml = """<checkstyle>
  <file name="Foo.java">
    <error line="2" severity="ignore" message="m" source="x.checks.coding.Foo"/>
  </file>
</checkstyle>"""
        issues = parse_checkstyle_xml(xml)
        assert issues[0]["severity"] == "info"

    def test_java_severity_all_values(self):
        """_java_severity sab known values test karo."""
        from Lyncus.languages.java_checks import _java_severity

        assert _java_severity("error") == "critical"
        assert _java_severity("warning") == "warning"
        assert _java_severity("info") == "info"
        assert _java_severity("ignore") == "info"
        # Unknown → default "warning"
        assert _java_severity("debug") == "warning"

    def test_parse_pmd_xml_ruleset_category_mapping(self):
        """PMD ruleset se category mapping check karo."""
        from Lyncus.languages.java_checks import parse_pmd_xml

        rulesets = {
            "Best Practices": "QUALITY",
            "Code Style": "STYLE",
            "Design": "QUALITY",
            "Documentation": "DOCSTRING",
            "Error Prone": "BUGPRONE",
            "Multithreading": "BUGPRONE",
            "Performance": "PERF",
            "Security": "SECURITY",
            "Unnecessary": "DEADCODE",
        }
        for ruleset, expected_cat in rulesets.items():
            xml = f"""<pmd>
  <file name="X.java">
    <violation beginline="1" begincolumn="1" priority="3"
               rule="SomeRule" ruleset="{ruleset}">msg</violation>
  </file>
</pmd>"""
            issues = parse_pmd_xml(xml)
            assert len(issues) == 1, f"ruleset={ruleset}"
            assert issues[0]["category"] == expected_cat, f"ruleset={ruleset}"

    def test_parse_pmd_xml_unknown_ruleset(self):
        from Lyncus.languages.java_checks import parse_pmd_xml

        xml = """<pmd>
  <file name="X.java">
    <violation beginline="5" begincolumn="1" priority="3"
               rule="R" ruleset="SomethingUnknown">m</violation>
  </file>
</pmd>"""
        issues = parse_pmd_xml(xml)
        assert issues[0]["category"] == "QUALITY"

    def test_detect_build_system_gradle_kts(self):
        """build.gradle.kts se gradle detect ho."""
        from Lyncus.languages.java_checks import detect_build_system

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "build.gradle.kts").write_text("plugins {}")
            assert detect_build_system(tmpdir) == "gradle"

    def test_detect_build_system_gradlew(self):
        """gradlew script se gradle detect ho."""
        from Lyncus.languages.java_checks import detect_build_system

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "gradlew").write_text("#!/bin/bash")
            assert detect_build_system(tmpdir) == "gradle"

    def test_find_java_root_file_input(self):
        """File path dene par parent mein pom.xml dhundna."""
        from Lyncus.languages.java_checks import find_java_root

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pom.xml").write_text("<project/>")
            java_file = Path(tmpdir) / "Main.java"
            java_file.write_text("public class Main {}")
            result = find_java_root(str(java_file))
            assert result == tmpdir

    def test_get_java_tools_gradle_only(self):
        """gradle build system → maven-only tools exclude hon."""
        from Lyncus.languages.java_checks import get_java_tools

        tools = get_java_tools(build_system="gradle")
        for t in tools:
            assert t.build_tool in ("gradle", "any")

    def test_parse_jacoco_xml_zero_total(self):
        """total=0 wale counters skip hon (division by zero nahi)."""
        from Lyncus.languages.java_checks import parse_jacoco_xml

        xml = """<?xml version="1.0"?>
<report name="Empty">
  <counter type="INSTRUCTION" missed="0" covered="0"/>
  <counter type="LINE" missed="10" covered="90"/>
</report>"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml)
            tmp = f.name
        try:
            result = parse_jacoco_xml(tmp)
            # INSTRUCTION total=0 → skip, should be None
            assert result["instruction_coverage"] is None
            # LINE = 90/100 = 90%
            assert abs(result["line_coverage"] - 90.0) < 0.1
        finally:
            os.unlink(tmp)
