"""
Lyncus/core/preview.py — Pre-scan Preview Engine

`lyncus scan .` se pehle user ko dikhata hai:
  - Detected language
  - Kaunse tools chalenge (installed / missing)
  - Mutation testing availability check
  - RapidCheck / Hypothesis auto-runner status
  - Install commands for missing tools
  - Suggested scan command

Design: scan command ke saath --preview flag bhi kaam karta hai,
aur standalone `lyncus preview .` command bhi.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import Lyncus.core.platform as _lyncus_platform
import contextlib

if TYPE_CHECKING:
    from collections.abc import Callable

console = Console()

# Named constants — magic numbers ki jagah
_MAX_MISSING_TOOLS_DISPLAY = 6   # Max missing tools to show in preview
_HYPOTHESIS_EXAMPLES = 1000      # Property testing example count
_RAPIDCHECK_EXAMPLES = 1000      # RapidCheck property testing example count


# ── DATA CLASSES ──────────────────────────────────────────────────────────────

@dataclass
class ToolPreview:
    name: str
    description: str
    check_type: str          # quality / security / mutation / property / coverage
    installed: bool
    install_cmd: str
    will_run: bool = True    # False = skipped (e.g. mutation on Windows)
    skip_reason: str = ""
    auto_create: bool = False  # RapidCheck runner auto-create h


@dataclass
class MutationInfo:
    tool: str                # mutmut / stryker / pitest / cargo-mutants etc.
    supported: bool
    installed: bool
    platform_ok: bool        # False = does not work on current OS natively
    windows_supported: bool = True   # True = works on Windows too
    platform_msg: str = ""
    install_cmd: str = ""
    wsl_note: str = ""       # Shown when tool is blocked on Windows — WSL alternative


@dataclass
class PreviewResult:
    language: str
    project_path: str
    tools: list[ToolPreview] = field(default_factory=list)
    mutation: MutationInfo | None = None
    missing_tools: list[ToolPreview] = field(default_factory=list)
    install_oneliner: str = ""
    scan_command: str = ""


_LANGUAGE_TOOLS: dict[str, list[tuple[str, str, str, str, str]]] = {

    # ── PYTHON ────────────────────────────────────────────────────────────────
    "python": [
        ("ruff",       "Fast linter — PEP8, bugs, unused imports", "quality",  "ruff",       "pip install ruff"),
        ("mypy",       "Static type checker — hallucination catcher","quality", "mypy",       "pip install mypy"),
        ("bandit",     "Security holes — hardcoded secrets, injections","security","bandit",  "pip install bandit"),
        ("vulture",    "Dead code detector — unused functions/vars", "deadcode","vulture",    "pip install vulture"),
        ("pip-audit",  "Dependency CVE scanner",                   "security", "pip-audit",  "pip install pip-audit"),
        ("hypothesis", "Property-based testing — 1000 examples",   "property", "hypothesis", "pip install hypothesis"),
        ("mutmut",     "Mutation testing — test suite strength",    "mutation", "mutmut",     "pip install 'mutmut>=3.0,<4'"),
    ],

    # ── C++ ───────────────────────────────────────────────────────────────────
    "cpp": [
        ("cppcheck",   "Static analysis — bugs, UB, style",        "quality",  "cppcheck",   "apt-get install -y cppcheck / brew install cppcheck / winget install --id Cppcheck.Cppcheck --exact --silent --accept-package-agreements --accept-source-agreements / choco install cppcheck -y"),
        ("clang-tidy", "Clang linter — modernize + core guidelines","quality",  "clang-tidy", "apt-get install -y clang-tidy / brew install llvm / winget install --id LLVM.LLVM --exact --silent --accept-package-agreements --accept-source-agreements / choco install llvm -y"),
        ("flawfinder", "Security holes — buffer overflow, format str","security","flawfinder","pip install flawfinder"),
        ("lizard",     "Complexity analyzer — cyclomatic complexity","quality",  "lizard",     "pip install lizard"),
        ("cpplint",    "Google C++ style checker",                  "quality",  "cpplint",    "pip install cpplint"),
        ("valgrind",   "Memory leaks + errors (Linux only)",        "security", "valgrind",   "apt install valgrind"),
        ("asan-cpp",   "AddressSanitizer — heap/stack/OOB/UAF",    "security", "clang++",    "apt-get install -y clang / brew install llvm"),
        ("ubsan-cpp",  "UndefinedBehaviorSanitizer — signed OVF, null deref", "quality", "clang++", "apt-get install -y clang / brew install llvm"),
        ("compsan-cpp","Combined ASan+UBSan — max runtime coverage","security", "clang++",    "apt-get install -y clang / brew install llvm"),
        ("rapidcheck", "Property-based testing — 1000 examples",   "property", "rapidcheck", "[Lyncus auto-runner will create it]"),
    ],

    # ── CUDA ──────────────────────────────────────────────────────────────────
    "cuda": [
        ("cppcheck",         "CUDA static analysis — bugs + UB",         "quality",  "cppcheck",         "apt-get install -y cppcheck / brew install cppcheck / winget install --id Cppcheck.Cppcheck --exact --silent --accept-package-agreements --accept-source-agreements / choco install cppcheck -y"),
        ("clang-tidy",       "CUDA clang linter",                        "quality",  "clang-tidy",       "apt-get install -y clang-tidy / brew install llvm / winget install --id LLVM.LLVM --exact --silent --accept-package-agreements --accept-source-agreements / choco install llvm -y"),
        ("nvcc",             "NVCC compiler warnings",                   "quality",  "nvcc",             "apt-get install -y nvidia-cuda-toolkit / winget install --id Nvidia.CUDA --exact --silent --accept-package-agreements --accept-source-agreements / choco install cuda -y"),
        ("flawfinder",       "Security holes — C/CUDA code",             "security", "flawfinder",       "pip install flawfinder"),
        ("valgrind",         "Memory analysis — CPU side (Linux only)",  "security", "valgrind",         "apt install valgrind"),
        ("asan-cuda",        "ASan — CUDA host-side memory errors",      "security", "clang++",          "apt-get install -y clang nvidia-cuda-toolkit"),
        ("ubsan-cuda",       "UBSan — CUDA host-side undefined behavior","quality",  "clang++",          "apt-get install -y clang nvidia-cuda-toolkit"),
        ("compute-sanitizer","Compute Sanitizer — GPU memory/race/OOB",  "security", "compute-sanitizer","apt-get install -y nvidia-cuda-toolkit"),
        ("rapidcheck",       "Property-based testing — 1000 examples",  "property", "rapidcheck",       "[Lyncus auto-runner will create it]"),
    ],

    # ── RUST ──────────────────────────────────────────────────────────────────
    "rust": [
        ("cargo",          "Clippy linter — bugs, anti-patterns",      "quality",  "cargo",       "rustup install stable"),
        ("cargo-audit",    "Dependency CVE scanner",                   "security", "cargo-audit", "cargo install cargo-audit"),
        ("cargo-machete",  "Dead dependency detector",                 "deadcode", "cargo-machete","cargo install cargo-machete"),
        ("cargo-geiger",   "Unsafe code counter",                      "security", "cargo-geiger","cargo install cargo-geiger"),
        ("cargo-tarpaulin","Code coverage (Linux only)",               "coverage", "cargo",       "cargo install cargo-tarpaulin"),
        ("asan-rust",      "AddressSanitizer — unsafe Rust memory errors","security","rustup",    "rustup toolchain install nightly"),
        ("ubsan-rust",     "UBSan — Rust arithmetic overflow, null ptr","quality",  "rustup",     "rustup toolchain install nightly"),
        ("compsan-rust",   "ThreadSanitizer — data races unsafe/async", "security", "rustup",     "rustup toolchain install nightly"),
        ("proptest",       "Property-based testing (Cargo.toml)",      "property", "cargo",       "cargo add --dev proptest"),
        ("cargo-mutants",  "Mutation testing",                         "mutation", "cargo-mutants","cargo install cargo-mutants"),
    ],

    # ── GO ────────────────────────────────────────────────────────────────────
    "go": [
        ("go",           "go vet — built-in bug analyzer",            "quality",  "go",           "golang.org se install karo"),
        ("staticcheck",  "Advanced static analysis — bugs + style",   "quality",  "staticcheck",  "go install honnef.co/go/tools/cmd/staticcheck@latest"),
        ("gosec",        "Security holes — SQL injection, crypto",    "security", "gosec",        "go install github.com/securego/gosec/v2/cmd/gosec@latest"),
        ("golangci-lint","Meta linter — 50+ linters ek saath",        "quality",  "golangci-lint","go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"),
        ("deadcode",     "Dead code detector",                        "deadcode", "deadcode",     "go install golang.org/x/tools/cmd/deadcode@latest"),
        ("gopter",       "Property-based testing",                    "property", "gopter",       "go get github.com/leanovate/gopter"),
        ("go-mutesting", "Mutation testing",                          "mutation", "go-mutesting", "go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest"),
    ],

    # ── JAVASCRIPT ────────────────────────────────────────────────────────────
    "javascript": [
        ("eslint",     "JS linter — bugs, style, anti-patterns",     "quality",  "eslint",  "npm install -g eslint"),
        ("npm",        "npm audit — CVE vulnerability scan",         "security", "npm",     "npm (built-in)"),
        ("jshint",     "Hardcoded values + potential errors",        "quality",  "jshint",  "npm install -g jshint"),
        ("fast-check", "Property-based testing — 1000 examples",    "property", "fast-check","npm install --save-dev fast-check"),
        ("stryker",    "Mutation testing",                           "mutation", "stryker", "npm install -g @stryker-mutator/core"),
    ],

    # ── TYPESCRIPT ────────────────────────────────────────────────────────────
    "typescript": [
        ("eslint",     "TS linter — bugs, type issues",             "quality",  "eslint",     "npm install -g eslint"),
        ("tsc",        "TypeScript type checker — strict mode",     "quality",  "tsc",        "npm install -g typescript"),
        ("npm",        "npm audit — CVE vulnerability scan",        "security", "npm",        "npm (built-in)"),
        ("ts-prune",   "Dead code — unused TS exports",            "deadcode", "ts-prune",   "npm install -g ts-prune"),
        ("fast-check", "Property-based testing — 1000 examples",   "property", "fast-check", "npm install --save-dev fast-check"),
        ("stryker",    "Mutation testing",                          "mutation", "stryker",    "npm install -g @stryker-mutator/core"),
    ],

    # ── JAVA ──────────────────────────────────────────────────────────────────
    "java": [
        ("java",       "Java compilation + basic analysis",         "quality",  "java",      "JDK: adoptium.net"),
        ("pmd",        "Static analysis — bugs, dead code",        "quality",  "pmd",       "brew install pmd"),
        ("spotbugs",   "Bytecode bug finder — null ptr, concurrency","quality", "spotbugs",  "Via Maven/Gradle plugin"),
        ("semgrep",    "Security patterns — OWASP top 10",         "security", "semgrep",   "pip install semgrep"),
        ("pitest",     "Mutation testing (Maven plugin)",           "mutation", "mvn",       "pom.xml mein pitest plugin add karo"),
    ],

    # ── KOTLIN ────────────────────────────────────────────────────────────────
    "kotlin": [
        ("detekt",   "Static analysis — bugs, complexity, smells", "quality",  "detekt",  "brew install detekt / Gradle plugin"),
        ("ktlint",   "Kotlin style enforcer",                      "quality",  "ktlint",  "brew install ktlint"),
        ("semgrep",  "Security patterns",                          "security", "semgrep", "pip install semgrep"),
        ("pitest",   "Mutation testing (Gradle plugin)",           "mutation", "mvn",     "build.gradle mein pitest add karo"),
    ],

    # ── C# ────────────────────────────────────────────────────────────────────
    "csharp": [
        ("dotnet",        "Roslyn — compiler + built-in analyzers", "quality",  "dotnet",        "dotnet.microsoft.com"),
        ("roslynator",    "500+ Roslyn quality rules — cross-platform", "quality", "roslynator", "dotnet tool install -g roslynator.dotnet.cli"),
        ("security-scan", "Security holes — .NET specific",         "security", "security-scan", "dotnet tool install -g security-scan"),
        ("semgrep",       "Security patterns — OWASP",              "security", "semgrep",       "pip install semgrep"),
        ("FsCheck",       "Property-based testing",                 "property", "dotnet",        "dotnet add package FsCheck"),
        ("dotnet-stryker","Mutation testing",                       "mutation", "dotnet-stryker","dotnet tool install -g dotnet-stryker"),
    ],

    # ── RUBY ──────────────────────────────────────────────────────────────────
    "ruby": [
        ("rubocop",      "Ruby linter — style, bugs, anti-patterns", "quality",  "rubocop",      "gem install rubocop"),
        ("brakeman",     "Rails security scanner",                   "security", "brakeman",     "gem install brakeman"),
        ("bundle-audit", "Gem CVE vulnerability scanner",            "security", "bundle-audit", "gem install bundler-audit"),
        ("debride",      "Dead code — unused methods",               "deadcode", "debride",      "gem install debride"),
        ("rantly",       "Property-based testing",                   "property", "rantly",       "gem install rantly"),
        ("mutant",       "Mutation testing",                         "mutation", "mutant",       "gem install mutant"),
    ],

    # ── PHP ───────────────────────────────────────────────────────────────────
    "php": [
        ("phpcs",      "PHP CodeSniffer — PSR12 style",             "quality",  "phpcs",    "composer global require squizlabs/php_codesniffer"),
        ("phpstan",    "PHP static analysis — level 8",             "quality",  "phpstan",  "composer require --dev phpstan/phpstan"),
        ("psalm",      "Taint analysis — security holes",           "security", "psalm",    "composer require --dev vimeo/psalm"),
        ("phpmd",      "Mess detector — dead code, complexity",     "deadcode", "phpmd",    "composer require --dev phpmd/phpmd"),
        ("eris",       "Property-based testing",                    "property", "eris",     "composer require --dev giorgiosironi/eris"),
        ("infection",  "Mutation testing",                          "mutation", "infection","composer require --dev infection/infection"),
    ],

    # ── SWIFT ─────────────────────────────────────────────────────────────────
    "swift": [
        ("swiftlint",  "Swift style + lint — bugs, anti-patterns", "quality",  "swiftlint",  "brew install swiftlint"),
        ("swiftformat","Swift code formatter",                     "quality",  "swiftformat","brew install swiftformat"),
        ("periphery",  "Dead code — unused types, functions",      "deadcode", "periphery",  "brew install peripheryapp/periphery/periphery"),
        ("semgrep",    "Security patterns",                        "security", "semgrep",    "pip install semgrep"),
    ],

    # ── DART / FLUTTER ────────────────────────────────────────────────────────
    "dart": [
        ("dart",    "Dart analyzer — bugs, lints, style",          "quality",  "dart",    "dart.dev se Dart SDK install karo"),
        ("flutter", "Flutter analyzer",                            "quality",  "flutter", "flutter.dev se Flutter install karo"),
        ("dcm",     "Dart Code Metrics — complexity, dead code",  "quality",  "dcm",     "dart pub global activate dart_code_metrics"),
        ("semgrep", "Security patterns",                          "security", "semgrep", "pip install semgrep"),
    ],
}


@dataclass
class _MutationSpec:
    tool_name: str
    executable: str
    install_cmd: str
    windows_supported: bool  # True = installs and runs on Windows natively
    windows_note: str = ""   # Shown on Windows when windows_supported=False
    wsl_note: str = ""       # WSL alternative message


_MUTATION_SPECS: dict[str, _MutationSpec] = {
    "python": _MutationSpec(
        tool_name="mutmut",
        executable="mutmut",
        install_cmd="pip install 'mutmut>=3.0,<4'",
        windows_supported=False,
        windows_note="mutmut requires fork support and does not run natively on Windows.",
        wsl_note="Run Lyncus inside WSL2 to use mutmut on Windows.",
    ),
    "cpp": _MutationSpec(
        tool_name="",
        executable="",
        install_cmd="",
        windows_supported=False,
        windows_note="No mature C++ mutation testing tool is available on any platform yet.",
        wsl_note="",
    ),
    "cuda": _MutationSpec(
        tool_name="",
        executable="",
        install_cmd="",
        windows_supported=False,
        windows_note="No mature CUDA mutation testing tool is available on any platform yet.",
        wsl_note="",
    ),
    "rust": _MutationSpec(
        tool_name="cargo-mutants",
        executable="cargo-mutants",
        install_cmd="cargo install cargo-mutants",
        windows_supported=True,  # cargo-mutants works on Windows
    ),
    "go": _MutationSpec(
        tool_name="go-mutesting",
        executable="go-mutesting",
        install_cmd="go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest",
        windows_supported=False,
        windows_note="go-mutesting relies on Unix process forking and does not run on Windows.",
        wsl_note="Use WSL2 to run go-mutesting: install Go inside WSL, then run 'lyncus scan .' from the WSL terminal.",
    ),
    "javascript": _MutationSpec(
        tool_name="stryker",
        executable="stryker",
        install_cmd="npm install -g @stryker-mutator/core",
        windows_supported=True,  # Stryker works on Windows
    ),
    "typescript": _MutationSpec(
        tool_name="stryker",
        executable="stryker",
        install_cmd="npm install -g @stryker-mutator/core",
        windows_supported=True,
    ),
    "java": _MutationSpec(
        tool_name="pitest",
        executable="mvn",
        install_cmd="Add the pitest-maven plugin to your pom.xml",
        windows_supported=True,  # pitest works on Windows via Maven/Gradle
    ),
    "kotlin": _MutationSpec(
        tool_name="pitest",
        executable="mvn",
        install_cmd="Add the pitest plugin to your build.gradle",
        windows_supported=True,
    ),
    "csharp": _MutationSpec(
        tool_name="dotnet-stryker",
        executable="dotnet-stryker",
        install_cmd="dotnet tool install -g dotnet-stryker",
        windows_supported=True,  # dotnet-stryker is Windows-native
    ),
    "ruby": _MutationSpec(
        tool_name="mutant",
        executable="mutant",
        install_cmd="gem install mutant",
        windows_supported=False,
        windows_note="mutant requires a POSIX fork-based process model and does not run on Windows.",
        wsl_note="Use WSL2 to run mutant: install Ruby inside WSL, then run 'lyncus scan .' from the WSL terminal.",
    ),
    "php": _MutationSpec(
        tool_name="infection",
        executable="infection",
        install_cmd="composer require --dev infection/infection",
        windows_supported=True,  # infection works on Windows
    ),
    "swift": _MutationSpec(
        tool_name="",
        executable="",
        install_cmd="",
        windows_supported=False,
        windows_note="No mature mutation testing tool is available for Swift.",
    ),
    "dart": _MutationSpec(
        tool_name="",
        executable="",
        install_cmd="",
        windows_supported=False,
        windows_note="No mature mutation testing tool is available for Dart.",
    ),
}

# Property testing tools — language-specific auto-create support
# Format: tool_name → auto_create (True = Lyncus runner banayega)
_PROPERTY_TEST_AUTO_CREATE: dict[str, bool] = {
    "rapidcheck": True,    # C++/CUDA — Lyncus cpp runner file banayega
    "hypothesis": False,   # Python — pip install se aata hai
    "proptest":   False,   # Rust — Cargo.toml feature
    "gopter":     False,   # Go — go get se
    "fast-check": False,   # JS/TS — npm se
    "FsCheck":    False,   # C# — dotnet add package
    "rantly":     False,   # Ruby — gem install
    "eris":       False,   # PHP — composer
}

# Tools jo Linux-only hain
_LINUX_ONLY_TOOLS: set[str] = {
    "cargo-tarpaulin",
    # Sanitizers — clang -fsanitize=* Linux/macOS pe proper support; Windows pe limited
    "asan-cpp", "ubsan-cpp", "compsan-cpp",
    "asan-cuda", "ubsan-cuda",
    # Rust sanitizers — nightly + x86_64-unknown-linux-gnu target required
    "asan-rust", "ubsan-rust", "compsan-rust",
    # compute-sanitizer GPU pe run karta hai — GPU zaroori, Windows pe bhi kaam karta hai
    # lekin Linux CI mein zyada reliable, isliye yahan rakhte hain
    # RapidCheck: cross-platform (vcpkg/conan/brew/apt sab pe kaam karta hai)
    # isliye _LINUX_ONLY_TOOLS mein NAHI hai
}


# ── PLATFORM DETECTION ────────────────────────────────────────────────────────

def _current_platform() -> str:
    s = platform.system().lower()
    if s == "linux":
        return "linux"
    if s == "darwin":
        return "macos"
    if s == "windows":
        return "windows"
    return "unknown"


def _is_linux() -> bool:
    return _current_platform() == "linux"


def _is_windows() -> bool:
    return _current_platform() == "windows"


# ── RAPIDCHECK AUTO-RUNNER CREATOR ────────────────────────────────────────────

def create_rapidcheck_runner(project_path: str) -> tuple[bool, str]:
    """
    RapidCheck runner file banao project root mein.
    Agar rapidcheck header-only library project mein hai,
    yeh ek minimal runner compile karke chalata hai.
    Returns:
        (success, message)
    """
    rapidcheck_examples = _RAPIDCHECK_EXAMPLES
    # C++ template braces {{ }} mein likhne hain f-string ke andar
    runner_code = (
        f"// lyncus_rapidcheck_runner.cpp\n"
        f"// Auto-generated by Lyncus — DO NOT COMMIT\n"
        f"// RapidCheck property tests runner ({rapidcheck_examples} examples)\n"
        "#include <iostream>\n"
        "#include <cassert>\n"
        "#include <cstdlib>\n"
        "\n"
        "// RapidCheck header detect karo\n"
        "#if __has_include(<rapidcheck.h>)\n"
        "  #include <rapidcheck.h>\n"
        "  #define HAS_RAPIDCHECK 1\n"
        "#elif __has_include(\"rapidcheck.h\")\n"
        "  #include \"rapidcheck.h\"\n"
        "  #define HAS_RAPIDCHECK 1\n"
        "#else\n"
        "  #define HAS_RAPIDCHECK 0\n"
        "#endif\n"
        "\n"
        "int main() {\n"
        "#if HAS_RAPIDCHECK\n"
        f"    // {rapidcheck_examples} examples run karo\n"
        "    rc::detail::TestParams params;\n"
        f"    params.maxSuccess = {rapidcheck_examples};\n"
        "\n"
        "    bool all_passed = true;\n"
        "\n"
        "    // Basic property: identity\n"
        "    auto r1 = rc::check(\"identity property\", []() {\n"
        "        auto x = *rc::gen::arbitrary<int>();\n"
        "        RC_ASSERT(x == x);\n"
        "    }, params);\n"
        "\n"
        "    if (!r1) {\n"
        "        std::cerr << \"[LYNCUS] RapidCheck: identity test FAILED\\n\";\n"
        "        all_passed = false;\n"
        "    }\n"
        "\n"
        "    // Commutative property\n"
        "    auto r2 = rc::check(\"commutative addition\", []() {\n"
        "        auto a = *rc::gen::arbitrary<int>();\n"
        "        auto b = *rc::gen::arbitrary<int>();\n"
        "        RC_ASSERT(a + b == b + a);\n"
        "    }, params);\n"
        "\n"
        "    if (!r2) {\n"
        "        std::cerr << \"[LYNCUS] RapidCheck: commutativity test FAILED\\n\";\n"
        "        all_passed = false;\n"
        "    }\n"
        "\n"
        "    if (all_passed) {\n"
        f"        std::cout << \"[LYNCUS] RapidCheck: 2 properties passed ({rapidcheck_examples} examples each)\\n\";\n"
        "        return 0;\n"
        "    }\n"
        "    return 1;\n"
        "#else\n"
        "    std::cout << \"[LYNCUS] RapidCheck header nahi mila — skip\\n\";\n"
        "    return 0;\n"
        "#endif\n"
        "}\n"
    )
    try:
        runner_path = Path(project_path) / "lyncus_rapidcheck_runner.cpp"
        runner_path.write_text(runner_code, encoding="utf-8")
        return True, str(runner_path)
    except OSError as e:
        return False, f"File create nahi ho saki: {e}"


def cleanup_rapidcheck_runner(project_path: str) -> None:
    """RapidCheck runner files cleanup karo."""
    for fname in ["lyncus_rapidcheck_runner.cpp", "lyncus_rapidcheck_runner",
                  "lyncus_rapidcheck_runner.exe", "lyncus_rapidcheck_runner.o"]:
        p = Path(project_path) / fname
        if p.exists():
            with contextlib.suppress(OSError):
                p.unlink()


# ── TOOL INSTALL CHECKERS — per-tool special cases ───────────────────────────

def _check_rapidcheck_tool(project_path: str, desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    has_header = _find_rapidcheck_header(project_path)
    return ToolPreview(
        name="rapidcheck", description=desc, check_type=check_type,
        installed=has_header, install_cmd=install_cmd,
        auto_create=True, will_run=True,
        skip_reason="" if has_header else "header not found — Lyncus will create an auto-runner",
    )


def _check_hypothesis_tool(desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    installed = _check_python_pkg("hypothesis")
    return ToolPreview(
        name="hypothesis", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else "pip install hypothesis",
    )


def _check_mutmut_tool(desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    installed = _check_python_pkg("mutmut")
    return ToolPreview(
        name="mutmut", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


def _check_proptest_tool(project_path: str, desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    has_cargo = shutil.which("cargo") is not None
    has_proptest = _check_cargo_toml_dep(project_path, "proptest")
    installed = has_cargo and has_proptest
    return ToolPreview(
        name="proptest", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else 'Cargo.toml: proptest = "1" add karo',
    )


def _check_gopter_tool(project_path: str, desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    installed = _check_go_dep(project_path, "gopter")
    return ToolPreview(
        name="gopter", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


def _check_fscheck_tool(project_path: str, desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    installed = shutil.which("dotnet") is not None and _check_dotnet_pkg(project_path, "FsCheck")
    return ToolPreview(
        name="FsCheck", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


def _check_pitest_tool(desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    installed = shutil.which("mvn") is not None or shutil.which("gradle") is not None
    return ToolPreview(
        name="pitest", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


def _check_dotnet_stryker_tool(desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    installed = shutil.which("dotnet-stryker") is not None
    return ToolPreview(
        name="dotnet-stryker", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


def _check_roslynator_tool(desc: str, check_type: str, install_cmd: str) -> ToolPreview:
    """
    roslynator availability — dotnet global tool.
    PATH check pehle, phir `dotnet tool list --global` fallback.
    Cross-platform: Windows / Linux / macOS sab pe kaam karta hai.
    """
    installed = shutil.which("roslynator") is not None
    if not installed:
        # Fallback: dotnet tool list --global
        try:
            import subprocess
            result = subprocess.run(
                ["dotnet", "tool", "list", "--global"],
                capture_output=True, text=True, timeout=10,
            )
            installed = "roslynator.dotnet.cli" in result.stdout.lower()
        except Exception:
            installed = False
    return ToolPreview(
        name="roslynator", description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


def _check_tool_preview(
    name: str,
    desc: str,
    check_type: str,
    executable: str,
    install_cmd: str,
    project_path: str,
) -> ToolPreview:
    """
    Dispatch to special-case checker or fall back to shutil.which.
    Keeps build_preview's main loop lean (complexity C target).
    """
    if name == "rapidcheck":
        return _check_rapidcheck_tool(project_path, desc, check_type, install_cmd)
    if name == "hypothesis":
        return _check_hypothesis_tool(desc, check_type, install_cmd)
    if name == "mutmut":
        return _check_mutmut_tool(desc, check_type, install_cmd)
    if name == "proptest":
        return _check_proptest_tool(project_path, desc, check_type, install_cmd)
    if name == "gopter":
        return _check_gopter_tool(project_path, desc, check_type, install_cmd)
    if name == "FsCheck":
        return _check_fscheck_tool(project_path, desc, check_type, install_cmd)
    if name == "pitest":
        return _check_pitest_tool(desc, check_type, install_cmd)
    if name == "dotnet-stryker":
        return _check_dotnet_stryker_tool(desc, check_type, install_cmd)
    if name == "roslynator":
        return _check_roslynator_tool(desc, check_type, install_cmd)
    # Default: shutil.which
    installed = shutil.which(executable) is not None
    return ToolPreview(
        name=name, description=desc, check_type=check_type,
        installed=installed, install_cmd=install_cmd,
        will_run=installed,
        skip_reason="" if installed else install_cmd,
    )


# ── PREVIEW BUILDER ───────────────────────────────────────────────────────────

def build_preview(language: str, project_path: str) -> PreviewResult:
    """
    Language ke tools ka preview build karo — kya chalega, kya nahi.
    """
    tool_defs = _LANGUAGE_TOOLS.get(language, [])
    plat = _current_platform()
    tools: list[ToolPreview] = []

    for name, desc, check_type, executable, install_cmd in tool_defs:
        # Linux-only tools on Windows
        if name in _LINUX_ONLY_TOOLS and _is_windows():
            tools.append(ToolPreview(
                name=name, description=desc, check_type=check_type,
                installed=False, install_cmd=install_cmd,
                will_run=False, skip_reason="Windows pe supported nahi",
            ))
            continue
        tools.append(
            _check_tool_preview(name, desc, check_type, executable, install_cmd, project_path)
        )

    mutation = _build_mutation_info(language, plat)
    missing = [t for t in tools if not t.installed and t.check_type != "mutation"]
    install_oneliner = _build_install_oneliner(language, missing)

    return PreviewResult(
        language=language,
        project_path=project_path,
        tools=tools,
        mutation=mutation,
        missing_tools=missing,
        install_oneliner=install_oneliner,
        scan_command="Lyncus scan .",
    )


def _find_rapidcheck_header(project_path: str) -> bool:
    """Project, vcpkg, and compiler include paths mein RapidCheck dhundo."""
    root = Path(project_path)
    ignored = {
        ".git", ".venv", "venv", "env", "node_modules", "build", "dist",
        "target", "bin", "obj", "vendor", ".cache", "cache",
    }
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in ignored]
        if "rapidcheck.h" in filenames:
            return True
        if "rapidcheck" in dirnames and (Path(directory) / "rapidcheck" / "rapidcheck.h").is_file():
            return True

    include_roots: list[Path] = []
    vcpkg_root = os.environ.get("VCPKG_ROOT")
    if vcpkg_root:
        include_roots.extend((Path(vcpkg_root) / "installed").glob("*/include"))
    include_roots.extend(Path(path) for path in os.environ.get("INCLUDE", "").split(os.pathsep) if path)
    for include_root in include_roots:
        if (include_root / "rapidcheck.h").is_file() or (
            include_root / "rapidcheck" / "rapidcheck.h"
        ).is_file():
            return True
    return False


def _check_python_pkg(pkg: str) -> bool:
    """Python package installed hai ya nahi check karo."""
    try:
        import importlib.util
        return importlib.util.find_spec(pkg) is not None
    except Exception:
        return False


def _check_cargo_toml_dep(project_path: str, dep: str) -> bool:
    """Cargo.toml mein dependency hai ya nahi check karo."""
    try:
        root = Path(project_path)
        for cargo_toml in root.rglob("Cargo.toml"):
            if "target" in str(cargo_toml):
                continue
            content = cargo_toml.read_text(encoding="utf-8", errors="replace")
            if dep.lower() in content.lower():
                return True
    except OSError:
        pass
    return False


def _check_go_dep(project_path: str, dep: str) -> bool:
    """go.sum / go.mod mein dependency hai ya nahi check karo."""
    try:
        root = Path(project_path)
        for fname in ["go.mod", "go.sum"]:
            for f in root.rglob(fname):
                content = f.read_text(encoding="utf-8", errors="replace")
                if dep.lower() in content.lower():
                    return True
    except OSError:
        pass
    return False


def _check_dotnet_pkg(project_path: str, pkg: str) -> bool:
    """*.csproj mein package reference hai ya nahi check karo."""
    try:
        root = Path(project_path)
        for csproj in root.rglob("*.csproj"):
            content = csproj.read_text(encoding="utf-8", errors="replace")
            if pkg.lower() in content.lower():
                return True
    except OSError:
        pass
    return False


def _build_mutation_info(language: str, plat: str) -> MutationInfo | None:
    """Language ke mutation tool ki info build karo — language-specific."""
    spec = _MUTATION_SPECS.get(language)
    if spec is None:
        return None

    tool_name = spec.tool_name

    # No mutation tool available for this language
    if not tool_name:
        return MutationInfo(
            tool="(unsupported)",
            supported=False,
            installed=False,
            platform_ok=True,
            platform_msg=spec.windows_note,
            install_cmd="",
        )

    # Permanently skipped tools — har platform pe skip
    if tool_name in _lyncus_platform.ALWAYS_SKIP_MUTATION_TOOLS:
        return MutationInfo(
            tool=tool_name,
            supported=True,
            installed=False,
            platform_ok=False,
            windows_supported=False,
            platform_msg=(
                f"{tool_name} permanently skipped — bahut slow hai (60+ min). "
                f"Fast analysis ke liye disable kiya gaya hai."
            ),
            install_cmd=spec.install_cmd,
            wsl_note="",
        )

    # Check installation
    if tool_name == "mutmut":
        installed = _check_python_pkg("mutmut")
    elif tool_name in ("pitest",):
        # Maven/Gradle plugin — mvn/gradle available hai to consider installed
        installed = shutil.which("mvn") is not None or shutil.which("gradle") is not None
    elif tool_name == "cargo-mutants":
        installed = shutil.which("cargo-mutants") is not None
    elif tool_name == "dotnet-stryker":
        # dotnet tool — check via dotnet tools list
        installed = shutil.which("dotnet") is not None
    else:
        installed = shutil.which(spec.executable) is not None

    platform_ok = plat != "windows" or spec.windows_supported
    platform_msg = spec.windows_note if not platform_ok else ""
    wsl_note = spec.wsl_note if not platform_ok else ""

    return MutationInfo(
        tool=tool_name,
        supported=True,
        installed=installed,
        platform_ok=platform_ok,
        windows_supported=spec.windows_supported,
        platform_msg=platform_msg,
        install_cmd=spec.install_cmd,
        wsl_note=wsl_note,
    )


def _get_pip_oneliner(missing: list[ToolPreview]) -> str:
    """Python pip install oneliner."""
    pkgs = [t.name for t in missing if t.install_cmd.startswith("pip install")]
    return f"pip install {' '.join(pkgs)}" if pkgs else ""


def _get_cpp_oneliner(missing: list[ToolPreview]) -> str:
    """C++/CUDA install oneliner — apt pehle, phir pip."""
    apt_tools = [t.name for t in missing if "apt install" in t.install_cmd and t.name != "rapidcheck"]
    if apt_tools:
        return f"sudo apt install {' '.join(apt_tools)}"
    pip_pkgs = [t.name for t in missing if t.install_cmd.startswith("pip install")]
    return f"pip install {' '.join(pip_pkgs)}" if pip_pkgs else ""


def _get_rust_oneliner(missing: list[ToolPreview]) -> str:
    """Rust cargo install oneliner."""
    tools = [t.name for t in missing if t.install_cmd.startswith("cargo install")]
    return f"cargo install {' '.join(tools)}" if tools else ""


def _get_go_oneliner(missing: list[ToolPreview]) -> str:
    """Go install oneliner — ek-ek hi hote hain."""
    go_tools = [t for t in missing if "go install" in t.install_cmd]
    if not go_tools:
        return ""
    return go_tools[0].install_cmd if len(go_tools) == 1 else "# Go tools ek-ek install karo (upar ki list dekho)"


def _get_npm_oneliner(missing: list[ToolPreview]) -> str:
    """JS/TS npm install oneliner."""
    tools = [t.name for t in missing if "npm install" in t.install_cmd and t.name != "fast-check"]
    return f"npm install -g {' '.join(tools)}" if tools else ""


def _get_dotnet_oneliner(missing: list[ToolPreview]) -> str:
    """C# dotnet tool install oneliner."""
    tools = [t.name for t in missing if "dotnet tool install" in t.install_cmd]
    return f"dotnet tool install -g {' '.join(tools)}" if tools else ""


def _get_gem_oneliner(missing: list[ToolPreview]) -> str:
    """Ruby gem install oneliner."""
    gems = [t.name for t in missing if t.install_cmd.startswith("gem install")]
    return f"gem install {' '.join(gems)}" if gems else ""


def _get_brew_oneliner(missing: list[ToolPreview]) -> str:
    """Swift/macOS brew install oneliner."""
    tools = [t.name for t in missing if "brew install" in t.install_cmd]
    return f"brew install {' '.join(tools)}" if tools else ""


# Dispatch table — language → oneliner builder function
_ONELINER_BUILDERS: dict[str, Callable[[list[ToolPreview]], str]] = {
    "python":     _get_pip_oneliner,
    "cpp":        _get_cpp_oneliner,
    "cuda":       _get_cpp_oneliner,
    "rust":       _get_rust_oneliner,
    "go":         _get_go_oneliner,
    "javascript": _get_npm_oneliner,
    "typescript": _get_npm_oneliner,
    "java":       lambda _: "# pom.xml / build.gradle mein plugins add karo (upar ki list dekho)",
    "kotlin":     lambda _: "# pom.xml / build.gradle mein plugins add karo (upar ki list dekho)",
    "csharp":     _get_dotnet_oneliner,
    "ruby":       _get_gem_oneliner,
    "php":        lambda _: "# composer require commands upar dekho",
    "swift":      _get_brew_oneliner,
}


def _build_install_oneliner(language: str, missing: list[ToolPreview]) -> str:
    """
    Missing tools ke liye language-specific install oneliner banao.
    Sirf same package manager ke tools ek saath install hote hain.
    """
    if not missing:
        return ""
    builder = _ONELINER_BUILDERS.get(language)
    if builder is None:
        return ""
    return builder(missing)


# ── PREVIEW PRINTER ───────────────────────────────────────────────────────────

_TYPE_COLORS = {
    "quality":  "cyan",
    "security": "red",
    "mutation": "magenta",
    "property": "yellow",
    "coverage": "blue",
    "deadcode": "dim",
}

_TYPE_ICONS = {
    "quality":  "🔍",
    "security": "🔒",
    "mutation": "🧬",
    "property": "⚡",
    "coverage": "📊",
    "deadcode": "👻",
}


def print_preview(result: PreviewResult, *, interactive: bool = True) -> bool:
    """
    Preview print karo.
    Returns:
        True = user ne scan karna chaha
        False = user ne cancel kiya
    """
    console.print()
    console.print(
        Panel(
            Text("🐺  Lyncus — Project Preview", style="bold white", justify="center"),
            style="bold cyan",
            box=box.DOUBLE,
        )
    )

    # Project info
    console.print(f"\n  [bold]📁 Project  :[/bold] {result.project_path}")
    console.print(f"  [bold]🔍 Language :[/bold] [cyan]{result.language}[/cyan]")
    console.print(f"  [bold]💻 Platform :[/bold] {platform.system()} {platform.machine()}")
    console.print()

    # Tools table
    console.rule("[bold]🛠  Tools that will run in this scan[/bold]")
    console.print()

    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold dim",
        padding=(0, 2),
    )
    table.add_column("Status", width=4)
    table.add_column("Tool", style="bold", width=18)
    table.add_column("Type", width=10)
    table.add_column("Description", width=40)
    table.add_column("Action", style="dim")

    for t in result.tools:
        # Status icon
        if t.installed and t.will_run:
            status = "[green]✅[/green]"
            action = ""
        elif t.auto_create and not t.installed:
            status = "[yellow]🔧[/yellow]"
            action = "[yellow]auto-create[/yellow]"
        elif not t.will_run and t.skip_reason:
            status = "[dim]⏭ [/dim]"
            action = f"[dim]{t.skip_reason}[/dim]"
        else:
            status = "[red]❌[/red]"
            action = f"[dim]{t.install_cmd[:40]}[/dim]"

        type_color = _TYPE_COLORS.get(t.check_type, "white")
        type_icon = _TYPE_ICONS.get(t.check_type, "•")
        type_text = f"[{type_color}]{type_icon} {t.check_type}[/{type_color}]"

        table.add_row(status, t.name, type_text, t.description, action)

    console.print(table)

    # Mutation testing section
    if result.mutation:
        _print_mutation_section(result.mutation)

    # Missing tools install hint
    if result.missing_tools:
        _print_missing_tools_section(result)

    # Scan command
    console.print()
    console.rule("[bold green]▶  Scan Command[/bold green]")
    console.print()
    console.print(f"  [bold green]$[/bold green] [bold white]{result.scan_command}[/bold white]")
    console.print(f"  [dim]For verbose output:[/dim] [dim white]{result.scan_command} --verbose[/dim white]")
    console.print()

    # Interactive prompt
    if not interactive:
        return True

    return _ask_user_to_scan()


def _print_mutation_section(mutation: MutationInfo) -> None:
    """Print mutation testing section — language-specific tool + platform check."""
    console.print()
    console.rule("[bold magenta]🧬  Mutation Testing[/bold magenta]")
    console.print()

    # Unsupported language (Swift, Dart etc.)
    if not mutation.supported:
        console.print(f"  [dim]⚠  {mutation.platform_msg or 'Mutation testing is not supported for this language'}[/dim]")
        return

    tool_status = "[green]✅ installed[/green]" if mutation.installed else "[red]❌ not installed[/red]"
    console.print(f"  [bold]Tool     :[/bold] [magenta]{mutation.tool}[/magenta]  {tool_status}")

    if not mutation.platform_ok:
        console.print(f"  [bold]Platform :[/bold] [yellow]⚠️  {mutation.platform_msg}[/yellow]")
        console.print()
        console.print(
            "  [yellow]⚠  Linux/macOS is recommended for this tool.[/yellow]"
        )
        if mutation.install_cmd:
            console.print(f"  [bold]Install  :[/bold] [dim]{mutation.install_cmd}[/dim]")
        console.print()
        console.print(
            "  [dim]You will be asked during the scan: "
            "[green]y[/green] = run   [red]n[/red] = skip[/dim]"
        )
    elif not mutation.installed:
        if mutation.install_cmd:
            console.print(f"  [bold]Install  :[/bold] [dim]{mutation.install_cmd}[/dim]")
        console.print()
        console.print(
            "  [dim]💡 Install this tool to get a mutation score — "
            "it measures how well your test suite catches bugs[/dim]"
        )
    else:
        console.print(
            "  [dim]✅ Mutation score will be reported — "
            "shows how many mutants were killed vs survived[/dim]"
        )


def _print_missing_tools_section(result: PreviewResult) -> None:
    """Print missing tools section with install commands."""
    console.print()
    console.rule("[bold yellow]📦  Missing Tools — Install Required[/bold yellow]")
    console.print()

    for t in result.missing_tools[:_MAX_MISSING_TOOLS_DISPLAY]:
        console.print(f"  [red]❌[/red]  [bold]{t.name:<18}[/bold] [dim]{t.install_cmd}[/dim]")

    if result.install_oneliner:
        console.print()
        console.print("  [bold]Quick install (one command):[/bold]")
        console.print(f"  [bold green]$[/bold green] [cyan]{result.install_oneliner}[/cyan]")


def _ask_user_to_scan() -> bool:
    """
    Ask the user whether to start the scan.
    Returns True if user wants to scan.
    """
    console.print()
    try:
        console.print(
            "  [bold]Start scan?[/bold]  "
            "[green][Enter][/green] = yes   "
            "[red][Ctrl+C][/red] = no"
        )
        input()
        return True
    except (KeyboardInterrupt, EOFError):
        console.print("\n  [dim]Scan cancelled.[/dim]\n")
        return False


# ── MUTATION PROMPT ───────────────────────────────────────────────────────────

def ask_mutation_platform_prompt(mutation: MutationInfo) -> bool:
    """
    Ask the user whether to run the mutation tool when platform support is limited.

    Returns True = run it, False = skip it
    """
    if mutation.platform_ok:
        return True

    console.print()
    console.print(
        Panel(
            f"[bold yellow]🧬 Mutation Testing — Platform Check[/bold yellow]\n\n"
            f"  Tool    : [magenta]{mutation.tool}[/magenta]\n"
            f"  Issue   : [yellow]{mutation.platform_msg}[/yellow]\n\n"
            f"  Mutation testing is recommended on [bold]Linux[/bold].\n"
            f"  You are on Windows — results may be incomplete or inaccurate.\n\n"
            f"  [green]y[/green] = run anyway (may be slow)\n"
            f"  [red]n[/red] = skip (recommended)",
            style="yellow",
            box=box.ROUNDED,
        )
    )

    try:
        answer = input("  Run mutation testing? [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        console.print("  [dim]Skipped.[/dim]")
        return False
