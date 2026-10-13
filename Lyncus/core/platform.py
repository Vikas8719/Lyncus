"""
Lyncus/core/platform.py — Platform & CI/CD Detection

Decide karta hai:
  - Current platform: windows / linux / macos
  - CI/CD environment hai ya nahi (GitHub Actions, GitLab, etc.)
  - Kaunse tools is context mein run ho sakte hain

Logic:
  LOCAL WINDOWS  → mutation tools skip (warn karo), linux-only tools skip
  LOCAL LINUX    → sab tools run
  LOCAL MACOS    → linux-only tools skip, mutation tools run
  CI/CD (any OS) → sab tools run — GitHub Actions pe linux-latest hai by default
                   CICD=true env var se force-enable bhi kiya ja sakta hai
"""

from __future__ import annotations

import os
import platform as _platform


# ── PLATFORM DETECTION ────────────────────────────────────────────────────────

def current_os() -> str:
    """'windows' | 'linux' | 'macos' | 'unknown'"""
    s = _platform.system().lower()
    if s == "windows":
        return "windows"
    if s == "linux":
        return "linux"
    if s == "darwin":
        return "macos"
    return "unknown"


def is_windows() -> bool:
    return current_os() == "windows"


def is_linux() -> bool:
    return current_os() == "linux"


def is_macos() -> bool:
    return current_os() == "macos"


# ── CI/CD DETECTION ───────────────────────────────────────────────────────────
#
# Supported CI environments:
#   GitHub Actions   → CI=true, GITHUB_ACTIONS=true
#   GitLab CI        → GITLAB_CI=true
#   CircleCI         → CIRCLECI=true
#   Travis CI        → TRAVIS=true
#   Jenkins          → JENKINS_URL set
#   Bitbucket        → BITBUCKET_BUILD_NUMBER set
#   Azure Pipelines  → TF_BUILD=true
#   AppVeyor         → APPVEYOR=true
#   TeamCity         → TEAMCITY_VERSION set
#   Generic          → CI=true  (most platforms set this)
#   Lyncus override  → LYNCUS_CI=true  (user force-kar sakta hai)

_CI_ENV_VARS = {
    "CI",                    # Generic — almost all CI platforms set this
    "GITHUB_ACTIONS",        # GitHub Actions
    "GITLAB_CI",             # GitLab CI
    "CIRCLECI",              # CircleCI
    "TRAVIS",                # Travis CI
    "JENKINS_URL",           # Jenkins
    "BITBUCKET_BUILD_NUMBER",# Bitbucket Pipelines
    "TF_BUILD",              # Azure Pipelines
    "APPVEYOR",              # AppVeyor
    "TEAMCITY_VERSION",      # TeamCity
    "LYNCUS_CI",             # Lyncus-specific override
}


def is_ci() -> bool:
    """
    CI/CD environment detect karo.

    Returns True if:
      - Koi bhi standard CI env var set hai (non-empty value)
      - Ya LYNCUS_CI=true set hai

    Local developers ke liye:
      - Koi bhi CI var set nahi hoga normally
      - Set karo: $env:LYNCUS_CI="true"  (PowerShell)
                  export LYNCUS_CI=true   (bash)
    """
    return any(os.environ.get(var, "").strip().lower() in ("true", "1", "yes") for var in _CI_ENV_VARS)


def ci_provider() -> str:
    """Konsa CI provider hai — display ke liye."""
    checks = {
        "GITHUB_ACTIONS": "GitHub Actions",
        "GITLAB_CI":      "GitLab CI",
        "CIRCLECI":       "CircleCI",
        "TRAVIS":         "Travis CI",
        "TF_BUILD":       "Azure Pipelines",
        "APPVEYOR":       "AppVeyor",
        "TEAMCITY_VERSION": "TeamCity",
        "JENKINS_URL":    "Jenkins",
        "BITBUCKET_BUILD_NUMBER": "Bitbucket Pipelines",
        "LYNCUS_CI":      "Lyncus CI (manual)",
    }
    for env_var, name in checks.items():
        if os.environ.get(env_var, "").strip():
            return name
    if os.environ.get("CI", "").strip():
        return "CI (generic)"
    return "local"


# ── TOOL RUN POLICY ───────────────────────────────────────────────────────────

# Tools jo sirf Linux pe natively kaam karte hain
# Windows/macOS pe skip karo — UNLESS CI environment hai (GitHub Actions linux-latest)
LINUX_NATIVE_TOOLS: frozenset[str] = frozenset({
    "cargo-tarpaulin",
    "go-mutesting",
    # ── C++ Sanitizers ─────────────────────────────────────────────────────────
    # clang -fsanitize=* Linux pe best results deta hai (full symbolizer support)
    # Windows pe clang-cl ka sanitizer support limited hai
    "asan-cpp",
    "ubsan-cpp",
    "msan-cpp",            # MemorySanitizer — uninitialized reads (valgrind replacement)
    "tsan-cpp",            # ThreadSanitizer — data races
    "compsan-cpp",         # ASan+UBSan combined
    # ── CUDA Sanitizers ────────────────────────────────────────────────────────
    "asan-cuda",
    "ubsan-cuda",
    "msan-cuda",
    "compute-sanitizer",   # NVIDIA — GPU memory errors (Linux/Windows dono, GPU zaroori)
    # ── Rust Sanitizers ────────────────────────────────────────────────────────
    "asan-rust",
    "ubsan-rust",
    "msan-rust",
    "compsan-rust",        # ThreadSanitizer — Linux/macOS only (Windows pe TSan nahi)
})

# Tools jo Windows pe natively nahi chalte (fork-based process model required)
# CI pe theek hai (GitHub Actions linux runner), local Windows pe skip
WINDOWS_INCOMPATIBLE_TOOLS: frozenset[str] = frozenset({
    "mutmut",          # Python mutation — Windows pe slow/broken
    "mutant",          # Ruby mutation — POSIX fork required
    "go-mutesting",    # Go mutation — Unix fork required
})

# Tools jo macOS pe bhi sahi chalte hain (no restriction)
# (ye list WINDOWS_INCOMPATIBLE_TOOLS se bahar hain)
MACOS_COMPATIBLE_MUTATION_TOOLS: frozenset[str] = frozenset({
    "mutmut",          # Python — macOS pe works
    "cargo-mutants",   # Rust — cross-platform
    "stryker",         # JS/TS/C# — cross-platform
    "stryker-js",
    "stryker-ts",
    "pitest",          # Java/Kotlin — JVM-based, cross-platform
    "infection",       # PHP — cross-platform
    "dotnet-stryker",  # C# — cross-platform
})


def should_skip_tool_on_platform(tool_name: str) -> tuple[bool, str]:
    """
    Kya yeh tool current platform pe skip karna chahiye?

    Returns:
        (should_skip: bool, reason: str)

    Logic:
        CI/CD mein: koi bhi tool skip mat karo (GitHub linux runner pe sab chalta hai)
        Linux local: koi bhi tool skip mat karo
        macOS local: sirf LINUX_NATIVE_TOOLS skip karo
        Windows local: LINUX_NATIVE_TOOLS + WINDOWS_INCOMPATIBLE_TOOLS skip karo
    """
    os_name = current_os()

    # Native Windows limitations apply in local runs and on Windows CI alike.
    if os_name == "windows":
        if tool_name in LINUX_NATIVE_TOOLS:
            return True, f"{tool_name} requires Linux — skipped on Windows"
        if tool_name in WINDOWS_INCOMPATIBLE_TOOLS:
            return True, f"{tool_name} does not run natively on Windows"

    # Linux/macOS CI runners can run tools omitted on some local platforms.
    if is_ci():
        return False, ""

    # Linux local — sab run
    if os_name == "linux":
        return False, ""

    # macOS — sirf Linux-native tools skip
    if os_name == "macos":
        if tool_name in LINUX_NATIVE_TOOLS:
            return True, f"{tool_name} requires Linux (not available on macOS)"
        return False, ""

    # Windows local — Linux-native + Windows-incompatible tools skip
    if os_name == "windows":
        if tool_name in LINUX_NATIVE_TOOLS:
            return True, f"{tool_name} requires Linux — use CI/CD or WSL2"
        if tool_name in WINDOWS_INCOMPATIBLE_TOOLS:
            return True, (
                f"{tool_name} does not run natively on Windows — "
                f"skipped locally (will run in CI/CD on Linux)"
            )
        return False, ""

    return False, ""


def get_platform_summary() -> dict[str, str]:
    """Display ke liye platform info dict."""
    return {
        "os":       current_os(),
        "ci":       str(is_ci()),
        "provider": ci_provider(),
        "system":   _platform.system(),
        "machine":  _platform.machine(),
    }
