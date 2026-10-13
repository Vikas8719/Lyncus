"""
Lyncus Tests — Phase 1 Core Engine
"""

from Lyncus.core.detector import detect_language
from Lyncus.rules.fake_test_rules import scan_file_for_fake_tests
from Lyncus.rules.hardcode_rules import scan_file_for_hardcode

# ── DETECTOR TESTS ────────────────────────────────────────────────────────────


class TestLanguageDetector:
    def test_python_project_detected(self, tmp_path):
        """Python files wala folder correctly detect ho."""
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "utils.py").write_text("y = 2")
        result = detect_language(str(tmp_path))
        assert result.primary_language == "python"

    def test_rust_project_detected(self, tmp_path):
        """Rust files wala folder correctly detect ho."""
        (tmp_path / "main.rs").write_text("fn main() {}")
        (tmp_path / "Cargo.toml").write_text("[package]")
        result = detect_language(str(tmp_path))
        assert result.primary_language == "rust"

    def test_go_project_detected(self, tmp_path):
        """Go files wala folder correctly detect ho."""
        (tmp_path / "main.go").write_text("package main")
        result = detect_language(str(tmp_path))
        assert result.primary_language == "go"

    def test_cuda_detected_with_cu_files(self, tmp_path):
        """CUDA .cu files wala folder cuda detect kare."""
        (tmp_path / "kernel.cu").write_text("__global__ void kernel() {}")
        result = detect_language(str(tmp_path))
        assert result.has_cuda is True
        assert result.primary_language == "cuda"

    def test_single_file_detection(self, tmp_path):
        """Single file pass karne pe bhi language detect ho."""
        fpath = tmp_path / "script.py"
        fpath.write_text("print('hello')")
        result = detect_language(str(fpath))
        assert result.primary_language == "python"

    def test_unknown_for_empty_folder(self, tmp_path):
        """Empty folder pe unknown return ho."""
        result = detect_language(str(tmp_path))
        assert result.primary_language == "unknown"

    def test_venv_folder_ignored(self, tmp_path):
        """venv folder ke andar files count na ho."""
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "something.js").write_text("// js")
        (tmp_path / "main.py").write_text("x = 1")
        result = detect_language(str(tmp_path))
        assert result.primary_language == "python"
        assert "javascript" not in result.all_languages


# ── HARDCODE RULES TESTS ──────────────────────────────────────────────────────


class TestHardcodeRules:
    def test_hardcoded_password_detected(self):
        """password= wala string pakda jaaye."""
        content = 'db_password = "admin123"'
        matches = scan_file_for_hardcode("test.py", content)
        rule_ids = [m.rule_id for m in matches]
        assert "HC005" in rule_ids or "HC001" in rule_ids

    def test_hardcoded_unix_path_detected(self):
        """/home/user/ wala path pakda jaaye."""
        content = 'data_path = "/home/rahul/Desktop/data.csv"'
        matches = scan_file_for_hardcode("test.py", content)
        assert any(m.rule_id == "HC010" for m in matches)

    def test_hardcoded_windows_path_detected(self):
        """C:\\Users\\ wala path pakda jaaye."""
        content = r'path = "C:\Users\john\Documents\data.csv"'
        matches = scan_file_for_hardcode("test.py", content)
        assert any(m.rule_id == "HC011" for m in matches)

    def test_hardcoded_api_key_detected(self):
        """api_key = '...' pakda jaaye."""
        content = 'api_key = "sk-abcd1234efgh5678"'
        matches = scan_file_for_hardcode("test.py", content)
        assert any(m.rule_id == "HC002" for m in matches)

    def test_hardcoded_localhost_detected(self):
        """localhost URL pakda jaaye."""
        content = 'BASE_URL = "http://localhost:8000/api"'
        matches = scan_file_for_hardcode("test.py", content)
        assert any(m.rule_id == "HC020" for m in matches)

    def test_todo_comment_detected(self):
        """# TODO comment pakda jaaye."""
        content = "# TODO: fix this later\nx = 1"
        matches = scan_file_for_hardcode("test.py", content)
        assert any(m.rule_id == "HC040" for m in matches)

    def test_clean_code_no_matches(self):
        """Clean code mein koi match na ho."""
        content = """
import os
DATA_PATH = os.environ.get("DATA_PATH", "data/")
API_KEY = os.environ["API_KEY"]
"""
        matches = scan_file_for_hardcode("test.py", content)
        # Koi credential ya path match nahi hona chahiye
        cred_matches = [m for m in matches if m.category in ("CREDENTIAL", "HARDPATH")]
        assert len(cred_matches) == 0

    def test_severity_of_credentials_is_critical(self):
        """Credentials ki severity critical honi chahiye."""
        content = 'password = "mypassword123"'
        matches = scan_file_for_hardcode("test.py", content)
        assert any(m.severity == "critical" for m in matches)

    def test_correct_line_number_reported(self):
        """Galat line number na aaye."""
        content = "x = 1\ny = 2\npassword = 'secret'\nz = 3"
        matches = scan_file_for_hardcode("test.py", content)
        pwd_matches = [
            m
            for m in matches
            if "password" in m.description.lower() or m.rule_id in ("HC001", "HC005")
        ]
        # ✅ Fix #12: if-guard hata — match hona CHAHIYE, nahi toh test fail ho
        assert pwd_matches, "password hardcode match nahi hua — HC001/HC005 rule toot gaya"
        assert pwd_matches[0].line == 3


# ── FAKE TEST RULES TESTS ─────────────────────────────────────────────────────


class TestFakeTestRules:
    def test_assert_true_detected(self):
        """assert True pakda jaaye — FT001 rule fire hona chahiye."""
        content = "def test_something():\n    assert True"
        matches = scan_file_for_fake_tests(content, "python")
        ft001_matches = [m for m in matches if m.rule_id == "FT001"]
        assert len(ft001_matches) == 1, (
            f"FT001 exactly ek baar fire hona chahiye, mila: {[m.rule_id for m in matches]}"
        )
        assert ft001_matches[0].line == 2, (
            f"assert True line 2 pe hai, mila: {ft001_matches[0].line}"
        )

    def test_assert_false_detected(self):
        """assert False pakda jaaye — FT002 rule fire hona chahiye."""
        content = "def test_fail():\n    assert False"
        matches = scan_file_for_fake_tests(content, "python")
        ft002_matches = [m for m in matches if m.rule_id == "FT002"]
        assert len(ft002_matches) == 1, (
            f"FT002 exactly ek baar fire hona chahiye, mila: {[m.rule_id for m in matches]}"
        )
        assert ft002_matches[0].severity == "critical", (
            f"FT002 severity 'critical' honi chahiye, mili: '{ft002_matches[0].severity}'"
        )

    def test_assert_not_none_detected(self):
        """assert result is not None pakda jaaye — FT003 rule fire hona chahiye."""
        content = "def test_result():\n    assert result is not None"
        matches = scan_file_for_fake_tests(content, "python")
        ft003_matches = [m for m in matches if m.rule_id == "FT003"]
        assert len(ft003_matches) == 1, (
            f"FT003 exactly ek baar fire hona chahiye, mila: {[m.rule_id for m in matches]}"
        )
        assert "weak" in ft003_matches[0].description.lower() or "none" in ft003_matches[0].description.lower(), (
            f"FT003 description mein weakness mention hona chahiye, mili: '{ft003_matches[0].description}'"
        )

    def test_real_assertion_not_flagged(self):
        """Sahi assert statement flag na ho — zero matches hone chahiye."""
        content = "def test_add():\n    assert add(2, 3) == 5"
        matches = scan_file_for_fake_tests(content, "python")
        assert len(matches) == 0, (
            f"Real assertion flag nahi honi chahiye, mili: {[m.rule_id for m in matches]}"
        )

    def test_java_assert_true_detected(self):
        """Java assertTrue(true) pakda jaaye — FT101 rule fire hona chahiye."""
        content = "assertTrue(true);"
        matches = scan_file_for_fake_tests(content, "java")
        ft101_matches = [m for m in matches if m.rule_id == "FT101"]
        assert len(ft101_matches) == 1, (
            f"FT101 fire hona chahiye Java ke liye, mila: {[m.rule_id for m in matches]}"
        )

    def test_js_expect_true_detected(self):
        """JS expect(true).toBe(true) pakda jaaye — FT201 rule fire hona chahiye."""
        content = "expect(true).toBe(true);"
        matches = scan_file_for_fake_tests(content, "javascript")
        ft201_matches = [m for m in matches if m.rule_id == "FT201"]
        assert len(ft201_matches) == 1, (
            f"FT201 fire hona chahiye JS ke liye, mila: {[m.rule_id for m in matches]}"
        )

    def test_rust_assert_true_detected(self):
        """Rust assert!(true) pakda jaaye — FT401 rule fire hona chahiye."""
        content = "assert!(true);"
        matches = scan_file_for_fake_tests(content, "rust")
        ft401_matches = [m for m in matches if m.rule_id == "FT401"]
        assert len(ft401_matches) == 1, (
            f"FT401 fire hona chahiye Rust ke liye, mila: {[m.rule_id for m in matches]}"
        )

    def test_suggestion_provided(self):
        """Har fake test ke saath non-empty suggestion honi chahiye."""
        content = "def test_x():\n    assert True"
        matches = scan_file_for_fake_tests(content, "python")
        assert matches, "assert True FT001 se pakda nahi gaya — rule toot gaya"
        ft001 = next(m for m in matches if m.rule_id == "FT001")
        assert ft001.suggestion != "", "FT001 suggestion empty hai — fix karo"
        assert len(ft001.suggestion) > 10, (
            f"Suggestion bahut chhota hai: '{ft001.suggestion}'"
        )

    def test_severity_is_critical(self):
        """Sabhi fake test matches ki severity 'critical' honi chahiye."""
        content = "def test_x():\n    assert True"
        matches = scan_file_for_fake_tests(content, "python")
        assert matches, "assert True FT001 se pakda nahi gaya — rule toot gaya"
        for match in matches:
            assert match.severity == "critical", (
                f"Rule {match.rule_id} ki severity '{match.severity}' hai, 'critical' honi chahiye"
            )
