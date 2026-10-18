"""
Async Tool Runner — System tools ko subprocess se chalata hai.
Phase 3: Language-specific project root detection + full tool registry.
Sab tools parallel run hote hain — speed ke liye.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from Lyncus.core.platform import (
    LINUX_NATIVE_TOOLS as _LINUX_NATIVE_TOOLS,
)
from Lyncus.core.platform import (
    is_ci,
    should_skip_tool_on_platform,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class ToolResult:
    tool_name: str
    language: str
    success: bool
    stdout: str
    stderr: str
    return_code: int
    skipped: bool = False
    skip_reason: str = ""
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None


@dataclass
class ToolConfig:
    name: str
    command: list[str]  # {path} placeholder use karo
    language: str
    check_type: str  # quality / security / deadcode / coverage / faketests / complexity / memory
    available: bool = False
    description: str = ""
    install_cmd: str = ""


@dataclass(frozen=True)
class ToolRunOptions:
    timeout_seconds: int = 300  # 5 min default — WSL/network filesystems slow hote hain
    tool_timeouts: dict[str, int] | None = None



_DEFAULT_TOOL_TIMEOUTS: dict[str, int] = {
    "ruff":       300,
    "bandit":     300,
    "vulture":    300,
    # Type checkers — first run pe stubs download + cache build hota hai
    "mypy":       600,
    # Complexity — bade codebase pe slow
    "radon":      300,
    # Dependency audit — network call bhi kar sakta hai
    "pip-audit":  300,
    # Coverage + tests — slowest legitimate tools
    "pytest-cov": 900,   # 15 min — full test suite + 1000 examples per hypothesis test
    # Property testing — fast tools, bounded by max_success
    # Hypothesis: pytest-cov ke andar chalta hai, alag timeout nahi
    "rapidcheck":      120,   # 1000 examples, < 2 min expected
    "rapidcheck-cuda": 120,
    # Mutation testing — jo abhi bhi run hote hain (fast/cross-platform)
    "cargo-mutants":  3600,  # Rust mutation — fast lekin bade projects pe slow
    "stryker":        1800,  # C# mutation
    "stryker-js":     1800,  # JS mutation
    "stryker-ts":     1800,  # TS mutation
    # Semgrep — pehli run pe rules download karta hai, WSL pe slow filesystem
    "semgrep":        300,   # 5 min — zyada ho to timeout, cache ke baad fast
    # Coverage tools
    "cargo-tarpaulin": 600,
    # Dart / Flutter — pehli run pe pub get + package resolution hoti hai
    # Flutter analyze especially slow hota hai fresh project pe (SDK warm-up ~2min)
    "dart-analyze":   600,   # 10 min — pub resolution + first-run SDK cache
    "flutter-analyze": 600,  # 10 min — Flutter SDK warm-up + pub get
}


_PATH_ARGUMENT = "{path}"
_ALL_GO_PACKAGES = "./..."
_GRADLE_KTS_FILE = "build.gradle.kts"
_MAX_CAPTURE_KB = 512
_MAX_CAPTURE_BYTES_PER_STREAM = _MAX_CAPTURE_KB * 1024
_MAX_CONCURRENT_TOOLS = 4
_CHUNK_READ_KB = 64
_CHUNK_READ_BYTES = _CHUNK_READ_KB * 1024
_OUTPUT_TRUNCATION_MARKER = b"\n...[output truncated]...\n"
_VULTURE_MIN_CONFIDENCE = 70  # Vulture dead code min confidence %
_HYPOTHESIS_MAX_EXAMPLES = 1000  # Property testing example count
_RAPIDCHECK_MAX_SUCCESS = 1000  # RapidCheck successful examples count
_PYTHON_SCAN_EXCLUDES = (
    ".venv,venv,venv-win,venv-linux,venv-mac,env,node_modules,.git,dist,build,__pycache__,*.egg-info,"
    ".mypy_cache,.pytest_cache,.ruff_cache,.hypothesis,.cache,cache,target,"
    "bin,obj,vendor,packages,.gradle,htmlcov,coverage,reports,.tox,.nox,"
    ".eggs,migrations,fixtures,static,media"
)

# mypy --exclude regex pattern (same dirs, regex format)
_MYPY_EXCLUDE_PATTERN = (
    r"(\.venv|venv|venv-win|venv-linux|venv-mac|env|\.git|dist|build|__pycache__|\.mypy_cache|\.pytest_cache"
    r"|\.ruff_cache|\.hypothesis|\.cache|cache|target|bin|obj|vendor|packages"
    r"|\.gradle|htmlcov|coverage|reports|\.tox|\.nox|\.eggs|migrations"
    r"|node_modules|.*\.egg-info)"
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL TOOL REGISTRY — Sab supported languages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_REGISTRY: list[ToolConfig] = [
    # ── PYTHON ────────────────────────────────────────────────────────────────
    ToolConfig(
        "ruff",
        [
            "ruff", "check", _PATH_ARGUMENT,
            "--output-format", "text",
            "--no-cache",
            "--exclude", _PYTHON_SCAN_EXCLUDES,
        ],
        "python",
        "quality",
        description="Fast Python linter",
        install_cmd="pip install ruff",
    ),
    ToolConfig(
        "mypy",
        [
            "mypy",
            _PATH_ARGUMENT,
            "--ignore-missing-imports",
            "--no-error-summary",
            "--show-column-numbers",
            "--exclude", _MYPY_EXCLUDE_PATTERN,
        ],
        "python",
        "quality",
        description="Type checker",
        install_cmd="pip install mypy",
    ),
    ToolConfig(
        "bandit",
        ["bandit", "-r", _PATH_ARGUMENT, "-q", "-x", _PYTHON_SCAN_EXCLUDES],
        "python",
        "security",
        description="Security scanner",
        install_cmd="pip install bandit",
    ),    ToolConfig(
        "vulture",
        [
            "vulture",
            _PATH_ARGUMENT,
            "--min-confidence", str(_VULTURE_MIN_CONFIDENCE),
            "--exclude",
            _PYTHON_SCAN_EXCLUDES,
        ],
        "python",
        "deadcode",
        description="Dead code detector",
        install_cmd="pip install vulture",
    ),
    ToolConfig(
        "radon",
        [
            "radon", "cc", _PATH_ARGUMENT, "-s", "-a", "-nb",
            "--exclude", _PYTHON_SCAN_EXCLUDES,
        ],
        "python",
        "complexity",
        description="Complexity analyzer",
        install_cmd="pip install radon",
    ),
    ToolConfig(
        "pip-audit",
        [
            "pip-audit",
            "--format", "json",
            "--progress-spinner", "off",
            # {pip_audit_target} placeholder — _build_tool_command mein resolve hoga:
            # pyproject.toml milne pe: --requirement=pyproject.toml
            # requirements.txt pe: --requirement=requirements.txt
            # kuch nahi: koi flag nahi (installed env scan, lekin SKIP_DIRS se .venv bahar)
            "{pip_audit_target}",
        ],
        "python",
        "security",
        description="Dependency vulnerability scan",
        install_cmd="pip install pip-audit",
    ),
    ToolConfig(
        "mutmut",
        [sys.executable, "-m", "Lyncus.core.mutmut_runner"],
        "python",
        "faketests",
        description="Mutation testing",
        install_cmd="pip install 'mutmut>=3.0,<4'",
    ),
    # ✅ Fix #11: pytest-cov registry mein add karo — Python coverage missing tha
    # Hypothesis bhi yahi se run hota hai — 1000 examples via hypothesis_profile plugin.
    # LYNCUS_HYPOTHESIS_MAX_EXAMPLES=1000 env se examples count control hota hai.
    ToolConfig(
        "pytest-cov",
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "Lyncus.core.hypothesis_profile",   # 1000-example profile load karo
            f"--cov={_PATH_ARGUMENT}",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=json",
            "-q",
            "--tb=short",                        # Hypothesis failure tracebacks short rakho
            "--ignore=.venv",
            "--ignore=venv",
            "--ignore=env",
            "--ignore=dist",
            "--ignore=build",
            "--ignore=htmlcov",
            "--ignore=migrations",
        ],
        "python",
        "coverage",
        description="Python branch coverage + Hypothesis (1000 examples/test)",
        install_cmd="pip install pytest-cov hypothesis",
    ),
    # hypothesis — property-based testing (Python)
    # pytest-cov ke saath automatically run hota hai via hypothesis_profile plugin.
    # Standalone command nahi — display + availability tracking ke liye sirf.
    # 1000 examples per test: LYNCUS_HYPOTHESIS_MAX_EXAMPLES env se control hota hai.
    ToolConfig(
        "hypothesis",
        [],          # pytest-cov ke sath hi chalata hai — standalone command nahi
        "python",
        "property",
        description="Property-based testing — 1000 random examples per test",
        install_cmd="pip install hypothesis",
    ),
    # ── JAVASCRIPT / TYPESCRIPT ───────────────────────────────────────────────
    ToolConfig(
        "eslint",
        ["npx", "eslint", _PATH_ARGUMENT, "--format", "json", "--ext", ".js,.jsx,.ts,.tsx"],
        "javascript",
        "quality",
        description="JS/TS linter",
        install_cmd="npm install -g eslint",
    ),
    ToolConfig(
        "tsc",
        ["npx", "tsc", "--noEmit", "--strict"],
        "typescript",
        "quality",
        description="TypeScript type checker",
        install_cmd="npm install -g typescript",
    ),
    ToolConfig(
        "npm-audit",
        ["npm", "audit", "--json"],
        "javascript",
        "security",
        description="npm vulnerability scan",
        install_cmd="npm (built-in)",
    ),
    ToolConfig(
        "ts-prune",
        ["npx", "ts-prune"],
        "typescript",
        "deadcode",
        description="Unused TS exports",
        install_cmd="npm install -g ts-prune",
    ),
    ToolConfig(
        "stryker-js",
        ["npx", "stryker", "run", "--reporters", "json", "--jsonReporter.fileName", "{tmpdir}/stryker-report.json"],
        "javascript",
        "faketests",
        description="JavaScript mutation testing",
        install_cmd="npm install -g @stryker-mutator/core",
    ),
    ToolConfig(
        "stryker-ts",
        ["npx", "stryker", "run", "--reporters", "json", "--jsonReporter.fileName", "{tmpdir}/stryker-ts-report.json"],
        "typescript",
        "faketests",
        description="TypeScript mutation testing",
        install_cmd="npm install -g @stryker-mutator/core",
    ),
    # ── RUST ──────────────────────────────────────────────────────────────────
    ToolConfig(
        "cargo-clippy",
        ["cargo", "clippy", "--message-format", "json", "--", "-D", "warnings"],
        "rust",
        "quality",
        description="Rust linter",
        install_cmd="rustup component add clippy",
    ),
    ToolConfig(
        "cargo-audit",
        ["cargo", "audit", "--json"],
        "rust",
        "security",
        description="Dependency CVE check",
        install_cmd="cargo install cargo-audit",
    ),
    ToolConfig(
        "cargo-machete",
        ["cargo", "machete"],
        "rust",
        "deadcode",
        description="Unused dependency detector",
        install_cmd="cargo install cargo-machete",
    ),
    ToolConfig(
        "cargo-tarpaulin",
        ["cargo", "tarpaulin", "--out", "Stdout", "--skip-clean"],
        "rust",
        "coverage",
        description="Code coverage",
        install_cmd="cargo install cargo-tarpaulin",
    ),
    ToolConfig(
        "cargo-mutants",
        ["cargo", "mutants", "--output", "{tmpdir}/mutants_out", "--json"],
        "rust",
        "faketests",
        description="Rust mutation testing",
        install_cmd="cargo install cargo-mutants",
    ),
    # ── RUST SANITIZERS ───────────────────────────────────────────────────────
    # Rust nightly + cargo +nightly required.
    # ASan: unsafe code mein memory errors dhundho.
    # UBSan: arithmetic overflow, null ptr etc. (nightly only).
    # MSan: uninitialized memory reads in unsafe Rust blocks.
    # CSan: Thread sanitizer — data races in unsafe/tokio code.
    ToolConfig(
        "asan-rust",
        [
            "bash", "-c",
            (
                "cd {cwd} && "
                "RUSTFLAGS='-Z sanitizer=address' "
                "cargo +nightly test --target x86_64-unknown-linux-gnu 2>&1 || true"
            ),
        ],
        "rust",
        "security",
        description="AddressSanitizer — unsafe Rust heap/stack/global buffer errors + leaks",
        install_cmd="rustup toolchain install nightly && rustup target add x86_64-unknown-linux-gnu",
    ),
    ToolConfig(
        "ubsan-rust",
        [
            "bash", "-c",
            (
                "cd {cwd} && "
                "RUSTFLAGS='-Z sanitizer=undefined' "
                "cargo +nightly test --target x86_64-unknown-linux-gnu 2>&1 || true"
            ),
        ],
        "rust",
        "quality",
        description="UndefinedBehaviorSanitizer — Rust arithmetic overflow, null ptr, misaligned",
        install_cmd="rustup toolchain install nightly && rustup target add x86_64-unknown-linux-gnu",
    ),
    ToolConfig(
        "msan-rust",
        [
            "bash", "-c",
            (
                "cd {cwd} && "
                "RUSTFLAGS='-Z sanitizer=memory' "
                "cargo +nightly test --target x86_64-unknown-linux-gnu 2>&1 || true"
            ),
        ],
        "rust",
        "security",
        description="MemorySanitizer — uninitialized memory reads in unsafe Rust (valgrind replacement)",
        install_cmd="rustup toolchain install nightly && rustup target add x86_64-unknown-linux-gnu",
    ),
    ToolConfig(
        "compsan-rust",
        [
            "bash", "-c",
            (
                "cd {cwd} && "
                "RUSTFLAGS='-Z sanitizer=thread' "
                "cargo +nightly test --target x86_64-unknown-linux-gnu 2>&1 || true"
            ),
        ],
        "rust",
        "security",
        description="ThreadSanitizer — data races in unsafe/async Rust code",
        install_cmd="rustup toolchain install nightly && rustup target add x86_64-unknown-linux-gnu",
    ),
    # ── GO ────────────────────────────────────────────────────────────────────
    ToolConfig(
        "go-vet",
        ["go", "vet", _ALL_GO_PACKAGES],
        "go",
        "quality",
        description="Go built-in analyzer",
        install_cmd="go (built-in)",
    ),
    ToolConfig(
        "staticcheck",
        ["staticcheck", "-f", "json", _ALL_GO_PACKAGES],
        "go",
        "quality",
        description="Advanced Go static analysis",
        install_cmd="go install honnef.co/go/tools/cmd/staticcheck@latest",
    ),
    ToolConfig(
        "gosec",
        ["gosec", "-fmt", "json", "-out", "/dev/stdout", "-quiet", _ALL_GO_PACKAGES],
        "go",
        "security",
        description="Go security scanner",
        install_cmd="go install github.com/securego/gosec/v2/cmd/gosec@latest",
    ),
    ToolConfig(
        "golangci-lint",
        ["golangci-lint", "run", "--out-format", "json", "--timeout", "120s"],
        "go",
        "quality",
        description="Go meta linter",
        install_cmd="brew install golangci-lint",
    ),
    ToolConfig(
        "deadcode",
        ["deadcode", "-test", _ALL_GO_PACKAGES],
        "go",
        "deadcode",
        description="Go dead code detector",
        install_cmd="go install golang.org/x/tools/cmd/deadcode@latest",
    ),
    ToolConfig(
        "go-mutesting",
        ["go-mutesting", _ALL_GO_PACKAGES],
        "go",
        "faketests",
        description="Go mutation testing",
        install_cmd="go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest",
    ),
    # ── C++ ───────────────────────────────────────────────────────────────────
    ToolConfig(
        "cppcheck",
        [
            "cppcheck",
            "--enable=all",
            "--inconclusive",
            "--xml",
            "--suppress=missingIncludeSystem",
            _PATH_ARGUMENT,
        ],
        "cpp",
        "quality",
        description="C++ static analysis",
        install_cmd=(
            "apt-get install -y cppcheck / brew install cppcheck / "
            "winget install --id Cppcheck.Cppcheck --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install cppcheck -y"
        ),
    ),
    ToolConfig(
        "clang-tidy",
        ["clang-tidy", _PATH_ARGUMENT, "--checks=*", "--", "-std=c++17"],
        "cpp",
        "quality",
        description="Clang-based C++ linter",
        install_cmd=(
            "apt-get install -y clang-tidy / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install llvm -y"
        ),
    ),
    ToolConfig(
        "flawfinder",
        ["flawfinder", "--dataonly", "--quiet", _PATH_ARGUMENT],
        "cpp",
        "security",
        description="C++ security scanner",
        install_cmd="pip install flawfinder",
    ),
    ToolConfig(
        "lizard",
        ["lizard", _PATH_ARGUMENT, "--CCN", "25", "-w"],
        "cpp",
        "complexity",
        description="C++ complexity analyzer",
        install_cmd="pip install lizard",
    ),
    ToolConfig(
        "cpplint",
        [
            "cpplint",
            "--recursive",
            "--filter=-build/include_subdir,-legal/copyright",
            "--exclude=build",
            "--exclude=build/vcpkg_installed",
            "--exclude=vcpkg_installed",
            "--exclude=third_party",
            "--exclude=extern",
            "--exclude=external",
            "--exclude=vendor",
            "--exclude=deps",
            "--exclude=.cache",
            _PATH_ARGUMENT,
        ],
        "cpp",
        "quality",
        description="Google C++ style checker",
        install_cmd="pip install cpplint",
    ),
    # ── RAPIDCHECK — C++ property-based testing ───────────────────────────────
    # Header-only library. Lyncus auto-runner banata hai agar header milta hai.
    # RC_PARAMS env se examples count control hota hai: max_success=1000
    # check_tool_available() mein header detection + auto-runner file check hota hai.
    ToolConfig(
        "rapidcheck",
        [
            "bash", "-c",
            (
                "rc_src={path} && rc_out={tmpdir}/rc_runner_bin && "
                "# Pehle lyncus_rapidcheck_runner.cpp dhundo (auto-generated) \n"
                "rc_runner=$(find \"$(dirname \"$rc_src\")\" -maxdepth 2 "
                "-name 'lyncus_rapidcheck_runner.cpp' 2>/dev/null | head -1) && "
                "if [ -z \"$rc_runner\" ]; then "
                "  echo '[LYNCUS] RapidCheck runner not found — auto-create needed'; exit 0; "
                "fi && "
                "clang++ -std=c++17 -I\"$(dirname \"$rc_runner\")\" "
                "-I/usr/local/include -I/usr/include "
                "\"$rc_runner\" -o \"$rc_out\" -lrapidcheck 2>&1 && "
                "RC_PARAMS=\"max_success=1000\" \"$rc_out\" 2>&1 || "
                "echo '[LYNCUS] RapidCheck: link failed — rapidcheck library not found'"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cpp",
        "property",
        description="Property-based testing — 1000 random examples per property (header-only)",
        install_cmd=(
            "vcpkg install rapidcheck / "
            "conan install rapidcheck/cci.20220327 / "
            "apt-get install -y librapidcheck-dev / "
            "brew install rapidcheck"
        ),
    ),
    # RapidCheck for CUDA — same runner, CUDA project context mein
    ToolConfig(
        "rapidcheck-cuda",
        [
            "bash", "-c",
            (
                "rc_src={path} && rc_out={tmpdir}/rc_cuda_runner_bin && "
                "rc_runner=$(find \"$(dirname \"$rc_src\")\" -maxdepth 2 "
                "-name 'lyncus_rapidcheck_runner.cpp' 2>/dev/null | head -1) && "
                "if [ -z \"$rc_runner\" ]; then "
                "  echo '[LYNCUS] RapidCheck runner not found — auto-create needed'; exit 0; "
                "fi && "
                "clang++ -std=c++17 -I\"$(dirname \"$rc_runner\")\" "
                "-I/usr/local/include -I/usr/include "
                "\"$rc_runner\" -o \"$rc_out\" -lrapidcheck 2>&1 && "
                "RC_PARAMS=\"max_success=1000\" \"$rc_out\" 2>&1 || "
                "echo '[LYNCUS] RapidCheck: link failed — rapidcheck library not found'"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cuda",
        "property",
        description="Property-based testing for CUDA host code — 1000 examples",
        install_cmd=(
            "vcpkg install rapidcheck / "
            "apt-get install -y librapidcheck-dev / "
            "brew install rapidcheck"
        ),
    ),
    ToolConfig(
        "valgrind",
        [],   # REMOVED — ASan+UBSan+MSan use karo; valgrind 10-50x slow hai CI mein
        "cpp",
        "memory",
        description="[DEPRECATED] Valgrind replaced by ASan+UBSan+MSan — faster CI coverage",
        install_cmd="",
    ),
    # ── C++ SANITIZERS ────────────────────────────────────────────────────────
    # Valgrind ki jagah: ASan + UBSan + MSan + TSan
    # Valgrind: 10-50x overhead, CI mein bahut slow, ASan/MSan se duplicate coverage
    # Sanitizer stack: CI-friendly, compile-time instrumentation, accurate stack traces
    #
    # ASan  — heap/stack buffer overflow, use-after-free, heap leaks
    # UBSan — signed overflow, null deref, misaligned access, division by zero
    # MSan  — uninitialized memory reads (valgrind ka primary USP — yahi replace karta hai)
    # TSan  — data races, deadlocks (multi-threaded C++ ke liye)
    # CSan  — ASan+UBSan combined (maximum single-run coverage)
    ToolConfig(
        "asan-cpp",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/asan_cpp_bin && "
                "clang++ -fsanitize=address -fno-omit-frame-pointer -g -O1 "
                "\"$src\" -o \"$out\" 2>&1 && "
                "ASAN_OPTIONS=detect_leaks=1:halt_on_error=0 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cpp",
        "security",
        description="AddressSanitizer — heap/stack/global buffer overflow, use-after-free, leaks",
        install_cmd=(
            "apt-get install -y clang / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent "
            "--accept-package-agreements --accept-source-agreements"
        ),
    ),
    ToolConfig(
        "ubsan-cpp",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/ubsan_cpp_bin && "
                "clang++ -fsanitize=undefined -fno-omit-frame-pointer -g -O1 "
                "\"$src\" -o \"$out\" 2>&1 && "
                "UBSAN_OPTIONS=halt_on_error=0:print_stacktrace=1 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cpp",
        "quality",
        description="UndefinedBehaviorSanitizer — signed overflow, null deref, misaligned access",
        install_cmd=(
            "apt-get install -y clang / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent "
            "--accept-package-agreements --accept-source-agreements"
        ),
    ),
    ToolConfig(
        "msan-cpp",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/msan_cpp_bin && "
                "clang++ -fsanitize=memory -fno-omit-frame-pointer "
                "-fno-optimize-sibling-calls -g -O1 "
                "\"$src\" -o \"$out\" 2>&1 && "
                "MSAN_OPTIONS=halt_on_error=0:print_stats=1 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cpp",
        "security",
        description="MemorySanitizer — uninitialized memory reads (valgrind ka primary feature, 3x faster)",
        install_cmd="apt-get install -y clang / brew install llvm",
    ),
    ToolConfig(
        "tsan-cpp",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/tsan_cpp_bin && "
                "clang++ -fsanitize=thread -fno-omit-frame-pointer -g -O1 "
                "\"$src\" -o \"$out\" 2>&1 && "
                "TSAN_OPTIONS=halt_on_error=0:second_deadlock_stack=1 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cpp",
        "security",
        description="ThreadSanitizer — data races, deadlocks in multi-threaded C++ code",
        install_cmd="apt-get install -y clang / brew install llvm",
    ),
    ToolConfig(
        "compsan-cpp",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/compsan_cpp_bin && "
                "clang++ -fsanitize=address,undefined -fno-omit-frame-pointer -g -O1 "
                "\"$src\" -o \"$out\" 2>&1 && "
                "ASAN_OPTIONS=detect_leaks=1:halt_on_error=0 "
                "UBSAN_OPTIONS=halt_on_error=0:print_stacktrace=1 "
                "\"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cpp",
        "security",
        description="Combined ASan+UBSan — maximum single-run runtime error coverage",
        install_cmd=(
            "apt-get install -y clang / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent "
            "--accept-package-agreements --accept-source-agreements"
        ),
    ),
    # ── CUDA ──────────────────────────────────────────────────────────────────
    ToolConfig(
        "cppcheck-cuda",
        [
            "cppcheck",
            "--enable=all",
            "--inconclusive",
            "--xml",
            "--suppress=missingIncludeSystem",
            "--language=c++",
            _PATH_ARGUMENT,
        ],
        "cuda",
        "quality",
        description="CUDA static analysis",
        install_cmd=(
            "apt-get install -y cppcheck / brew install cppcheck / "
            "winget install --id Cppcheck.Cppcheck --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install cppcheck -y"
        ),
    ),
    ToolConfig(
        "clang-tidy-cuda",
        ["clang-tidy", _PATH_ARGUMENT, "--checks=cuda-*,cppcoreguidelines-*", "--", "-x", "cuda"],
        "cuda",
        "quality",
        description="CUDA clang-tidy",
        install_cmd=(
            "apt-get install -y clang-tidy / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install llvm -y"
        ),
    ),
    ToolConfig(
        "nvcc-warnings",
        [
            "nvcc",
            "-Xcompiler",
            "-Wall,-Wextra",
            "--device-c",
            "-dc",
            _PATH_ARGUMENT,
            "-o",
            "{tmpdir}/Lyncus_cuda.o",
        ],
        "cuda",
        "quality",
        description="NVCC compiler warnings",
        install_cmd=(
            "apt-get install -y nvidia-cuda-toolkit / "
            "winget install --id Nvidia.CUDA --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install cuda -y"
        ),
    ),
    ToolConfig(
        "valgrind-cuda",
        [],   # REMOVED — compute-sanitizer use karo GPU ke liye, MSan CPU ke liye
        "cuda",
        "memory",
        description="[DEPRECATED] Use compute-sanitizer (GPU) + msan-cuda (CPU host) instead",
        install_cmd="",
    ),
    # ── CUDA SANITIZERS ───────────────────────────────────────────────────────
    # CUDA host-side (CPU threads + host memory): ASan / UBSan / MSan / TSan
    # CUDA device-side (GPU memory): compute-sanitizer
    ToolConfig(
        "asan-cuda",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/asan_cuda_host_bin && "
                "clang++ -x cuda --cuda-gpu-arch=sm_75 "
                "-fsanitize=address -fno-omit-frame-pointer -g -O1 "
                "\"$src\" -o \"$out\" -lcuda 2>&1 && "
                "ASAN_OPTIONS=detect_leaks=1:halt_on_error=0 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cuda",
        "security",
        description="AddressSanitizer — CUDA host-side heap/stack errors + leaks",
        install_cmd=(
            "apt-get install -y clang nvidia-cuda-toolkit / "
            "winget install --id Nvidia.CUDA --exact --silent "
            "--accept-package-agreements --accept-source-agreements"
        ),
    ),
    ToolConfig(
        "ubsan-cuda",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/ubsan_cuda_host_bin && "
                "clang++ -x cuda --cuda-gpu-arch=sm_75 "
                "-fsanitize=undefined -fno-omit-frame-pointer -g -O1 "
                "\"$src\" -o \"$out\" -lcuda 2>&1 && "
                "UBSAN_OPTIONS=halt_on_error=0:print_stacktrace=1 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cuda",
        "quality",
        description="UndefinedBehaviorSanitizer — CUDA host-side UB detection",
        install_cmd=(
            "apt-get install -y clang nvidia-cuda-toolkit / "
            "winget install --id Nvidia.CUDA --exact --silent "
            "--accept-package-agreements --accept-source-agreements"
        ),
    ),
    ToolConfig(
        "msan-cuda",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/msan_cuda_host_bin && "
                "clang++ -x cuda --cuda-gpu-arch=sm_75 "
                "-fsanitize=memory -fno-omit-frame-pointer "
                "-fno-optimize-sibling-calls -g -O1 "
                "\"$src\" -o \"$out\" -lcuda 2>&1 && "
                "MSAN_OPTIONS=halt_on_error=0:print_stats=1 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cuda",
        "security",
        description="MemorySanitizer — CUDA host-side uninitialized memory reads (valgrind replacement)",
        install_cmd="apt-get install -y clang nvidia-cuda-toolkit",
    ),
    ToolConfig(
        "compute-sanitizer",
        [
            "bash", "-c",
            (
                "src={path} && out={tmpdir}/compute_san_bin && "
                "nvcc -g -G -lineinfo \"$src\" -o \"$out\" 2>&1 && "
                "compute-sanitizer --tool memcheck --leak-check=full "
                "--error-exitcode 1 \"$out\" 2>&1 || true"
            ).replace("{path}", _PATH_ARGUMENT),
        ],
        "cuda",
        "security",
        description="NVIDIA Compute Sanitizer — GPU memory errors, race conditions, OOB",
        install_cmd=(
            "apt-get install -y nvidia-cuda-toolkit / "
            "winget install --id Nvidia.CUDA --exact --silent "
            "--accept-package-agreements --accept-source-agreements / "
            "choco install cuda -y"
        ),
    ),
    # ── C# ────────────────────────────────────────────────────────────────────
    ToolConfig(
        "dotnet-build",
        ["dotnet", "build", _PATH_ARGUMENT, "--verbosity", "normal", "--nologo"],
        "csharp",
        "quality",
        description="Roslyn compiler + analyzers",
        install_cmd="https://dotnet.microsoft.com/download",
    ),
    ToolConfig(
        "dotnet-format",
        ["dotnet", "format", _PATH_ARGUMENT, "--verify-no-changes"],
        "csharp",
        "quality",
        description="C# formatter check",
        install_cmd="dotnet tool install -g dotnet-format",
    ),
    ToolConfig(
        "security-scan",
        ["dotnet", "tool", "run", "security-scan", _PATH_ARGUMENT],
        "csharp",
        "security",
        description="C# security scanner",
        install_cmd="dotnet tool install -g security-scan",
    ),
    ToolConfig(
        "roslynator",
        [
            "roslynator", "analyze",
            _PATH_ARGUMENT,
            "--output", "{tmpdir}/roslynator_out.xml",
            "--format", "xml",
        ],
        "csharp",
        "quality",
        description="Roslyn-based analyzer — 500+ code quality rules",
        install_cmd="dotnet tool install -g roslynator.dotnet.cli",
    ),
    ToolConfig(
        "stryker",
        ["dotnet", "stryker", "--reporter", "json"],
        "csharp",
        "faketests",
        description="C# mutation testing",
        install_cmd="dotnet tool install -g dotnet-stryker",
    ),
    ToolConfig(
        "semgrep",
        [
            "semgrep", "scan",
            "--config", "p/csharp",
            "--config", "p/secrets",
            "--config", "p/owasp-top-ten",
            "--json",
            "--quiet",
            _PATH_ARGUMENT,
        ],
        "csharp",
        "security",
        description="C# SAST — OWASP rules, hardcoded secrets, injection vulnerabilities",
        install_cmd=(
            "pip install semgrep / "
            "brew install semgrep / "
            "winget install --id Semgrep.Semgrep --exact --silent "
            "--accept-package-agreements --accept-source-agreements"
        ),
    ),
    # ── JAVA ──────────────────────────────────────────────────────────────────
    ToolConfig(
        "checkstyle",
        [
            "java",
            "-jar",
            "{checkstyle_jar}",
            "-c",
            "/google_checks.xml",
            "-f",
            "xml",
            _PATH_ARGUMENT,
        ],
        "java",
        "quality",
        description="Java style checker",
        install_cmd="Download checkstyle jar",
    ),
    ToolConfig(
        "pmd",
        ["pmd", "check", "-d", _PATH_ARGUMENT, "-R", "rulesets/java/quickstart.xml", "-f", "xml"],
        "java",
        "quality",
        description="Java static analysis",
        install_cmd="brew install pmd / download pmd",
    ),
    ToolConfig(
        "spotbugs",
        ["spotbugs", "-textui", "-xml", "-output", "{tmpdir}/spotbugs_out.xml", _PATH_ARGUMENT],
        "java",
        "quality",
        description="Java bytecode analysis",
        install_cmd="Via Maven/Gradle plugin",
    ),
    ToolConfig(
        "pitest",
        ["mvn", "org.pitest:pitest-maven:mutationCoverage", "-DoutputFormats=JSON"],
        "java",
        "faketests",
        description="Java mutation testing",
        install_cmd="pom.xml mein pitest plugin add karo",
    ),
    # ── RUBY ──────────────────────────────────────────────────────────────────
    ToolConfig(
        "rubocop",
        ["rubocop", _PATH_ARGUMENT, "--format", "json", "--no-color"],
        "ruby",
        "quality",
        description="Ruby linter",
        install_cmd="gem install rubocop",
    ),
    ToolConfig(
        "brakeman",
        ["brakeman", _PATH_ARGUMENT, "--format", "json", "--quiet"],
        "ruby",
        "security",
        description="Rails security scanner",
        install_cmd="gem install brakeman",
    ),
    ToolConfig(
        "debride",
        ["debride", _PATH_ARGUMENT],
        "ruby",
        "deadcode",
        description="Ruby dead method detector",
        install_cmd="gem install debride",
    ),
    ToolConfig(
        "bundler-audit",
        ["bundle-audit", "check", "--update"],
        "ruby",
        "security",
        description="Gem vulnerability scanner",
        install_cmd="gem install bundler-audit",
    ),
    ToolConfig(
        "mutant",
        ["mutant", "run", "--include", _PATH_ARGUMENT, "--require", "mutation_spec"],
        "ruby",
        "faketests",
        description="Ruby mutation testing",
        install_cmd="gem install mutant",
    ),
    # ── PHP ───────────────────────────────────────────────────────────────────
    ToolConfig(
        "phpcs",
        ["phpcs", "--standard=PSR12", "--report=json", _PATH_ARGUMENT],
        "php",
        "quality",
        description="PHP CodeSniffer",
        install_cmd="composer global require squizlabs/php_codesniffer",
    ),
    ToolConfig(
        "phpstan",
        [
            "phpstan",
            "analyse",
            _PATH_ARGUMENT,
            "--level",
            "8",
            "--error-format",
            "json",
            "--no-progress",
        ],
        "php",
        "quality",
        description="PHP static analysis",
        install_cmd="composer require --dev phpstan/phpstan",
    ),
    ToolConfig(
        "psalm",
        ["psalm", "--output-format=json", "--no-progress"],
        "php",
        "security",
        description="PHP taint analysis",
        install_cmd="composer require --dev vimeo/psalm",
    ),
    ToolConfig(
        "phpmd",
        ["phpmd", _PATH_ARGUMENT, "json", "cleancode,codesize,naming,unusedcode"],
        "php",
        "quality",
        description="PHP mess detector",
        install_cmd="composer require --dev phpmd/phpmd",
    ),
    ToolConfig(
        "infection",
        ["infection", "--only-covered", "--min-msi=60", "--logger-json", "{tmpdir}/infection.json"],
        "php",
        "faketests",
        description="PHP mutation testing",
        install_cmd="composer require --dev infection/infection",
    ),
    # ── KOTLIN ────────────────────────────────────────────────────────────────
    ToolConfig(
        "detekt",
        ["detekt", "--input", _PATH_ARGUMENT, "--report", "xml:{tmpdir}/detekt_report.xml"],
        "kotlin",
        "quality",
        description="Kotlin static analysis",
        install_cmd="brew install detekt / Gradle plugin",
    ),
    ToolConfig(
        "ktlint",
        [
            "ktlint",
            "--reporter=json,output={tmpdir}/ktlint_report.json",
            f"{_PATH_ARGUMENT}/**/*.kt",
        ],
        "kotlin",
        "quality",
        description="Kotlin style enforcer",
        install_cmd="brew install ktlint",
    ),
    # ── SWIFT ─────────────────────────────────────────────────────────────────
    ToolConfig(
        "swiftlint",
        ["swiftlint", "lint", "--path", _PATH_ARGUMENT, "--reporter", "json", "--quiet"],
        "swift",
        "quality",
        description="Swift style + lint",
        install_cmd="brew install swiftlint",
    ),
    ToolConfig(
        "periphery",
        ["periphery", "scan", "--project", _PATH_ARGUMENT, "--format", "json", "--quiet"],
        "swift",
        "deadcode",
        description="Swift dead code detector",
        install_cmd="brew install peripheryapp/periphery/periphery",
    ),
    # ── DART / FLUTTER ────────────────────────────────────────────────────────
    ToolConfig(
        "dart-analyze",
        ["dart", "analyze", "--format", "machine", _PATH_ARGUMENT],
        "dart",
        "quality",
        description="Dart static analyzer",
        install_cmd="dart.dev se Dart SDK install karo",
    ),
    ToolConfig(
        "flutter-analyze",
        ["flutter", "analyze", "--no-pub", _PATH_ARGUMENT],
        "dart",
        "quality",
        description="Flutter analyzer",
        install_cmd="flutter.dev se Flutter install karo",
    ),
]


_TEST_SCAN_IGNORES = {
    ".git", ".venv", "venv", "venv-win", "venv-linux", "venv-mac", "env",
    "node_modules", "build", "dist",
    "target", "bin", "obj", "vendor", "packages", ".gradle", ".cache",
    "cache", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".hypothesis",
}


def _project_files(root: Path) -> Iterator[Path]:
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _TEST_SCAN_IGNORES]
        for filename in filenames:
            yield Path(directory) / filename


def _project_test_files(root: Path, language: str) -> bool:
    if language == "python":
        return any(
            file.suffix.lower() == ".py"
            and (file.name.startswith("test_") or file.name.endswith("_test.py"))
            for file in _project_files(root)
        )
    if language == "go":
        return any(file.name.endswith("_test.go") for file in _project_files(root))
    if language == "rust":
        for file in _project_files(root):
            if file.suffix.lower() != ".rs":
                continue
            try:
                source = file.read_text(encoding="utf-8", errors="replace")
                if "#[test]" in source or "#[cfg(test)]" in source:
                    return True
            except OSError:
                continue
    if language in {"java", "kotlin", "csharp", "ruby", "php", "swift", "dart"}:
        test_dirs = {
            "java": ("src/test/java", "test"),
            "kotlin": ("src/test/kotlin", "test"),
            "csharp": ("tests", "test"),
            "ruby": ("spec", "test"),
            "php": ("tests", "test"),
            "swift": ("Tests",),
            "dart": ("test",),
        }[language]
        return any((root / directory).is_dir() for directory in test_dirs)
    return False


def _find_ctest_build_dir(root: Path) -> Path | None:
    candidates = [root, root / "build", root / "cmake-build-debug", root / "cmake-build-release"]
    candidates.extend(path.parent for path in _project_files(root) if path.name == "CTestTestfile.cmake")
    for candidate in candidates:
        if (candidate / "CTestTestfile.cmake").is_file():
            return candidate
    return None


def _project_test_tool(language: str, project_path: str) -> ToolConfig | None:
    root = Path(project_path)
    if root.is_file():
        root = root.parent
    if not root.is_dir():
        return None

    if language == "python" and _project_test_files(root, language):
        return next(tool for tool in TOOL_REGISTRY if tool.name == "pytest-cov")

    if language in {"cpp", "cuda"} and _find_ctest_build_dir(root):
        return _ctest_tool(language)

    test_command = _native_test_command(language, root)
    if not test_command:
        return None
    command, description = test_command
    executable = command[0]
    install_commands = {
        "go": "choco install golang -y / brew install go / apt-get install -y golang-go",
        "npm": "choco install nodejs-lts -y / brew install node / apt-get install -y nodejs npm",
        "mvn": "choco install maven -y / brew install maven / apt-get install -y maven",
        "gradle": "choco install gradle -y / brew install gradle / apt-get install -y gradle",
        "dotnet": "choco install dotnet-sdk -y / brew install --cask dotnet-sdk",
        "bundle": "gem install bundler",
        "composer": "choco install composer -y / brew install composer / apt-get install -y composer",
        "cargo": "choco install rustup.install -y / brew install rustup-init / apt-get install -y cargo",
        "dart": "choco install dart-sdk -y / brew install dart / snap install dart --classic",
    }
    return ToolConfig(
        f"{executable}-tests",
        command,
        language,
        "tests",
        description=description,
        install_cmd=install_commands.get(executable, ""),
    )


def _ctest_tool(language: str) -> ToolConfig:
    return ToolConfig(
        "ctest",
        ["ctest", "--test-dir", "{ctest_build_dir}", "--output-on-failure"],
        language,
        "tests",
        description="CMake/CTest project tests",
        install_cmd="choco install cmake -y / brew install cmake / apt-get install -y cmake",
    )


def _native_test_command(language: str, root: Path) -> tuple[list[str], str] | None:
    if language == "rust" and (root / "Cargo.toml").exists() and (
        (root / "tests").is_dir() or _project_test_files(root, "rust")
    ):
        return ["cargo", "test"], "Rust project tests"
    if language == "go" and (root / "go.mod").exists() and _project_test_files(root, "go"):
        return ["go", "test", "./..."], "Go project tests"
    if language in {"javascript", "typescript"}:
        return _manifest_test_command(root / "package.json", "scripts", "test", ["npm", "test"], "npm project tests")
    if language in {"java", "kotlin"}:
        return _jvm_test_command(language, root)
    if language == "csharp" and any(root.glob("*.csproj")) and _project_test_files(root, language):
        return ["dotnet", "test"], ".NET project tests"
    if language == "ruby" and (root / "Gemfile").exists() and (root / "Rakefile").exists() and _project_test_files(root, language):
        return ["bundle", "exec", "rake", "test"], "Ruby project tests"
    if language == "php" and (root / "composer.json").exists() and _project_test_files(root, language):
        return _manifest_test_command(root / "composer.json", "scripts", "test", ["composer", "test"], "Composer project tests")
    if language == "swift" and (root / "Package.swift").exists() and _project_test_files(root, language):
        return ["swift", "test"], "Swift package tests"
    if language == "dart" and (root / "pubspec.yaml").exists() and _project_test_files(root, language):
        return ["dart", "test"], "Dart project tests"
    return None


def _manifest_test_command(
    manifest: Path,
    section: str,
    key: str,
    command: list[str],
    description: str,
) -> tuple[list[str], str] | None:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return (command, description) if (data.get(section) or {}).get(key) else None


def _jvm_test_command(language: str, root: Path) -> tuple[list[str], str] | None:
    has_tests = _project_test_files(root, "kotlin" if language == "kotlin" else "java")
    if not has_tests:
        return None
    if language == "java" and (root / "pom.xml").exists():
        return ["mvn", "test"], "Maven project tests"
    if any((root / name).exists() for name in ("build.gradle", "build.gradle.kts")):
        return ["gradle", "test"], "Gradle project tests"
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LANGUAGE-SPECIFIC PROJECT ROOT DETECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def resolve_project_root(language: str, project_path: str) -> str:
    """
    Language ke hisaab se project root dhundo.
    Kuch tools (cargo, go, mvn) project root pe chalte hain, file pe nahi.
    """
    root_finders = {
        "rust": _find_cargo_root,
        "go": _find_go_root,
        "java": _find_java_root,
        "ruby": _find_gemfile_root,
        "php": _find_composer_root,
        "kotlin": _find_gradle_root,
        "swift": _find_swift_root,
        "dart": _find_pubspec_root,
        "csharp": _find_csproj_root,
    }

    finder = root_finders.get(language)
    if finder:
        found = finder(project_path)
        return found if found else project_path

    return project_path


def _find_cargo_root(path: str) -> str | None:
    p = Path(path)
    search_path = p.parent if p.is_file() else p
    for parent in (search_path, *search_path.parents):
        if (parent / "Cargo.toml").exists():
            return str(parent)
    for f in p.rglob("Cargo.toml"):
        if "target" not in str(f):
            return str(f.parent)
    return None


def _find_go_root(path: str) -> str | None:
    p = Path(path)
    search_path = p.parent if p.is_file() else p
    for parent in (search_path, *search_path.parents):
        if (parent / "go.mod").exists():
            return str(parent)
    for f in p.rglob("go.mod"):
        return str(f.parent)
    return None


def _find_java_root(path: str) -> str | None:
    p = Path(path)
    for marker in ("pom.xml", "build.gradle", _GRADLE_KTS_FILE):
        if (p / marker).exists():
            return str(p)
    for f in p.rglob("pom.xml"):
        if "target" not in str(f):
            return str(f.parent)
    return None


def _find_gemfile_root(path: str) -> str | None:
    p = Path(path)
    if (p / "Gemfile").exists():
        return str(p)
    for f in p.rglob("Gemfile"):
        if "vendor" not in str(f):
            return str(f.parent)
    return None


def _find_composer_root(path: str) -> str | None:
    p = Path(path)
    if (p / "composer.json").exists():
        return str(p)
    for f in p.rglob("composer.json"):
        if "vendor" not in str(f):
            return str(f.parent)
    return None


def _find_gradle_root(path: str) -> str | None:
    p = Path(path)
    for marker in (_GRADLE_KTS_FILE, "build.gradle", "settings.gradle.kts"):
        if (p / marker).exists():
            return str(p)
    for f in p.rglob(_GRADLE_KTS_FILE):
        return str(f.parent)
    return None


def _find_swift_root(path: str) -> str | None:
    p = Path(path)
    if (p / "Package.swift").exists():
        return str(p)
    for f in p.rglob("Package.swift"):
        return str(f.parent)
    return None


def _find_pubspec_root(path: str) -> str | None:
    p = Path(path)
    if (p / "pubspec.yaml").exists():
        return str(p)
    for f in p.rglob("pubspec.yaml"):
        return str(f.parent)
    return None


def _find_csproj_root(path: str) -> str | None:
    p = Path(path)
    for _ in p.glob("*.sln"):
        return str(p)
    for _ in p.glob("*.csproj"):
        return str(p)
    for f in p.rglob("*.csproj"):
        if "obj" not in str(f):
            return str(f.parent)
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL AVAILABILITY CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Tool name → actual executable mapping
_EXECUTABLE_MAP: dict[str, str] = {
    # Python tools — mutmut PATH mein nahi aata pip install ke baad same process mein
    # check_tool_available mein importlib fallback handle karta hai inhe
    # (yahan sirf woh tools jinke liye executable name alag hai)
    "mutmut": "mutmut",   # importlib fallback check_tool_available mein hai
    # Rust
    "cargo-clippy":   "cargo",
    "cargo-audit":    "cargo",
    "cargo-machete":  "cargo",
    "cargo-tarpaulin":"cargo",
    "cargo-mutants":  "cargo-mutants",
    # Go
    "go-vet":         "go",
    "go-test-coverage":"go",
    "deadcode":       "deadcode",
    "go-mutesting":   "go-mutesting",
    # .NET / C#
    "dotnet-build":   "dotnet",
    "dotnet-format":  "dotnet",
    "roslyn-analyzer":"dotnet",
    "roslynator":     "roslynator",   # dotnet tool install -g roslynator.dotnet.cli
    "stryker":        "dotnet",
    "security-scan":  "dotnet",
    "dotnet-stryker": "dotnet-stryker",
    # JS/TS
    "npm-audit":      "npm",
    "ts-prune":       "npx",
    "tsc":            "npx",
    "stryker-js":     "npx",
    "stryker-ts":     "npx",
    # Ruby
    "bundler-audit":  "bundle-audit",
    "mutant":         "mutant",
    # PHP
    "infection":      "infection",
    # CUDA aliases
    "cppcheck-cuda":  "cppcheck",
    "clang-tidy-cuda":"clang-tidy",
    "nvcc-warnings":  "nvcc",
    "valgrind-cuda":  "valgrind",
    # Java/Kotlin
    "pitest":         "mvn",
    # Dart — NOTE: dart-analyze / flutter-analyze / dart-tests ke liye
    # _EXECUTABLE_MAP use NAHI hota; woh check_tool_available mein
    # _DART_FLUTTER_TOOLS → _check_dart_flutter_executable se handle hote hain.
    # Yahan entry nahi rakhi taaki _EXECUTABLE_MAP fallback galat shutil.which
    # se True return na kare jab dart PATH mein nahi hota.
    # ── Sanitizers ── bash script ke andar clang++ call hota hai
    # check_tool_available "bash" ko check karega — jo always available hai on Linux
    # isliye real check clang++ pe map karo
    "asan-cpp":          "clang++",
    "ubsan-cpp":         "clang++",
    "msan-cpp":          "clang++",
    "tsan-cpp":          "clang++",
    "compsan-cpp":       "clang++",
    "asan-cuda":         "clang++",
    "ubsan-cuda":        "clang++",
    "msan-cuda":         "clang++",
    "compute-sanitizer": "compute-sanitizer",
    # Rust sanitizers — nightly rustup check
    "asan-rust":         "rustup",
    "ubsan-rust":        "rustup",
    "msan-rust":         "rustup",
    "compsan-rust":      "rustup",
    # RapidCheck — bash runner, clang++ se compile karta hai
    # check_tool_available mein special header-detection logic hai
    "rapidcheck":        "clang++",
    "rapidcheck-cuda":   "clang++",
}

# Tools jo sirf Linux pe natively kaam karte hain — platform.py se import kiya
# (windows/macos pe skip, CI/CD mein always run)
_LINUX_ONLY_TOOL_NAMES: frozenset[str] = _LINUX_NATIVE_TOOLS


def _is_linux_platform() -> bool:
    """Backward compat alias — use platform.py functions directly jahan possible ho."""
    import platform
    return platform.system().lower() == "linux"


def _which_in_venv(executable: str) -> str | None:
    """
    shutil.which() ka extended version — system PATH ke saath-saath
    active venv, Scripts/bin, aur Linux user-local paths bhi check karta hai.

    Windows pe pip install ke baad tool .venv\\Scripts\\ mein jaata hai
    lekin shutil.which() PATH-only check karta hai — isliye tools skip ho jaate the.

    WSL/Linux pe pip install --user ke baad tool ~/.local/bin/ mein jaata hai
    jo kabhi kabhi PATH mein nahi hota — isliye explicitly check karo.
    """
    import platform as _plat

    # 1. Standard PATH check (sabse pehle — fastest)
    found = shutil.which(executable)
    if found:
        return found

    # 2. Current venv Scripts / bin check (VIRTUAL_ENV ya sys.prefix se)
    venv_root = os.environ.get("VIRTUAL_ENV") or sys.prefix
    candidates: list[Path] = [
        Path(venv_root) / "Scripts" / executable,          # Windows venv
        Path(venv_root) / "Scripts" / f"{executable}.exe", # Windows venv .exe
        Path(venv_root) / "bin" / executable,              # Linux/macOS venv
    ]

    # 3. sys.executable ke directory mein bhi check karo
    # (pip install ke baad same venv/Scripts ya bin mein rehta hai)
    local_scripts = Path(sys.executable).parent
    candidates += [
        local_scripts / executable,
        local_scripts / f"{executable}.exe",
    ]

    # 4. Linux / WSL — pip install --user → ~/.local/bin/
    #    Yeh PATH mein ho bhi sakta hai ya nahi bhi — explicitly check karo
    if _plat.system().lower() in ("linux", "darwin"):
        home = Path.home()
        candidates += [
            home / ".local" / "bin" / executable,
        ]

    # 5. WSL mein system-level pip install → /usr/local/bin/ ya /usr/bin/
    #    shutil.which() PATH se miss kar sakta hai agar PATH incomplete ho
    if _plat.system().lower() == "linux":
        candidates += [
            Path("/usr/local/bin") / executable,
            Path("/usr/bin") / executable,
        ]

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def _dotnet_global_tools_path() -> list[Path]:
    """
    dotnet global tools install directory dhundo — sab platforms ke liye.

    Windows:        %USERPROFILE%\\.dotnet\\tools\\
    Linux / WSL:    ~/.dotnet/tools/
    macOS:          ~/.dotnet/tools/
    Custom DOTNET_ROOT env se bhi override ho sakta hai.

    `dotnet tool install -g` ke baad executable yahan jaata hai.
    Yeh directory PATH mein NAHI hoti by default on fresh Linux/macOS installs
    jab tak user ne ~/.bashrc / ~/.zshrc mein add nahi kiya — isliye
    shutil.which() miss karta hai even though tool installed hai.
    """
    candidates: list[Path] = []

    # 1. DOTNET_ROOT env override (custom dotnet install location)
    dotnet_root = os.environ.get("DOTNET_ROOT", "")
    if dotnet_root:
        candidates.append(Path(dotnet_root) / "tools")

    # 2. Standard user-level dotnet tools path (all platforms)
    home = Path.home()
    candidates.append(home / ".dotnet" / "tools")

    # 3. Windows: %USERPROFILE%\.dotnet\tools (explicit, same as home usually)
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        candidates.append(Path(userprofile) / ".dotnet" / "tools")

    # 4. Linux/macOS snap-installed dotnet → /snap/dotnet-sdk/.../tools
    #    (rare, but some Ubuntu users install via snap)
    snap_dotnet = Path("/snap/dotnet-sdk/current/tools")
    if snap_dotnet.exists():
        candidates.append(snap_dotnet)

    return [p for p in candidates if p.is_dir()]


def _check_dotnet_global_tool(tool_name: str, package_id: str) -> bool:
    """
    dotnet global tool availability check — 3-layer strategy:

    Layer 1: shutil.which() — PATH mein directly milta hai (best case)
    Layer 2: ~/.dotnet/tools/ direct file check — PATH mein nahi lekin installed hai
             (Linux/WSL/macOS pe common — user ne PATH update nahi kiya)
    Layer 3: dotnet tool list --global — definitive check (slow ~0.5s, last resort)

    Layer 2 WSL pe kyun important hai:
    - `dotnet tool install -g roslynator.dotnet.cli` → ~/.dotnet/tools/roslynator
    - Agar ~/.bashrc mein `export PATH=$PATH:~/.dotnet/tools` nahi hai →
      shutil.which("roslynator") → None, even though binary exists
    - Same on macOS with zsh (default shell since Catalina)
    """
    import platform as _plat

    # Layer 1: Standard PATH check
    if shutil.which(tool_name) is not None:
        return True

    # Layer 2: Direct file check in known dotnet tools directories
    exe_name = f"{tool_name}.exe" if _plat.system().lower() == "windows" else tool_name
    for tools_dir in _dotnet_global_tools_path():
        candidate = tools_dir / exe_name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
        # Windows: .exe extension
        candidate_exe = tools_dir / f"{tool_name}.exe"
        if candidate_exe.is_file():
            return True

    # Layer 3: dotnet tool list --global (definitive but slow ~0.5s)
    # Only reach here if layers 1+2 both missed
    try:
        import subprocess
        result = subprocess.run(
            ["dotnet", "tool", "list", "--global"],
            capture_output=True, text=True, timeout=15,
        )
        return package_id.lower() in result.stdout.lower()
    except Exception:
        return False


def _check_roslynator_available() -> bool:
    """
    roslynator availability — 3-layer detection (PATH → ~/.dotnet/tools/ → dotnet tool list).

    WSL/Linux pe dotnet tool install -g ke baad ~/.dotnet/tools/ mein jaata hai
    lekin PATH mein nahi hota jab tak user ne ~/.bashrc mein add nahi kiya.
    macOS pe zsh default shell hai aur same issue — ~/.zshrc update nahi hoti automatically.
    Windows pe PATH automatically update hoti hai installer se.
    """
    return _check_dotnet_global_tool("roslynator", "roslynator.dotnet.cli")


def check_tool_available(tool_name: str) -> bool:
    """Check karo ki tool system pe installed hai ya nahi."""
    # ── dotnet global tools — 3-layer detection (PATH → ~/.dotnet/tools/ → dotnet tool list) ──
    # WSL/Linux + macOS pe PATH automatically update nahi hoti after `dotnet tool install -g`
    # isliye shutil.which() alone fail karta hai even when tool is installed.
    _DOTNET_GLOBAL_TOOLS: dict[str, str] = {
        "roslynator":    "roslynator.dotnet.cli",
        "security-scan": "security-scan",
        "dotnet-stryker":"dotnet-stryker",
    }
    if tool_name in _DOTNET_GLOBAL_TOOLS:
        return _check_dotnet_global_tool(tool_name, _DOTNET_GLOBAL_TOOLS[tool_name])
    if tool_name == "pytest-cov":
        try:
            from importlib.util import find_spec
            return find_spec("pytest") is not None and find_spec("pytest_cov") is not None
        except (ImportError, ValueError):
            return False
    if tool_name == "hypothesis":
        try:
            from importlib.util import find_spec
            return find_spec("hypothesis") is not None
        except (ImportError, ValueError):
            return False
    # RapidCheck — clang++ available hona chahiye (compile ke liye)
    # Header existence project-specific hai — preview.py ke _find_rapidcheck_header
    # se check hota hai. Yahan sirf clang++ compiler check karo.
    if tool_name in {"rapidcheck", "rapidcheck-cuda"}:
        return shutil.which("clang++") is not None    # mutmut: shutil.which miss kar sakta hai Windows pe (.venv\Scripts\ PATH mein nahi hota)
    # Fix: _which_in_venv + importlib double-check
    if tool_name == "mutmut":
        if _which_in_venv("mutmut") is not None:
            return True
        try:
            from importlib.util import find_spec
            return find_spec("mutmut") is not None
        except (ImportError, ValueError):
            return False
    # pip-installed CLI tools jo Windows pe sirf venv/Scripts mein hote hain
    # (ruff, mypy, bandit, vulture, radon, pip-audit) — _which_in_venv use karo
    _PIP_CLI_TOOLS = {
        "ruff", "mypy", "bandit", "vulture", "radon", "pip-audit",
        "flawfinder", "lizard", "cpplint", "semgrep",
    }
    if tool_name in _PIP_CLI_TOOLS:
        return _which_in_venv(tool_name) is not None

    # C++ system tools — Windows pe common install paths bhi check karo
    # cppcheck: C:\Program Files\Cppcheck\cppcheck.exe
    # clang-tidy: C:\Program Files\LLVM\bin\clang-tidy.exe
    # clang++: C:\Program Files\LLVM\bin\clang++.exe (asan/ubsan/compsan ke liye)
    _CPP_SYSTEM_TOOLS: dict[str, list[str]] = {
        "cppcheck": [
            r"C:\Program Files\Cppcheck\cppcheck.exe",
            r"C:\Program Files (x86)\Cppcheck\cppcheck.exe",
        ],
        "clang-tidy": [
            r"C:\Program Files\LLVM\bin\clang-tidy.exe",
            r"C:\Program Files (x86)\LLVM\bin\clang-tidy.exe",
        ],
        "clang++": [
            r"C:\Program Files\LLVM\bin\clang++.exe",
            r"C:\Program Files (x86)\LLVM\bin\clang++.exe",
            # MSYS2 / MinGW paths
            r"C:\msys64\mingw64\bin\clang++.exe",
            r"C:\msys64\ucrt64\bin\clang++.exe",
        ],
    }
    if tool_name in _CPP_SYSTEM_TOOLS:
        # Pehle PATH mein dhundo
        if shutil.which(tool_name):
            return True
        # Phir Windows common install paths check karo
        import platform as _plat
        if _plat.system().lower() == "windows":
            for path in _CPP_SYSTEM_TOOLS[tool_name]:
                if Path(path).is_file():
                    return True
        return False
    # ── Dart / Flutter — Windows + macOS + Linux special path detection ──────
    # Windows pe Flutter SDK typically C:\Users\<user>\flutter\bin\ mein hota hai
    # ya choco/winget install kare toh C:\tools\flutter\bin\ mein.
    # macOS pe brew install flutter → /opt/homebrew/bin/ ya /usr/local/bin/
    # Linux pe snap install flutter → /snap/bin/ ya ~/.local/share/flutter/bin/
    # dart.exe aur flutter.exe PATH mein nahi hoti agar user ne manually add nahi kiya.
    _DART_FLUTTER_TOOLS = {"dart-analyze", "flutter-analyze", "dart-tests"}
    if tool_name in _DART_FLUTTER_TOOLS:
        # Konsa executable chahiye
        exe = "flutter" if tool_name == "flutter-analyze" else "dart"
        found = _check_dart_flutter_executable(exe)
        if not found:
            # Friendly skip reason ke liye False return karo —
            # verbose output mein "Executable not found" dikhega
            return False
        return True

    if tool_name.endswith("-tests"):
        test_executables = {
            "rust-tests": "cargo",
            "cargo-tests": "cargo",
            "go-tests": "go",
            "npm-tests": "npm",
            "mvn-tests": "mvn",
            "gradle-tests": "gradle",
            "dotnet-tests": "dotnet",
            "bundle-tests": "bundle",
            "composer-tests": "composer",
            "swift-tests": "swift",
            "dart-tests": "dart",
        }
        executable = test_executables.get(tool_name)
        if executable in {"dart", "flutter"}:
            return _check_dart_flutter_executable(executable)
        return bool(executable and shutil.which(executable))
    executable = _EXECUTABLE_MAP.get(tool_name, tool_name)
    return shutil.which(executable) is not None


def _resolve_dart_flutter_exe(exe: str) -> str | None:
    """
    Dart / Flutter executable ka absolute path return karo.

    _check_dart_flutter_executable ka path-returning version —
    woh bool return karta hai, yeh actual path return karta hai.

    _build_tool_command mein use hota hai taaki subprocess mein
    sirf "dart"/"flutter" string ki jagah full path bheja jaaye.
    Windows pe PATH mein nahi hoti lekin known location pe milti hai.

    Returns: absolute path string, ya None agar nahi mila.
    """
    import platform as _plat

    # Layer 1: Standard PATH check
    found = shutil.which(exe)
    if found:
        return found

    os_name = _plat.system().lower()
    exe_suffix = ".exe" if os_name == "windows" else ""
    home = Path.home()

    # Layer 2: Env vars
    flutter_root = os.environ.get("FLUTTER_ROOT", "")
    dart_sdk = os.environ.get("DART_SDK", "")
    pub_cache = os.environ.get("PUB_CACHE", "")

    env_paths: list[Path] = []
    if flutter_root:
        env_paths.append(Path(flutter_root) / "bin")
        if exe == "dart":
            env_paths.append(Path(flutter_root) / "bin" / "cache" / "dart-sdk" / "bin")
    if dart_sdk:
        env_paths.append(Path(dart_sdk) / "bin")
    if pub_cache:
        env_paths.append(Path(pub_cache) / "bin")

    for env_path in env_paths:
        candidate = env_path / f"{exe}{exe_suffix}"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    # Layer 3: Platform-specific known paths
    if os_name == "windows":
        win_paths = (
            [
                Path(r"C:\tools\flutter\bin"),
                Path(r"C:\flutter\bin"),
                Path(r"C:\src\flutter\bin"),
                home / "flutter" / "bin",
                home / "AppData" / "Local" / "flutter" / "bin",
                Path(r"C:\Program Files\FlutterSDK\bin"),
                home / "fvm" / "default" / "bin",
                home / "AppData" / "Local" / "fvm" / "default" / "bin",
            ] if exe == "flutter" else [
                Path(r"C:\tools\dart-sdk\bin"),
                Path(r"C:\Program Files\Dart\dart-sdk\bin"),
                Path(r"C:\tools\flutter\bin"),
                home / "flutter" / "bin",
            ]
        )
        for base in win_paths:
            for name in (f"{exe}.exe", f"{exe}.bat"):
                candidate = base / name
                if candidate.is_file():
                    return str(candidate)

    elif os_name == "darwin":
        for base in [
            Path("/opt/homebrew/bin"), Path("/usr/local/bin"),
            home / "fvm" / "default" / "bin", home / ".pub-cache" / "bin",
            home / "flutter" / "bin", home / "development" / "flutter" / "bin",
            Path("/opt/homebrew/opt/dart/libexec/bin"),
            Path("/usr/local/opt/dart/libexec/bin"),
        ]:
            candidate = base / exe
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)

    else:  # Linux / WSL
        for base in [
            Path("/snap/bin"), Path("/snap/flutter/current/bin"),
            home / "flutter" / "bin",
            home / "snap" / "flutter" / "common" / "flutter" / "bin",
            home / ".pub-cache" / "bin",
            home / "fvm" / "default" / "bin", home / ".fvm" / "default" / "bin",
            Path("/usr/lib/dart/bin"), Path("/usr/bin"), Path("/usr/local/bin"),
            home / ".local" / "share" / "dart" / "bin",
        ]:
            candidate = base / exe
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)

    return None


def _check_dart_flutter_executable(exe: str) -> bool:
    """
    Dart / Flutter executable check — bool wrapper around _resolve_dart_flutter_exe.
    Path detection logic _resolve_dart_flutter_exe mein hai (single source of truth).
    """
    return _resolve_dart_flutter_exe(exe) is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_tool(
    tool: ToolConfig,
    project_path: str,
    options: ToolRunOptions | None = None,
    env: dict[str, str] | None = None,
) -> ToolResult:
    """Ek tool async chalao."""
    run_options = options or ToolRunOptions()
    # Per-tool timeout: caller override → default table → global default
    timeout_seconds = (
        (run_options.tool_timeouts or {}).get(tool.name)
        or _DEFAULT_TOOL_TIMEOUTS.get(tool.name)
        or run_options.timeout_seconds
    )
    if not tool.available:
        return ToolResult(
            tool_name=tool.name,
            language=tool.language,
            success=False,
            stdout="",
            stderr="",
            return_code=-1,
            skipped=True,
            skip_reason=f"{tool.name} is not installed",
        )

    # Working directory — language-specific root pe chalao
    cwd = resolve_project_root(tool.language, project_path)
    cmd, temporary_directory = _build_tool_command(tool, project_path)
    run_env = os.environ.copy()
    # Python-based scanners can emit Unicode findings on Windows. Force their
    # subprocess stdio to UTF-8 instead of the machine's legacy code page.
    run_env.setdefault("PYTHONUTF8", "1")
    if env:
        run_env.update(env)

    try:
        async with asyncio.timeout(timeout_seconds):
            return_code, stdout_b, stderr_b = await _execute_command(cmd, cwd, run_env)
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        # exit 0 = clean, 1 = issues found, 2 = ruff syntax error in source — sab valid runs
        # exit -2 (timeout), -3 (not found) etc. = real failures
        # Semgrep exit codes: 0 = no findings, 1 = findings found, 2 = error,
        #   3 = config error, 4 = parse error, 7 = findings + partial scan (some files skipped)
        # Roslynator: 0 = no issues, 1 = issues found
        _TOOL_VALID_EXITS: dict[str, set[int]] = {
            "semgrep": {0, 1, 4, 7},   # 7 = findings with partial scan (valid output)
                                        # 4 = parse error on some files (still produces output)
        }
        tool_valid_exits = _TOOL_VALID_EXITS.get(tool.name)
        if tool_valid_exits is not None:
            valid_exit = return_code in tool_valid_exits
        else:
            valid_exit = return_code in (0, 1, 2)
        return ToolResult(
            tool_name=tool.name,
            language=tool.language,
            success=return_code == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            skipped=not valid_exit,
            skip_reason="" if valid_exit else f"exit {return_code}",
            temporary_directory=temporary_directory,
        )

    except TimeoutError:
        if temporary_directory:
            temporary_directory.cleanup()
        return ToolResult(
            tool_name=tool.name,
            language=tool.language,
            success=False,
            stdout="",
            stderr=(f"Timeout: {tool.name} did not complete within {timeout_seconds}s"),
            return_code=-2,
            skipped=True,
            skip_reason="Timeout",
        )
    except FileNotFoundError:
        if temporary_directory:
            temporary_directory.cleanup()
        return ToolResult(
            tool_name=tool.name,
            language=tool.language,
            success=False,
            stdout="",
            stderr=f"{tool.name} executable not found",
            return_code=-3,
            skipped=True,
            skip_reason="Executable not found",
        )
    except Exception as e:
        if temporary_directory:
            temporary_directory.cleanup()
        return ToolResult(
            tool_name=tool.name,
            language=tool.language,
            success=False,
            stdout="",
            stderr=str(e),
            return_code=-4,
            skipped=True,
            skip_reason=f"Error: {e}",
        )


def _resolve_dotnet_global_tool_exe(tool_name: str) -> str:
    """
    dotnet global tool ka actual executable path return karo.

    WSL/Linux pe `~/.dotnet/tools/` PATH mein nahi hoti — subprocess mein
    tool_name direct call karna fail karta hai even though binary exist karti hai.
    Yahan full absolute path return karte hain taaki subprocess seedha chalaye.

    Fallback: agar PATH mein milta hai ya koi directory nahi mili → tool_name as-is.
    """
    import platform as _plat

    # PATH mein hai → as-is (Windows pe always PATH mein hota hai)
    if shutil.which(tool_name) is not None:
        return tool_name

    exe_suffix = ".exe" if _plat.system().lower() == "windows" else ""
    for tools_dir in _dotnet_global_tools_path():
        candidate = tools_dir / f"{tool_name}{exe_suffix}"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    # Fallback — PATH pe rely karo
    return tool_name


def _build_tool_command(
    tool: ToolConfig,
    project_path: str,
) -> tuple[list[str], tempfile.TemporaryDirectory[str] | None]:
    temporary_directory = (
        tempfile.TemporaryDirectory(prefix="Lyncus-")
        if any("{tmpdir}" in part for part in tool.command)
        else None
    )
    temp_path = temporary_directory.name if temporary_directory else ""

    # pip-audit ke liye project dependency file dhundo
    # pip-audit sirf requirements.txt style files support karta hai directly
    # pyproject.toml ke liye pip-audit v2.7+ mein native support hai
    pip_audit_target = ""
    if "{pip_audit_target}" in tool.command:
        proj_root = Path(project_path) if Path(project_path).is_dir() else Path(project_path).parent
        if (proj_root / "requirements.txt").exists():
            # requirements.txt milne pe: sirf declared deps scan karo
            pip_audit_target = "--requirement=requirements.txt"
        elif (proj_root / "pyproject.toml").exists():
            # pyproject.toml milne pe: pip-audit v2.7+ native support
            pip_audit_target = "--requirement=pyproject.toml"
        else:
            # Koi file nahi — installed env scan karo lekin .venv ke system tools
            # (pip, setuptools) bahar rakhne ke liye --skip-editable use karo
            pip_audit_target = "--skip-editable"

    # dotnet global tools ke liye — WSL/Linux pe PATH mein nahi hoti ~/.dotnet/tools/
    # Pehle element (executable) ko absolute path se replace karo agar zaroorat ho
    _DOTNET_GLOBAL_EXE_TOOLS = {"roslynator", "security-scan", "dotnet-stryker"}
    # pip-installed CLI tools jo venv/bin mein hain lekin subprocess PATH mein nahi hoti
    _PIP_EXE_TOOLS = {"semgrep"}
    # Dart/Flutter tools — Windows pe PATH mein nahi hoti lekin
    # _check_dart_flutter_executable ne kisi known path se True return kiya tha.
    # Subprocess mein sirf "dart"/"flutter" string bhejne se FileNotFoundError aata hai.
    # Solution: wahi absolute path use karo jo detection mein mili thi.
    _DART_EXE_TOOLS = {"dart-analyze", "dart-tests"}
    _FLUTTER_EXE_TOOLS = {"flutter-analyze"}
    command = []
    first_part = True
    for part in tool.command:
        resolved = (
            part
            .replace(_PATH_ARGUMENT, project_path)
            .replace("{tmpdir}", temp_path)
            .replace("{pip_audit_target}", pip_audit_target)
            .replace(
                "{ctest_build_dir}",
                str(_find_ctest_build_dir(Path(project_path)) or project_path),
            )
            .replace("{cwd}", resolve_project_root(tool.language, project_path))
        )
        # Blank parts skip karo (jab placeholder empty string ho)
        if not resolved:
            first_part = False
            continue
        # First element = executable — absolute path resolve karo jahan zaroorat ho
        if first_part:
            if tool.name in _DOTNET_GLOBAL_EXE_TOOLS:
                resolved = _resolve_dotnet_global_tool_exe(resolved)
            elif tool.name in _PIP_EXE_TOOLS:
                # pip-installed tools: _which_in_venv se actual path lo
                found = _which_in_venv(resolved)
                if found:
                    resolved = found
            elif tool.name in _DART_EXE_TOOLS or tool.name in _FLUTTER_EXE_TOOLS:
                # Dart/Flutter: PATH mein nahi hoti Windows pe —
                # _check_dart_flutter_executable wala path use karo
                exe = "flutter" if tool.name in _FLUTTER_EXE_TOOLS else "dart"
                dart_path = _resolve_dart_flutter_exe(exe)
                if dart_path:
                    resolved = dart_path
        first_part = False
        command.append(resolved)

    return command, temporary_directory


async def _execute_command(
    command: list[str],
    cwd: str,
    env: dict[str, str],
) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        if process.stdout is None or process.stderr is None:
            raise RuntimeError("Subprocess output pipes were not created")
        stdout, stderr = await asyncio.gather(
            _read_limited(process.stdout, _MAX_CAPTURE_BYTES_PER_STREAM),
            _read_limited(process.stderr, _MAX_CAPTURE_BYTES_PER_STREAM),
        )
    except asyncio.CancelledError:
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass
        raise
    return process.returncode or 0, stdout, stderr


async def _read_limited(stream: asyncio.StreamReader, limit: int) -> bytes:
    """Drain a subprocess stream while retaining only its first ``limit`` bytes."""
    captured = bytearray()
    truncated = False
    while chunk := await stream.read(_CHUNK_READ_BYTES):
        remaining = limit - len(captured)
        if remaining > 0:
            captured.extend(chunk[:remaining])
        if len(chunk) > remaining:
            truncated = True

    if truncated:
        payload_limit = max(0, limit - len(_OUTPUT_TRUNCATION_MARKER))
        return bytes(captured[:payload_limit]) + _OUTPUT_TRUNCATION_MARKER
    return bytes(captured)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERBOSE LOGGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class VerboseLogger:
    """
    Structured tool-level logging for verbose mode.

    When --verbose is enabled, prints each tool's status in real-time:
      ── Running tools ──
      ⚙  Running  ruff                  (quality)
      ✅  Done     ruff                  [0.4s]
      ⏭  Skipped  mypy                  not installed
      ❌  Error    bandit                timeout

    Design goals:
      - Thin logger object — avoids injecting Console into runner internals
      - Prints to stderr so stdout (JSON/SARIF) stays clean
      - Zero overhead when verbose=False (early return)
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self._console: Console | None
        if enabled:
            from rich.console import Console  # local import — verbose mode only
            self._console = Console(stderr=True)
        else:
            self._console = None

    def _print(self, message: str) -> None:
        console = self._console
        if console is None:
            return
        console.print(message)

    def tool_start(self, tool: ToolConfig) -> None:
        if not self._enabled:
            return
        from rich.markup import escape as rich_escape
        self._print(
            f"  [dim]⚙  Running[/dim]  "
            f"[bold cyan]{rich_escape(tool.name):<24}[/bold cyan]"
            f"[dim]({rich_escape(tool.check_type)})[/dim]"
        )

    def tool_done(self, result: ToolResult, elapsed: float) -> None:
        if not self._enabled:
            return
        from rich.markup import escape as rich_escape
        if result.skipped:
            reason = result.skip_reason or "not installed"
            self._print(
                f"  [dim]⏭  Skipped[/dim]  "
                f"[yellow]{rich_escape(result.tool_name):<24}[/yellow]"
                f"[dim]{rich_escape(reason)}[/dim]"
            )
        elif not result.skipped:
            # Tool ran successfully (valid exit) — skipped=False means valid run
            self._print(
                f"  [dim]✅  Done   [/dim]  "
                f"[green]{rich_escape(result.tool_name):<24}[/green]"
                f"[dim][{elapsed:.1f}s][/dim]"
            )
        else:
            skip_reason = result.skip_reason or f"exit {result.return_code}"
            self._print(
                f"  [dim]❌  Error  [/dim]  "
                f"[red]{rich_escape(result.tool_name):<24}[/red]"
                f"[dim]{rich_escape(skip_reason)}[/dim]"
            )

    def section(self, title: str) -> None:
        if not self._enabled:
            return
        self._print(f"\n  [bold dim]── {title} ──[/bold dim]")

    def summary(self, ran: int, skipped: int) -> None:
        if not self._enabled:
            return
        self._print(
            f"\n  [dim]Tools ran:[/dim] [bold]{ran}[/bold]  "
            f"[dim]skipped:[/dim] [bold]{skipped}[/bold]\n"
        )


def _apply_linux_only_filter(
    tools: list[ToolConfig],
    verbose: bool,
) -> list[ToolConfig]:
    """
    Platform ke hisaab se tools filter karo.

    CI/CD mein: koi tool skip mat karo — GitHub Actions linux runner pe sab chalta hai.
    Local Windows: linux-native + windows-incompatible tools skip karo.
    Local macOS: sirf linux-native tools skip karo.
    Local Linux: koi tool skip mat karo.
    """
    skipped: list[ToolConfig] = []
    filtered: list[ToolConfig] = []

    for tool in tools:
        skip, reason = should_skip_tool_on_platform(tool.name)
        if skip:
            skipped.append(tool)
        else:
            filtered.append(tool)

    if verbose and skipped:
        from rich.console import Console as _RC
        from rich.markup import escape as rich_escape
        ci_note = " (CI/CD mein ye tools run honge)" if is_ci() else ""
        _RC(stderr=True).print(
            f"  [dim]ℹ  Platform-skipped tools: "
            f"{rich_escape(', '.join(t.name for t in skipped))}"
            f"{ci_note}[/dim]"
        )
    return filtered


def _apply_slow_filter(tools: list[ToolConfig]) -> list[ToolConfig]:
    """Mutation testing aur slow tools skip karo (--skip-slow flag ke liye)."""
    # ALWAYS_SKIP_MUTATION_TOOLS pehle se platform.py se filter ho jaate hain.
    # Yahan sirf woh slow tools hain jo --skip-slow se skip honge (mutation nahi).
    # hypothesis + rapidcheck FAST hain — skip nahi honge --skip-slow mein bhi.
    slow_names = {
        "pytest-cov",       # slow — full test suite run karta hai
        "cargo-tarpaulin",
        "cargo-mutants",    # Rust mutation — fast lekin --skip-slow mein skip karo
        "stryker",
        "stryker-js",
        "stryker-ts",
        "jacoco",
        "coverlet",
    }
    return [t for t in tools if t.name not in slow_names]


def _filter_tools_for_run(
    language: str,
    lang_key: str,
    only: str | None,
    skip_slow: bool,
    verbose: bool,
    project_path: str | None = None,
) -> list[ToolConfig]:
    """Language, only-filter, slow-filter, aur platform ke hisaab se tools select karo."""
    # Strict: only pick tools whose language matches lang_key or language
    # This prevents cpp/csharp/etc. tools from bleeding into a python scan
    allowed_languages = {lang_key, language}
    tools = [t for t in TOOL_REGISTRY if t.language in allowed_languages]

    # TypeScript-only tools include karo (only when language is typescript)
    if language == "typescript":
        ts_tools = [t for t in TOOL_REGISTRY if t.language == "typescript"]
        existing_names = {t.name for t in tools}
        tools += [t for t in ts_tools if t.name not in existing_names]

    if project_path:
        test_tool = _project_test_tool(language, project_path)
        tools = [t for t in tools if t.name != "pytest-cov" or test_tool is not None]
        if (
            test_tool
            and all(t.name != test_tool.name for t in tools)
            and test_tool.language in allowed_languages
        ):
            tools.append(test_tool)

    if only:
        tools = [t for t in tools if t.check_type == only]

    tools = _apply_linux_only_filter(tools, verbose)

    if skip_slow:
        tools = _apply_slow_filter(tools)

    return tools


def _split_runnable_skipped(
    tools: list[ToolConfig],
    skip_unavailable: bool,
) -> tuple[list[ToolConfig], list[ToolConfig]]:
    """Tool availability check karo aur runnable/skipped mein split karo."""
    for tool in tools:
        tool.available = check_tool_available(tool.name)

    # hypothesis standalone run nahi hota — sirf display/availability ke liye hai
    # pytest-cov ke sath automatically chalata hai (hypothesis_profile plugin ke zariye)
    # rapidcheck TOOL_REGISTRY mein proper ToolConfig hai — woh actually run karta hai
    _display_only_tools = {"hypothesis"}

    if skip_unavailable:
        runnable = [t for t in tools if t.available and t.name not in _display_only_tools]
        skipped = [t for t in tools if not t.available and t.name not in _display_only_tools]
        return runnable, skipped
    runnable = [t for t in tools if t.name not in _display_only_tools]
    return runnable, []

async def _run_tools_with_semaphore(
    runnable: list[ToolConfig],
    project_path: str,
    run_options: ToolRunOptions,
    logger: VerboseLogger,
    hypothesis_env: dict[str, str],
) -> list[ToolResult | BaseException]:
    """Concurrent aur sequential tools ko semaphore ke sath run karo."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_TOOLS)

    async def run_limited(tool: ToolConfig) -> ToolResult:
        async with semaphore:
            logger.tool_start(tool)
            t0 = asyncio.get_event_loop().time()
            tool_env = None
            if tool.name == "pytest-cov":
                tool_env = hypothesis_env
            elif tool.name == "ctest" and tool.language in {"cpp", "cuda"}:
                tool_env = {"RC_PARAMS": f"max_success={_RAPIDCHECK_MAX_SUCCESS}"}
            result = await run_tool(tool, project_path, options=run_options, env=tool_env)
            elapsed = asyncio.get_event_loop().time() - t0
            logger.tool_done(result, elapsed)
            return result

    _MUTATION_TOOL_NAMES = {
        # Permanently skipped tools (ALWAYS_SKIP_MUTATION_TOOLS) yahan nahi aate —
        # platform filter pehle hata deta hai. Sirf woh jo kabhi kabhi run ho sakte hain.
        "cargo-mutants",    # Rust — fast, --skip-slow ke bina run hoga
        "stryker",          # C# — dotnet-based, sequential zaroor hai
        "stryker-js",       # JS — npm-based, sequential
        "stryker-ts",       # TS — npm-based, sequential
        "dotnet-stryker",   # C# alias
    }
    concurrent_tools = [t for t in runnable if t.name not in _MUTATION_TOOL_NAMES]
    sequential_tools = [t for t in runnable if t.name in _MUTATION_TOOL_NAMES]

    raw: list[ToolResult | BaseException] = list(
        await asyncio.gather(*[run_limited(t) for t in concurrent_tools], return_exceptions=True)
    )
    for tool in sequential_tools:
        try:
            raw.append(await run_limited(tool))
        except BaseException as error:
            raw.append(error)

    # Re-order so index matches concurrent_tools + sequential_tools
    return raw


def _wrap_results(
    raw_results: list[ToolResult | BaseException],
    runnable: list[ToolConfig],
) -> list[ToolResult]:
    """BaseException entries ko ToolResult mein wrap karo."""
    results: list[ToolResult] = []
    for i, res in enumerate(raw_results):
        if isinstance(res, BaseException):
            tool = runnable[i]
            results.append(ToolResult(
                tool_name=tool.name,
                language=tool.language,
                success=False,
                stdout="",
                stderr=str(res),
                return_code=-5,
                skipped=True,
                skip_reason=f"Unexpected error: {type(res).__name__}: {res}",
            ))
        else:
            results.append(res)
    return results


async def run_all_tools(
    language: str,
    project_path: str,
    only: str | None = None,
    skip_unavailable: bool = True,
    options: ToolRunOptions | None = None,
    skip_slow: bool = False,
    verbose: bool = False,
) -> list[ToolResult]:
    """
    Run all tools for the given language in parallel.

    Args:
        language:         Programming language (python, rust, go, etc.)
        project_path:     Path to the project root
        only:             Run only one type — quality/security/deadcode/coverage/faketests
        skip_unavailable: Skip tools that are not installed
        options:          Per-tool execution settings
        skip_slow:        Skip mutation testing and coverage tools
        verbose:          Print real-time status for each tool
    """
    run_options = options or ToolRunOptions()
    logger = VerboseLogger(enabled=verbose)
    hypothesis_env = {
        "LYNCUS_HYPOTHESIS_MAX_EXAMPLES": str(_HYPOTHESIS_MAX_EXAMPLES),
    }

    lang_key = "javascript" if language == "typescript" else language

    tools = _filter_tools_for_run(language, lang_key, only, skip_slow, verbose, project_path)
    runnable, skipped = _split_runnable_skipped(tools, skip_unavailable)

    if verbose:
        logger.section("Running tools")

    _MUTATION_TOOL_NAMES = {
        # Permanently skipped tools (ALWAYS_SKIP_MUTATION_TOOLS) platform filter se
        # pehle hi hat jaate hain — yahan sirf woh jo sequential run karne hain.
        "cargo-mutants",
        "stryker",
        "stryker-js",
        "stryker-ts",
        "dotnet-stryker",
    }
    concurrent_tools = [t for t in runnable if t.name not in _MUTATION_TOOL_NAMES]
    sequential_tools = [t for t in runnable if t.name in _MUTATION_TOOL_NAMES]
    ordered_runnable = concurrent_tools + sequential_tools

    raw_results = await _run_tools_with_semaphore(
        runnable, project_path, run_options, logger, hypothesis_env
    )
    results = _wrap_results(raw_results, ordered_runnable)

    # Skipped tool results
    skip_results = [
        ToolResult(
            tool_name=t.name,
            language=t.language,
            success=False,
            stdout="",
            stderr="",
            return_code=-1,
            skipped=True,
            skip_reason="not installed",
        )
        for t in skipped
    ]

    if verbose:
        for t in skipped:
            fake = ToolResult(
                tool_name=t.name, language=t.language, success=False,
                stdout="", stderr="", return_code=-1,
                skipped=True, skip_reason="not installed",
            )
            logger.tool_done(fake, 0.0)
        # hypothesis display-only tool ka status bhi dikhao
        _display_only = {"hypothesis"}
        for t in tools:
            if t.name in _display_only:
                status = "✅ runs via pytest-cov" if t.available else "not installed"
                from rich.console import Console as _RC
                from rich.markup import escape as rich_escape
                color = "green" if t.available else "yellow"
                _RC(stderr=True).print(
                    f"  [dim]ℹ  [/dim]  "
                    f"[{color}]{rich_escape(t.name):<24}[/{color}]"
                    f"[dim]{rich_escape(status)}[/dim]"
                )
        ran_count = len([r for r in results if not r.skipped])
        skip_count = len(skipped) + len([r for r in results if r.skipped])
        logger.summary(ran_count, skip_count)

    return results + skip_results


def get_available_tools(language: str) -> dict[str, bool]:
    """
    Language ke tools aur unki availability.

    Platform-skipped tools bhi include karte hain — False ke sath.
    Caller `should_skip_tool_on_platform()` se reason le sakta hai.
    """
    lang_key = "javascript" if language == "typescript" else language
    tools = [t for t in TOOL_REGISTRY if t.language in (lang_key, language)]
    result: dict[str, bool] = {}
    for t in tools:
        should_skip, _ = should_skip_tool_on_platform(t.name)
        if should_skip:
            result[t.name] = False  # Platform-incompatible — not available
        else:
            result[t.name] = check_tool_available(t.name)
    return result


def get_all_languages() -> list[str]:
    """Supported languages ki list."""
    seen = set()
    langs = []
    for t in TOOL_REGISTRY:
        if t.language not in seen:
            seen.add(t.language)
            langs.append(t.language)
    return langs


def get_tool_install_info(language: str) -> dict[str, dict[str, str | bool]]:
    """Language ke tools ke install commands aur availability."""
    lang_key = "javascript" if language == "typescript" else language
    tools = [t for t in TOOL_REGISTRY if t.language in (lang_key, language)]
    return {
        t.name: {
            "available": check_tool_available(t.name),
            "install_cmd": t.install_cmd,
            "description": t.description,
            "check_type": t.check_type,
        }
        for t in tools
    }
