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
from collections.abc import Iterator

from Lyncus.core.platform import (
    LINUX_NATIVE_TOOLS as _LINUX_NATIVE_TOOLS,
    should_skip_tool_on_platform,
    is_ci,
    current_os,
)


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
    timeout_seconds: int = 120
    tool_timeouts: dict[str, int] | None = None


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
_RAPIDCHECK_MAX_SUCCESS = 1000  # RapidCheck successful cases per property
_PYTHON_SCAN_EXCLUDES = (
    ".venv,venv,env,node_modules,.git,dist,build,__pycache__,*.egg-info,"
    ".mypy_cache,.pytest_cache,.ruff_cache,.hypothesis,.cache,cache,target,"
    "bin,obj,vendor,packages,.gradle"
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL TOOL REGISTRY — Sab supported languages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_REGISTRY: list[ToolConfig] = [
    # ── PYTHON ────────────────────────────────────────────────────────────────
    ToolConfig(
        "ruff",
        ["ruff", "check", _PATH_ARGUMENT, "--output-format", "text", "--no-cache"],
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
    ),
    ToolConfig(
        "vulture",
        [
            "vulture",
            _PATH_ARGUMENT,
            "--min-confidence", str(_VULTURE_MIN_CONFIDENCE),
            # .venv, site-packages aur dusre non-project dirs exclude karo
            # Vulture --exclude comma-separated glob patterns leta hai
            "--exclude",
            ".venv,venv,env,.git,dist,build,__pycache__,*.egg-info,node_modules",
        ],
        "python",
        "deadcode",
        description="Dead code detector",
        install_cmd="pip install vulture",
    ),
    ToolConfig(
        "radon",
        ["radon", "cc", _PATH_ARGUMENT, "-s", "-a", "-nb"],
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
        ["python", "-m", "Lyncus.core.mutmut_runner"],
        "python",
        "faketests",
        description="Mutation testing",
        install_cmd="pip install 'mutmut>=3.0,<4'",
    ),
    # ✅ Fix #11: pytest-cov registry mein add karo — Python coverage missing tha
    ToolConfig(
        "pytest-cov",
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "Lyncus.core.hypothesis_profile",
            f"--cov={_PATH_ARGUMENT}",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=json",
            "-q",
        ],
        "python",
        "coverage",
        description="Python branch coverage (pytest-cov)",
        install_cmd="pip install pytest-cov hypothesis",
    ),
    # hypothesis — property-based testing (Python)
    # Pytest plugin ke roop mein kaam karta hai — pytest-cov ke sath chalata hai
    # check_tool_available() mein importlib se check hoga (shutil.which nahi)
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
        ["cpplint", "--recursive", "--filter=-build/include_subdir,-legal/copyright", _PATH_ARGUMENT],
        "cpp",
        "quality",
        description="Google C++ style checker",
        install_cmd="pip install cpplint",
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
        "stryker",
        ["dotnet", "stryker", "--reporter", "json"],
        "csharp",
        "faketests",
        description="C# mutation testing",
        install_cmd="dotnet tool install -g dotnet-stryker",
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
    ".git", ".venv", "venv", "env", "node_modules", "build", "dist",
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

    if language in {"cpp", "cuda"}:
        if _find_ctest_build_dir(root):
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
    # Dart
    "dart-analyze":   "dart",
    "flutter-analyze":"flutter",
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
}

# Tools jo sirf Linux pe natively kaam karte hain — platform.py se import kiya
# (windows/macos pe skip, CI/CD mein always run)
_LINUX_ONLY_TOOL_NAMES: frozenset[str] = _LINUX_NATIVE_TOOLS


def _is_linux_platform() -> bool:
    """Backward compat alias — use platform.py functions directly jahan possible ho."""
    import platform
    return platform.system().lower() == "linux"


def check_tool_available(tool_name: str) -> bool:
    """Check karo ki tool system pe installed hai ya nahi."""
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
        return bool(executable and shutil.which(executable))
    executable = _EXECUTABLE_MAP.get(tool_name, tool_name)
    return shutil.which(executable) is not None


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
    timeout_seconds = (run_options.tool_timeouts or {}).get(tool.name, run_options.timeout_seconds)
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

    command = []
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
        if resolved:
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
        elif result.return_code in (0, 1, 2):
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
    """Mutation testing aur slow tools skip karo."""
    slow_names = {
        "mutmut", "pytest-cov",
        "cargo-tarpaulin", "cargo-mutants",
        "go-mutesting",
        "stryker", "stryker-js", "stryker-ts",
        "pitest",
        "dotnet-stryker", "coverlet",
        "mutant",
        "infection",
        "jacoco",
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
        if test_tool and all(t.name != test_tool.name for t in tools):
            # Only add test_tool if it belongs to the correct language
            if test_tool.language in allowed_languages:
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
    # isliye runnable list se bahar rakhte hain
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
        "mutmut", "cargo-mutants", "go-mutesting",
        "stryker", "stryker-js", "stryker-ts",
        "pitest", "dotnet-stryker", "mutant", "infection",
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
        "mutmut", "cargo-mutants", "go-mutesting",
        "stryker", "stryker-js", "stryker-ts",
        "pitest", "dotnet-stryker", "mutant", "infection",
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
