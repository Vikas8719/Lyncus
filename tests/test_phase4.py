"""
Phase 4 tests — config loader, SARIF, badge, CLI commands
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# ── CONFIG LOADER TESTS ───────────────────────────────────────────────────────


class TestConfigLoader:
    def test_default_config_values(self):
        from Lyncus.config.config_loader import load_config

        cfg = load_config()
        assert cfg.scan.severity == "all"
        assert cfg.scan.output == "table"
        assert cfg.thresholds.min_coverage == 80.0
        assert cfg.thresholds.max_complexity == 10
        assert cfg.hardcode.check_credentials is True
        assert cfg.tools.skip_unavailable is True

    def test_load_from_toml_file(self):
        from Lyncus.config.config_loader import load_config

        toml_content = """
[Lyncus]
version = "1.0"

[scan]
severity = "critical"
output = "json"
parallel = false

[thresholds]
min_coverage   = 90.0
max_complexity = 5

[ignore]
rules = ["HC001", "HC002"]

[hardcode]
check_credentials   = false
check_magic_numbers = false
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False, encoding="utf-8"
        ) as f:
            f.write(toml_content)
            tmp = f.name

        try:
            cfg = load_config(config_file=tmp)
            assert cfg.scan.severity == "critical"
            assert cfg.scan.output == "json"
            assert cfg.scan.parallel is False
            assert cfg.thresholds.min_coverage == 90.0
            assert cfg.thresholds.max_complexity == 5
            assert "HC001" in cfg.ignore.rules
            assert cfg.hardcode.check_credentials is False
            assert cfg.hardcode.check_magic_numbers is False
        finally:
            os.unlink(tmp)

    def test_load_from_pyproject_toml(self):
        from Lyncus.config.config_loader import load_config

        toml_content = """
[tool.Lyncus.scan]
severity = "warning"
output   = "html"

[tool.Lyncus.thresholds]
min_coverage = 70.0
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text(toml_content, encoding="utf-8")
            cfg = load_config(project_path=tmpdir)
            assert cfg.scan.severity == "warning"
            assert cfg.scan.output == "html"
            assert cfg.thresholds.min_coverage == 70.0

    def test_write_default_config(self):
        from Lyncus.config.config_loader import write_default_config

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "Lyncus.toml")
            write_default_config(out)
            assert Path(out).exists()
            content = Path(out).read_text(encoding="utf-8")
            assert "[Lyncus]" in content
            assert "[scan]" in content
            assert "[thresholds]" in content
            assert "[hardcode]" in content
            assert "[ignore]" in content

    def test_missing_config_returns_defaults(self):
        from Lyncus.config.config_loader import load_config

        cfg = load_config(config_file="/nonexistent/path/Lyncus.toml")
        assert cfg.scan.severity == "all"  # default
        assert cfg.version == "1.0"


# ── SARIF TESTS ───────────────────────────────────────────────────────────────


class TestSarifExporter:
    def _make_problems(self):
        from Lyncus.core.parser import Problem

        return [
            Problem(
                tool="bandit",
                rule_id="B201",
                category="SECURITY",
                severity="critical",
                file="src/auth.py",
                line=42,
                column=5,
                message="Hardcoded password detected",
                suggestion="Use environment variables",
            ),
            Problem(
                tool="ruff",
                rule_id="E501",
                category="STYLE",
                severity="info",
                file="src/utils.py",
                line=88,
                column=120,
                message="Line too long",
            ),
        ]

    def test_sarif_valid_json(self):
        from Lyncus.core.sarif import export_sarif

        problems = self._make_problems()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.sarif")
            export_sarif(problems, tmpdir, "Python", 2.5, out)

            assert Path(out).exists()
            with open(out) as f:
                data = json.load(f)

            assert data["version"] == "2.1.0"
            assert "$schema" in data
            assert len(data["runs"]) == 1

    def test_sarif_has_correct_structure(self):
        from Lyncus.core.sarif import export_sarif

        problems = self._make_problems()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.sarif")
            export_sarif(problems, tmpdir, "Python", 2.5, out)

            with open(out) as f:
                data = json.load(f)

            run = data["runs"][0]
            assert run["tool"]["driver"]["name"] == "Lyncus"
            assert len(run["results"]) == 2
            assert len(run["tool"]["driver"]["rules"]) == 2  # B201 + E501

    def test_sarif_severity_mapping(self):
        from Lyncus.core.sarif import _severity_to_sarif

        assert _severity_to_sarif("critical") == "error"
        assert _severity_to_sarif("warning") == "warning"
        assert _severity_to_sarif("info") == "note"
        assert _severity_to_sarif("unknown") == "warning"

    def test_sarif_fix_included(self):
        from Lyncus.core.parser import Problem
        from Lyncus.core.sarif import export_sarif

        problems = [
            Problem(
                tool="bandit",
                rule_id="B201",
                category="SECURITY",
                severity="critical",
                file="src/auth.py",
                line=10,
                column=0,
                message="Hardcoded password",
                suggestion="Use os.environ['PASSWORD']",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.sarif")
            export_sarif(problems, tmpdir, "Python", 1.0, out)
            with open(out) as f:
                data = json.load(f)
            result = data["runs"][0]["results"][0]
            assert "fixes" in result
            assert "os.environ" in result["fixes"][0]["description"]["text"]

    def test_sarif_empty_problems(self):
        from Lyncus.core.sarif import export_sarif

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "empty.sarif")
            export_sarif([], tmpdir, "Python", 0.1, out)
            with open(out) as f:
                data = json.load(f)
            assert data["runs"][0]["results"] == []


# ── BADGE TESTS ───────────────────────────────────────────────────────────────


class TestBadgeGenerator:
    def test_score_badge_created(self):
        from Lyncus.core.badge import generate_score_badge

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "badge.svg")
            svg = generate_score_badge(87, out)
            assert Path(out).exists()
            assert "<svg" in svg
            assert "87/100" in svg
            assert "good" in svg

    def test_score_badge_colors(self):
        from Lyncus.core.badge import _score_color

        assert _score_color(95) == "#22c55e"  # green
        assert _score_color(80) == "#84cc16"  # light green
        assert _score_color(65) == "#f59e0b"  # yellow
        assert _score_color(45) == "#f97316"  # orange
        assert _score_color(20) == "#ef4444"  # red

    def test_score_badge_labels(self):
        from Lyncus.core.badge import _score_label

        assert _score_label(95) == "excellent"
        assert _score_label(80) == "good"
        assert _score_label(65) == "fair"
        assert _score_label(45) == "poor"
        assert _score_label(20) == "critical"

    def test_problems_badge_clean(self):
        from Lyncus.core.badge import generate_problems_badge

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "issues.svg")
            svg = generate_problems_badge(0, 0, out)
            assert "✅ clean" in svg

    def test_problems_badge_with_issues(self):
        from Lyncus.core.badge import generate_problems_badge

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "issues.svg")
            svg = generate_problems_badge(3, 5, out)
            assert "❌ 3" in svg
            assert "⚠️ 5" in svg

    def test_language_badge_colors(self):
        from Lyncus.core.badge import generate_language_badge

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "py.svg")
            svg = generate_language_badge("python", out)
            assert "#3776ab" in svg  # Python blue
            assert "python" in svg.lower()


# ── CLI INTEGRATION TESTS ─────────────────────────────────────────────────────


class TestCLI:
    def test_init_creates_config(self):
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert Path("Lyncus.toml").exists()
            assert "✅" in result.output

    def test_init_no_overwrite(self):
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("Lyncus.toml").write_text("[Lyncus]\n")
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 1
            assert "already exists" in result.output

    def test_init_force_overwrite(self):
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("Lyncus.toml").write_text("[Lyncus]\n")
            result = runner.invoke(main, ["init", "--force"])
            assert result.exit_code == 0

    def test_badge_command(self):
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["badge", "--score", "75"])
            assert result.exit_code == 0
            assert Path("Lyncus-badge.svg").exists()
            assert "75/100" in Path("Lyncus-badge.svg").read_text(encoding="utf-8")

    def test_version(self):
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_doctor_runs(self):
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--lang", "python"])
        assert result.exit_code == 0


# ── FULL PIPELINE SMOKE TEST ──────────────────────────────────────────────────


class TestFullPipeline:
    def test_scan_python_project_with_hardcode(self):
        """End-to-end: Python project scan karo with hardcoded values."""
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Fake Python project banao — intentionally bad patterns detector test ke liye
            src = Path("src")
            src.mkdir()
            # LYNCUS_TEST_CRED env var se credential lo — hardcode avoid karo
            _test_cred = os.environ.get("LYNCUS_TEST_CRED", "test-credential-value")
            (src / "main.py").write_text(
                f'password = "{_test_cred}"\n'
                'api_url  = "http://localhost:8080/api"\n'
                'DB_PATH  = "/home/user/database.db"\n'
                "\n"
                "def process():\n"
                "    return 42 * 99\n"
            )
            (src / "__init__.py").write_text("")

            result = runner.invoke(
                main,
                [
                    "scan",
                    ".",
                    "--lang",
                    "python",
                    "--output",
                    "json",
                    "--report-file",
                    "out.json",
                    "--fail-on",
                    "never",
                ],
            )

            assert result.exit_code == 0, result.output
            assert Path("out.json").exists()
            with open("out.json") as f:
                report = json.load(f)

            assert report["language"] == "python"
            assert "summary" in report
            assert "problems" in report
            # Hardcoded password + URL + path should be found
            categories = {p["category"] for p in report["problems"]}
            # Actual categories from Lyncus-builtin engine
            assert categories & {
                "HARDCODE",
                "SECURITY",
                "CREDENTIAL",
                "HARDPATH",
                "HARDURL",
            } or any(p["rule_id"].startswith("HC") for p in report["problems"])

    def test_scan_outputs_all_formats(self):
        """--output all se sab files ban ne chahiye."""
        from click.testing import CliRunner

        from Lyncus.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("hello.py").write_text('x = "test"\n')

            result = runner.invoke(
                main,
                [
                    "scan",
                    ".",
                    "--lang",
                    "python",
                    "--output",
                    "all",
                    "--fail-on",
                    "never",
                ],
            )

            assert result.exit_code == 0, result.output
            assert Path("Lyncus-report.html").exists()
            assert Path("Lyncus-report.json").exists()
            assert Path("Lyncus-report.sarif").exists()
            assert Path("Lyncus-badge.svg").exists()
