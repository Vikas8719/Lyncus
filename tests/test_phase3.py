"""
Phase 3 integration tests — C++, C#, Java, Ruby, PHP, CUDA
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# ── C++ PARSER TESTS ──────────────────────────────────────────────────────────


class TestCppParsers:
    def test_parse_cppcheck_xml_memory_leak(self):
        from Lyncus.languages.cpp_checks import parse_cppcheck_xml

        xml = """<?xml version="1.0" encoding="UTF-8"?>
<results version="2">
<errors>
  <error id="memleak" severity="error" msg="Memory leak: ptr" verbose="Memory not freed at program exit">
    <location file="src/main.cpp" line="42" column="5"/>
  </error>
</errors>
</results>"""
        issues = parse_cppcheck_xml(xml)
        assert len(issues) == 1
        assert issues[0]["severity"] == "critical"
        assert issues[0]["category"] == "MEMORY"
        assert issues[0]["line"] == 42

    def test_parse_cppcheck_xml_skip_missing_include(self):
        from Lyncus.languages.cpp_checks import parse_cppcheck_xml

        xml = """<?xml version="1.0"?>
<results version="2"><errors>
  <error id="missingIncludeSystem" severity="information" msg="Cppcheck cannot find all the include files"/>
</errors></results>"""
        issues = parse_cppcheck_xml(xml)
        assert len(issues) == 0

    def test_parse_clang_tidy_output(self):
        from Lyncus.languages.cpp_checks import parse_clang_tidy_output

        output = (
            "src/main.cpp:10:5: warning: use nullptr instead of NULL "
            "[modernize-use-nullptr]\n"
            "src/main.cpp:20:1: error: use of undeclared identifier 'foo' "
            "[clang-diagnostic-error]\n"
        )
        issues = parse_clang_tidy_output(output)
        assert len(issues) == 2
        assert issues[0]["severity"] == "warning"
        assert issues[1]["severity"] == "critical"

    def test_parse_flawfinder_output(self):
        from Lyncus.languages.cpp_checks import parse_flawfinder_output

        output = (
            "src/auth.cpp:15:  [5] (buffer) strcpy:\n"
            "  Does not check for buffer overflows when copying to destination\n"
        )
        # Simple format match
        issues = parse_flawfinder_output(output)
        # At minimum should return empty list without crashing
        assert isinstance(issues, list)

    def test_find_cpp_files(self):
        from Lyncus.languages.cpp_checks import find_cpp_files

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.cpp").write_text("int main(){}")
            (Path(tmpdir) / "utils.h").write_text("#pragma once")
            (Path(tmpdir) / "build").mkdir()
            (Path(tmpdir) / "build" / "main.o").write_bytes(b"")
            files = find_cpp_files(tmpdir)
            assert any("main.cpp" in f for f in files)
            assert any("utils.h" in f for f in files)


# ── C# PARSER TESTS ───────────────────────────────────────────────────────────


class TestCsharpParsers:
    def test_parse_dotnet_build_warnings(self):
        from Lyncus.languages.csharp_checks import parse_dotnet_build_output

        output = (
            "src\\Program.cs(42,10): warning CS0219: The variable 'x' is assigned "
            "but its value is never used [MyProject.csproj]\n"
            "src\\Auth.cs(10,5): error CS0246: The type or namespace name 'Foo' "
            "could not be found [MyProject.csproj]\n"
        )
        issues = parse_dotnet_build_output(output)
        assert len(issues) == 2
        assert issues[0]["severity"] == "warning"
        assert issues[1]["severity"] == "critical"
        assert "CS0219" in issues[0]["rule_id"]

    def test_parse_stryker_json(self):
        from Lyncus.languages.csharp_checks import parse_stryker_json

        data = {
            "files": {
                "src/Calculator.cs": {
                    "mutants": [
                        {"status": "Killed", "mutatorName": "ArithmeticOperator"},
                        {
                            "status": "Survived",
                            "mutatorName": "ConditionalExpression",
                            "location": {"start": {"line": 10}},
                            "replacement": "!=",
                        },
                        {"status": "Killed", "mutatorName": "StringMutation"},
                    ]
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp = f.name

        try:
            result = parse_stryker_json(tmp)
            assert result["total"] == 3
            assert result["killed"] == 2
            assert result["survived"] == 1
            assert abs(result["mutation_score"] - 66.67) < 0.1
        finally:
            os.unlink(tmp)

    def test_detect_dotnet_project_csproj(self):
        from Lyncus.languages.csharp_checks import detect_dotnet_project

        with tempfile.TemporaryDirectory() as tmpdir:
            csproj = Path(tmpdir) / "MyApp.csproj"
            csproj.write_text("""
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>""")
            result = detect_dotnet_project(tmpdir)
            assert result["type"] == "project"
            assert result["target_framework"] == "net8.0"

    def test_find_csharp_files_excludes_obj(self):
        from Lyncus.languages.csharp_checks import find_csharp_files

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Program.cs").write_text("class P{}")
            obj_dir = Path(tmpdir) / "obj"
            obj_dir.mkdir()
            (obj_dir / "Generated.cs").write_text("// generated")
            files = find_csharp_files(tmpdir)
            assert any("Program.cs" in f for f in files)
            assert not any("Generated.cs" in f for f in files)


# ── RUBY PARSER TESTS ─────────────────────────────────────────────────────────


class TestRubyParsers:
    def test_parse_rubocop_json(self):
        from Lyncus.languages.ruby_checks import parse_rubocop_json

        data = {
            "files": [
                {
                    "path": "app/models/user.rb",
                    "offenses": [
                        {
                            "severity": "convention",
                            "message": "Missing frozen string literal comment.",
                            "cop_name": "Style/FrozenStringLiteralComment",
                            "location": {"start_line": 1, "start_column": 1},
                        },
                        {
                            "severity": "error",
                            "message": "Avoid using `eval`.",
                            "cop_name": "Security/Eval",
                            "location": {"start_line": 42, "start_column": 5},
                        },
                    ],
                }
            ]
        }
        issues = parse_rubocop_json(json.dumps(data))
        assert len(issues) == 2
        assert issues[1]["severity"] == "critical"
        assert issues[1]["category"] == "SECURITY"

    def test_parse_brakeman_json(self):
        from Lyncus.languages.ruby_checks import parse_brakeman_json

        data = {
            "warnings": [
                {
                    "warning_code": 102,
                    "fingerprint": "abc123",
                    "warning_type": "SQL Injection",
                    "confidence": "High",
                    "file": "app/controllers/users_controller.rb",
                    "line": 34,
                    "message": "Possible SQL injection",
                }
            ]
        }
        issues = parse_brakeman_json(json.dumps(data))
        assert len(issues) == 1
        assert issues[0]["severity"] == "critical"
        assert issues[0]["category"] == "SECURITY"

    def test_parse_debride_output(self):
        from Lyncus.languages.ruby_checks import parse_debride_output

        output = """
The following methods may be unused:
  old_helper in app/helpers/user_helper.rb:23
  deprecated_method in lib/utils.rb:78
"""
        issues = parse_debride_output(output)
        assert len(issues) == 2
        assert issues[0]["category"] == "DEADCODE"
        assert issues[0]["line"] == 23

    def test_parse_flog_output(self):
        from Lyncus.languages.ruby_checks import parse_flog_output

        output = """
    76.5: UserController#create in app/controllers/users_controller.rb:10
    15.2: User#validate in app/models/user.rb:5
     8.3: User#save in app/models/user.rb:20
"""
        issues = parse_flog_output(output)
        # Only score >= 25 should appear
        assert len(issues) == 1
        assert issues[0]["severity"] == "critical"  # >= 50 is critical


# ── PHP PARSER TESTS ──────────────────────────────────────────────────────────


class TestPhpParsers:
    def test_parse_phpcs_json(self):
        from Lyncus.languages.php_checks import parse_phpcs_json

        data = {
            "totals": {"errors": 1, "warnings": 1, "fixable": 1},
            "files": {
                "/var/www/src/User.php": {
                    "messages": [
                        {
                            "message": "Missing doc comment for function login()",
                            "source": "Squiz.Commenting.FunctionComment.Missing",
                            "severity": 5,
                            "type": "WARNING",
                            "line": 25,
                            "column": 5,
                            "fixable": False,
                        },
                        {
                            "message": "Expected 1 blank line after function",
                            "source": "PSR2.Methods.FunctionClosingBrace.SpacingBeforeClose",
                            "severity": 5,
                            "type": "ERROR",
                            "line": 40,
                            "column": 1,
                            "fixable": True,
                        },
                    ]
                }
            },
        }
        issues = parse_phpcs_json(json.dumps(data))
        assert len(issues) == 2
        assert issues[1]["severity"] == "critical"

    def test_parse_phpstan_json(self):
        from Lyncus.languages.php_checks import parse_phpstan_json

        data = {
            "totals": {"errors": 1, "file_errors": 1},
            "files": {
                "/var/www/src/Auth.php": {
                    "errors": 1,
                    "messages": [
                        {
                            "message": "Parameter $user of method Auth::login() has invalid type User|null",
                            "line": 15,
                            "ignorable": True,
                        }
                    ],
                }
            },
            "errors": [],
        }
        issues = parse_phpstan_json(json.dumps(data))
        assert len(issues) == 1
        assert issues[0]["category"] == "TYPE"

    def test_parse_composer_audit_json(self):
        from Lyncus.languages.php_checks import parse_composer_audit_json

        data = {
            "advisories": {
                "laravel/framework": [
                    {
                        "advisoryId": "PKSA-xxxx",
                        "packageName": "laravel/framework",
                        "title": "SQL Injection via raw queries",
                        "link": "https://...",
                        "cve": "CVE-2024-9999",
                        "affectedVersions": ">=9.0,<9.52.16",
                    }
                ]
            }
        }
        issues = parse_composer_audit_json(json.dumps(data))
        assert len(issues) == 1
        assert issues[0]["severity"] == "critical"
        assert "CVE-2024-9999" in issues[0]["rule_id"]

    def test_detect_php_project_laravel(self):
        from Lyncus.languages.php_checks import detect_php_project

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "artisan").write_text("#!/usr/bin/env php")
            (Path(tmpdir) / "composer.json").write_text(
                json.dumps({"require": {"php": "^8.2", "laravel/framework": "^11.0"}})
            )
            result = detect_php_project(tmpdir)
            assert result["framework"] == "laravel"
            assert result["has_composer"] is True
            assert "8.2" in result["php_version"]


# ── CUDA PARSER TESTS ─────────────────────────────────────────────────────────


class TestCudaParsers:
    def test_parse_nvcc_warnings(self):
        from Lyncus.languages.cuda_checks import parse_nvcc_warnings

        output = (
            "kernel.cu(50): warning: variable 'temp' is used before it is initialized\n"
            "kernel.cu(80): error: identifier 'blockDim' is undefined\n"
        )
        issues = parse_nvcc_warnings(output)
        assert len(issues) == 2
        assert issues[0]["severity"] == "warning"
        assert issues[1]["severity"] == "critical"

    def test_analyze_cuda_patterns_block_size(self):
        from Lyncus.languages.cuda_checks import analyze_cuda_patterns

        code = """
__global__ void myKernel(float* data) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    data[idx] *= 2.0f;
}

int main() {
    myKernel<<<100, 2048>>>(d_data);  // Block size 2048 > 1024 limit!
    return 0;
}
"""
        issues = analyze_cuda_patterns(code, "kernel.cu")
        block_issues = [i for i in issues if i["rule_id"] == "CUDA-INVALID-BLOCK-SIZE"]
        assert len(block_issues) == 1
        assert block_issues[0]["severity"] == "critical"

    def test_analyze_cuda_patterns_unchecked_api(self):
        from Lyncus.languages.cuda_checks import analyze_cuda_patterns

        code = """
void setup() {
    float* d_data;
    cudaMalloc((void**)&d_data, 1024 * sizeof(float));  // No error check!
    cudaMemcpy(d_data, h_data, size, cudaMemcpyHostToDevice);
}
"""
        issues = analyze_cuda_patterns(code, "setup.cu")
        unchecked = [i for i in issues if i["rule_id"] == "CUDA-UNCHECKED-API"]
        assert len(unchecked) >= 1

    def test_find_cuda_files(self):
        from Lyncus.languages.cuda_checks import find_cuda_files

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "kernel.cu").write_text("__global__ void k(){}")
            (Path(tmpdir) / "defs.cuh").write_text("#pragma once")
            build_dir = Path(tmpdir) / "build"
            build_dir.mkdir()
            (build_dir / "kernel.ptx").write_text("")
            files = find_cuda_files(tmpdir)
            assert any("kernel.cu" in f for f in files)
            assert any("defs.cuh" in f for f in files)


# ── INSTALL DEPS TESTS ────────────────────────────────────────────────────────


class TestInstallDeps:
    def test_get_tools_for_language_python(self):
        from Lyncus.core.install_deps import get_tools_for_language

        tools = get_tools_for_language("python")
        names = [t.name for t in tools]
        assert "ruff" in names
        assert "mypy" in names
        assert "bandit" in names

    def test_get_tools_for_language_unknown(self):
        from Lyncus.core.install_deps import get_tools_for_language

        tools = get_tools_for_language("cobol")
        assert tools == []

    def test_pick_install_cmd_pip_is_universal(self):
        from Lyncus.core.install_deps import _pick_install_cmd

        cmd = _pick_install_cmd(["pip install flawfinder"])
        assert cmd == "pip install flawfinder"


# ── HTML REPORTER TESTS ───────────────────────────────────────────────────────


class TestHtmlReporter:
    def test_export_html_report_creates_file(self):
        from Lyncus.core.html_reporter import export_html_report
        from Lyncus.core.parser import Problem

        problems = [
            Problem(
                tool="ruff",
                rule_id="E501",
                category="STYLE",
                severity="warning",
                file="src/main.py",
                line=10,
                column=80,
                message="Line too long",
            ),
            Problem(
                tool="bandit",
                rule_id="B201",
                category="SECURITY",
                severity="critical",
                file="src/auth.py",
                line=42,
                column=0,
                message="Hardcoded password",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.html")
            export_html_report(
                problems=problems,
                project_path="./test-project",
                language="Python",
                tools_used=["ruff", "bandit"],
                scan_time=1.23,
                output_file=out,
            )
            assert Path(out).exists()
            content = Path(out).read_text(encoding="utf-8")
            assert "Lyncus" in content
            assert "CRITICAL" in content
            assert "SECURITY" in content
            assert "filterSeverity" in content  # JS interactive
            assert "score-ring" in content  # Score chart
