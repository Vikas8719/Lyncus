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
    "msan-cpp",            # MemorySanitizer — uninitialized reads (Linux only; macOS partial)
    "tsan-cpp",            # ThreadSanitizer — data races (Linux/macOS, Windows nahi)
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
    "mutant",          # Ruby mutation — POSIX fork required
    "go-mutesting",    # Go mutation — Unix fork required
})

# Mutation tools jo HAR platform pe permanently skip honge — bahut slow hain
# aur fast analysis ke flow ko rok dete hain.
# mutmut   → Python mutation testing — 60+ min, CI mein bhi impractical
# pitest   → Java mutation — Maven build + full test suite = hours
# infection → PHP mutation — composer + PHPUnit overhead
# mutant   → Ruby mutation — extremely slow on all platforms
# go-mutesting → Go mutation — slow + Linux-only
ALWAYS_SKIP_MUTATION_TOOLS: frozenset[str] = frozenset({
    "mutmut",          # Python — bahut slow, --skip-slow se bhi alag permanently off
    "pitest",          # Java — Maven rebuild + full suite = too slow
    "infection",       # PHP — composer + PHPUnit overhead = too slow
    "mutant",          # Ruby — POSIX fork + slow on all platforms
    "go-mutesting",    # Go — slow + Linux-only
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
        ALWAYS_SKIP_MUTATION_TOOLS: har platform pe skip — bahut slow
        CI/CD mein: koi bhi bacha hua tool skip mat karo (GitHub linux runner pe sab chalta hai)
        Linux local: koi bhi tool skip mat karo
        macOS local: sirf LINUX_NATIVE_TOOLS skip karo
        Windows local: LINUX_NATIVE_TOOLS + WINDOWS_INCOMPATIBLE_TOOLS skip karo
    """
    # Permanently skip — har platform, har run mein (too slow for practical use)
    if tool_name in ALWAYS_SKIP_MUTATION_TOOLS:
        return True, f"{tool_name} permanently skipped — too slow for analysis (use --skip-slow=false is not enough)"

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

    # macOS — sirf Linux-native tools skip, lekin tsan-cpp aur compsan-cpp macOS pe bhi chalte hain
    if os_name == "macos":
        # macOS pe ye sanitizers kaam karte hain (Apple LLVM support hai):
        # tsan-cpp: macOS pe supported hai
        # compsan-cpp: macOS pe supported hai (ASan+UBSan)
        # asan-cpp, ubsan-cpp: macOS pe bhi kaam karte hain
        # msan-cpp: macOS pe NAHI (MemorySanitizer Linux-only hai officially)
        _MACOS_UNSUPPORTED = frozenset({"msan-cpp", "msan-rust", "msan-cuda", "asan-cuda", "ubsan-cuda"})
        if tool_name in _MACOS_UNSUPPORTED:
            return True, f"{tool_name} requires Linux (not available on macOS)"
        if tool_name in LINUX_NATIVE_TOOLS and tool_name not in _MACOS_UNSUPPORTED:
            # asan-cpp, ubsan-cpp, tsan-cpp, compsan-cpp — macOS pe chalte hain
            _MACOS_COMPATIBLE_SANITIZERS = frozenset({
                "asan-cpp", "ubsan-cpp", "tsan-cpp", "compsan-cpp",
                "cargo-tarpaulin",  # macOS pe bhi support hai recently
            })
            if tool_name not in _MACOS_COMPATIBLE_SANITIZERS:
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
