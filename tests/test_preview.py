from Lyncus.core import preview
from Lyncus.core import platform as lyncus_platform


def test_mutation_preview_skips_python_mutmut_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(preview, "_check_python_pkg", lambda _package: True)
    # mutmut ALWAYS_SKIP_MUTATION_TOOLS mein hai — platform check test ke liye temporarily hataao
    monkeypatch.setattr(
        lyncus_platform,
        "ALWAYS_SKIP_MUTATION_TOOLS",
        lyncus_platform.ALWAYS_SKIP_MUTATION_TOOLS - {"mutmut"},
    )

    mutation = preview._build_mutation_info("python", "windows")

    # Specific fields check karo — sirf None check nahin
    assert mutation.tool == "mutmut", f"Expected 'mutmut', got '{mutation.tool}'"
    assert mutation.supported is True, "Python mutation testing supported hona chahiye"
    assert mutation.installed is True, "monkeypatch se installed=True hona chahiye"
    assert mutation.platform_ok is False, "Windows pe mutmut ko skip hona chahiye"
    assert "WSL2" in mutation.wsl_note
    assert mutation.install_cmd == "pip install 'mutmut>=3.0,<4'", (
        f"Unexpected install_cmd: {mutation.install_cmd}"
    )


def test_mutation_preview_reports_unsupported_language() -> None:
    mutation = preview._build_mutation_info("cpp", "linux")

    # Unsupported language ke liye exact values check karo
    assert mutation.supported is False, "C++ mutation testing unsupported hona chahiye"
    assert mutation.tool == "(unsupported)", f"Expected '(unsupported)', got '{mutation.tool}'"
    assert "No mature C++" in mutation.platform_msg, (
        f"Expected 'No mature C++' in platform_msg, got: '{mutation.platform_msg}'"
    )


def test_mutation_preview_reports_windows_limit_and_wsl_hint(monkeypatch) -> None:
    monkeypatch.setattr(preview.shutil, "which", lambda _executable: None)
    # go-mutesting ALWAYS_SKIP_MUTATION_TOOLS mein hai — platform check test ke liye temporarily hataao
    monkeypatch.setattr(
        lyncus_platform,
        "ALWAYS_SKIP_MUTATION_TOOLS",
        lyncus_platform.ALWAYS_SKIP_MUTATION_TOOLS - {"go-mutesting"},
    )

    mutation = preview._build_mutation_info("go", "windows")

    # Go + Windows specific behavior verify karo
    assert mutation.supported is True, "Go mutation testing supported hona chahiye"
    assert mutation.platform_ok is False, "Go mutmut Windows pe platform_ok=False hona chahiye"
    assert "does not run on Windows" in mutation.platform_msg, (
        f"Expected Windows warning in platform_msg, got: '{mutation.platform_msg}'"
    )
    assert "WSL2" in mutation.wsl_note, (
        f"Expected WSL2 hint in wsl_note, got: '{mutation.wsl_note}'"
    )
