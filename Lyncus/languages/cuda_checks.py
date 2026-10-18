"""
CUDA Language Checks — compute-sanitizer, nsight-systems, nsight-compute, clang-tidy
CUDA 12.4+ aur NVCC ke liye optimized. .cu aur .cuh files handle karta hai.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"
_BINARY_ARGUMENT = "{binary}"

# Named constants — magic numbers nahi
_GPU_OCCUPANCY_MIN = 0.5          # Minimum acceptable GPU occupancy (50%)
_KERNEL_DURATION_WARN_US = 1_000_000   # Kernel longer than 1 second = warning (in microseconds)
_CUDA_MAX_BLOCK_SIZE = 1024       # CUDA max threads per block (hardware limit)
_CLANG_TIDY_LOOKAHEAD_LINES = 5  # Lines to check before cudaMemcpy for loop detection
_NSYS_NS_TO_US_DIVISOR = 1000    # Convert nanoseconds to microseconds
_NSYS_US_TO_MS_DIVISOR = 1000    # Convert microseconds to milliseconds


@dataclass
class CudaToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_gpu: bool = False          # Actual GPU chahiye
    needs_compiled_binary: bool = False   # Compiled .out/.exe chahiye


# ── CUDA TOOL DEFINITIONS ─────────────────────────────────────────────────────

CUDA_TOOLS: list[CudaToolConfig] = [

    CudaToolConfig(
        name="compute-sanitizer",
        command=[
            "compute-sanitizer",
            "--tool", "memcheck",
            "--leak-check", "full",
            "--report-api-errors", "all",
            _BINARY_ARGUMENT,
        ],
        check_type="memory",
        output_format="text",
        description="GPU memory error detector — out-of-bounds, race conditions, leaks",
        min_version="12.4",
        install_cmd="CUDA Toolkit ke saath aata hai: https://developer.nvidia.com/cuda-downloads",
        needs_gpu=True,
        needs_compiled_binary=True,
    ),

    CudaToolConfig(
        name="compute-sanitizer-racecheck",
        command=[
            "compute-sanitizer",
            "--tool", "racecheck",
            "--print-level", "warn",
            _BINARY_ARGUMENT,
        ],
        check_type="memory",
        output_format="text",
        description="Shared memory race condition detector",
        min_version="12.4",
        install_cmd="CUDA Toolkit mein built-in",
        needs_gpu=True,
        needs_compiled_binary=True,
    ),

    CudaToolConfig(
        name="compute-sanitizer-initcheck",
        command=[
            "compute-sanitizer",
            "--tool", "initcheck",
            _BINARY_ARGUMENT,
        ],
        check_type="memory",
        output_format="text",
        description="Uninitialized device memory access detector",
        min_version="12.4",
        install_cmd="CUDA Toolkit mein built-in",
        needs_gpu=True,
        needs_compiled_binary=True,
    ),

    CudaToolConfig(
        name="clang-tidy-cuda",
        command=[
            "clang-tidy",
            _PATH_ARGUMENT,
            "--checks=cuda-*,clang-diagnostic-*,modernize-*,performance-*",
            "--",
            "-x", "cuda",
            "--cuda-gpu-arch=sm_75",
            "-I/usr/local/cuda/include",
        ],
        check_type="quality",
        output_format="text",
        description="Clang-tidy CUDA checks — kernel launch, memory, type issues",
        min_version="18.0.0",
        install_cmd=(
            "apt-get install -y clang-tidy / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent --accept-package-agreements "
            "--accept-source-agreements / choco install llvm -y"
        ),
    ),

    CudaToolConfig(
        name="nvcc-warnings",
        command=[
            "nvcc",
            "-Werror", "all-warnings",
            "--compiler-options", "-Wall,-Wextra",
            "--generate-code", "arch=compute_75,code=sm_75",
            "--keep",
            "-c", _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="text",
        description="NVCC compiler warnings — CUDA-specific issues, deprecated APIs",
        min_version="12.4",
        install_cmd=(
            "apt-get install -y nvidia-cuda-toolkit / "
            "winget install --id Nvidia.CUDA --exact --silent --accept-package-agreements "
            "--accept-source-agreements / choco install cuda -y"
        ),
    ),

    CudaToolConfig(
        name="nsight-systems-cli",
        command=[
            "nsys", "profile",
            "--output={tmpdir}/nsys_report",
            "--stats=true",
            "--export=json",
            _BINARY_ARGUMENT,
        ],
        check_type="performance",
        output_format="json",
        description="GPU timeline profiler — kernel overlaps, memory transfers, bottlenecks",
        min_version="2024.2.1",
        install_cmd="Download: https://developer.nvidia.com/nsight-systems",
        needs_gpu=True,
        needs_compiled_binary=True,
    ),

    CudaToolConfig(
        name="cppcheck-cuda",
        command=[
            "cppcheck",
            "--enable=all",
            "--language=c++",
            "--std=c++17",
            "--suppress=missingIncludeSystem",
            "--xml",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="xml",
        description="Static analysis for CUDA C++ host code — memory, logic errors",
        min_version="2.14.0",
        install_cmd=(
            "apt-get install -y cppcheck / brew install cppcheck / "
            "winget install --id Cppcheck.Cppcheck --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install cppcheck -y"
        ),
    ),
]


# ── COMPUTE-SANITIZER PARSER ──────────────────────────────────────────────────

def parse_compute_sanitizer_output(output: str) -> list[dict[str, Any]]:
    """compute-sanitizer text output parse ."""
    issues = []

    # Error pattern: ========= CUDA-MEMCHECK: Error at 0x... (file.cu:line)
    error_pattern = re.compile(
        r"========= (.+?)\n"
        r"========= .+?at 0x[0-9a-f]+\s+\((.+?):(\d+)\)",
        re.MULTILINE | re.DOTALL,
    )

    for m in error_pattern.finditer(output):
        error_msg, file, line = m.groups()
        issues.append({
            "file":     file.strip(),
            "line":     int(line),
            "column":   0,
            "severity": _sanitizer_severity(error_msg),
            "rule_id":  "CUDA-MEMCHECK",
            "message":  error_msg.strip()[:120],
            "category": "MEMORY",
        })

    # Summary: ========= N errors detected
    summary_match = re.search(r"========= (\d+) error", output)
    if summary_match and int(summary_match.group(1)) > 0 and not issues:
        issues.append({
            "file":     "",
            "line":     0,
            "column":   0,
            "severity": "critical",
            "rule_id":  "CUDA-MEMCHECK-SUMMARY",
            "message":  f"{summary_match.group(1)} CUDA memory errors detected",
            "category": "MEMORY",
        })

    return issues


def _sanitizer_severity(msg: str) -> str:
    msg_lower = msg.lower()
    critical_keywords = {
        "out of bounds", "race condition", "uninitialized",
        "invalid write", "invalid read", "double free",
    }
    for kw in critical_keywords:
        if kw in msg_lower:
            return "critical"
    return "warning"


# ── NVCC WARNINGS PARSER ──────────────────────────────────────────────────────

def parse_nvcc_warnings(output: str) -> list[dict[str, Any]]:
    """NVCC compiler output parse ."""
    return [
        issue
        for raw_line in output.splitlines()
        if (issue := _parse_nvcc_line(raw_line)) is not None
    ]


def _parse_nvcc_line(raw_line: str) -> dict[str, Any] | None:
    location, separator, diagnostic = raw_line.rpartition("): ")
    if not separator:
        return None
    file, separator, line = location.rpartition("(")
    if not separator or not line.isdigit():
        return None
    level, separator, message = diagnostic.partition(": ")
    if not separator or level not in ("warning", "error"):
        return None
    return {
        "file": file.strip().replace("\\", "/"),
        "line": int(line),
        "column": 0,
        "severity": "critical" if level == "error" else "warning",
        "rule_id": "NVCC-WARNING",
        "message": message.strip(),
        "category": _nvcc_category(message),
    }


def _nvcc_category(message: str) -> str:
    message_lower = message.lower()
    if "deprecated" in message_lower:
        return "DEADCODE"
    if "memory" in message_lower or "access" in message_lower:
        return "MEMORY"
    if "launch" in message_lower:
        return "CUDA-LAUNCH"
    return "QUALITY"


# ── NSIGHT SYSTEMS JSON PARSER ────────────────────────────────────────────────

def parse_nsight_systems_json(json_path: str) -> list[dict[str, Any]]:
    """nsys export JSON output parse — performance issues."""
    issues = []

    try:
        with open(json_path) as f:
            data = json.load(f)

        kernels = data.get("kernels", [])
        for kernel in kernels:
            duration_us = kernel.get("duration_ns", 0) / _NSYS_NS_TO_US_DIVISOR
            occupancy   = kernel.get("achieved_occupancy", 1.0)
            name        = kernel.get("shortName", kernel.get("name", "unknown"))

            # Low occupancy = performance problem
            if occupancy < _GPU_OCCUPANCY_MIN:
                issues.append({
                    "file":     "",
                    "line":     0,
                    "column":   0,
                    "severity": "warning",
                    "rule_id":  "CUDA-LOW-OCCUPANCY",
                    "message":  (
                        f"Kernel '{name}': low GPU occupancy {occupancy * 100:.1f}% "
                        f"(min: {int(_GPU_OCCUPANCY_MIN * 100)}%)"
                    ),
                    "category": "PERF",
                })

            # Very long kernels without async overlap
            if duration_us > _KERNEL_DURATION_WARN_US:
                duration_ms = duration_us / _NSYS_US_TO_MS_DIVISOR
                issues.append({
                    "file":     "",
                    "line":     0,
                    "column":   0,
                    "severity": "info",
                    "rule_id":  "CUDA-LONG-KERNEL",
                    "message":  f"Kernel '{name}': {duration_ms:.1f}ms — consider batching or async",
                    "category": "PERF",
                })

    except (json.JSONDecodeError, OSError, KeyError):
        pass

    return issues


# ── CLANG-TIDY CUDA PARSER ────────────────────────────────────────────────────

def parse_clang_tidy_cuda_output(output: str) -> list[dict[str, Any]]:
    """clang-tidy CUDA output parse (same format as C++)."""
    issues = []
    for raw_line in output.splitlines():
        before_check, separator, check = raw_line.rpartition(" [")
        if not separator or not check.endswith("]"):
            continue
        fields = before_check.rsplit(":", 3)
        if len(fields) != 4:
            continue
        file, line, col, level_message = fields
        level, separator, msg = level_message.strip().partition(":")
        check = check[:-1]
        if (
            not separator
            or not line.isdigit()
            or not col.isdigit()
            or level not in ("error", "warning")
        ):
            continue

        # Only .cu/.cuh files
        if not any(file.endswith(ext) for ext in (".cu", ".cuh")):
            continue

        issues.append({
            "file":     file.strip(),
            "line":     int(line),
            "column":   int(col),
            "severity": "critical" if level == "error" else "warning",
            "rule_id":  f"CUDA-TIDY-{check.upper().replace('-', '_')}",
            "message":  msg.strip(),
            "category": _cuda_tidy_category(check),
        })

    return issues


def _cuda_tidy_category(check_name: str) -> str:
    if "cuda" in check_name.lower():
        return "CUDA-SPECIFIC"
    if "performance" in check_name.lower():
        return "PERF"
    if "modernize" in check_name.lower():
        return "QUALITY"
    return "QUALITY"


# ── KERNEL PATTERN ANALYZER ───────────────────────────────────────────────────

def analyze_cuda_patterns(source_code: str, file_path: str) -> list[dict[str, Any]]:
    """
    CUDA source code mein common anti-patterns dhundo.
    Static analysis without running — hardcoded patterns.
    """
    lines = source_code.splitlines()
    issues = []
    for line_number, line in enumerate(lines, 1):
        issues.extend(_cuda_sync_memcpy_issues(lines, line, line_number, file_path))
        issues.extend(_check_cuda_block_size(line, line_number, file_path))
        api_issue = _unchecked_cuda_api_issue(line, line_number, file_path)
        if api_issue:
            issues.append(api_issue)
    return issues


def _cuda_sync_memcpy_issues(
    lines: list[str],
    line: str,
    line_number: int,
    file_path: str,
) -> list[dict[str, Any]]:
    if "cudaMemcpy(" not in line or "Async" in line:
        return []
    preceding_lines = lines[max(0, line_number - _CLANG_TIDY_LOOKAHEAD_LINES):line_number]
    if not any(loop in preceding_lines for loop in ("for(", "for (", "while(")):
        return []
    return [{
        "file": file_path,
        "line": line_number,
        "column": 0,
        "severity": "warning",
        "rule_id": "CUDA-SYNC-MEMCPY-IN-LOOP",
        "message": "cudaMemcpy in loop — use cudaMemcpyAsync + stream for better performance",
        "category": "PERF",
    }]


def _check_cuda_block_size(line: str, line_number: int, file_path: str) -> list[dict[str, Any]]:
    match = re.search(r"<<<\s*\d+\s*,\s*(\d+)\s*>>>", line)
    if not match or int(match.group(1)) <= _CUDA_MAX_BLOCK_SIZE:
        return []
    block_size = int(match.group(1))
    return [{
        "file": file_path,
        "line": line_number,
        "column": 0,
        "severity": "critical",
        "rule_id": "CUDA-INVALID-BLOCK-SIZE",
        "message": f"Block size {block_size} exceeds CUDA limit of {_CUDA_MAX_BLOCK_SIZE} threads/block",
        "category": "CUDA-SPECIFIC",
    }]


def _unchecked_cuda_api_issue(
    line: str, line_number: int, file_path: str
) -> dict[str, Any] | None:
    api_calls = ("cudaMalloc(", "cudaMemcpy(", "cudaFree(", "cudaLaunchKernel(")
    api = next((call for call in api_calls if call in line), None)
    if not api:
        return None
    result_markers = ("cudaError", "err =", "ret =", "status =")
    if any(marker in line for marker in result_markers) or line.strip().startswith("//"):
        return None
    return {
        "file": file_path,
        "line": line_number,
        "column": 0,
        "severity": "warning",
        "rule_id": "CUDA-UNCHECKED-API",
        "message": f"{api[:-1]} return value not checked — CUDA errors silently ignored",
        "category": "QUALITY",
    }


# ── FILE DETECTION ─────────────────────────────────────────────────────────────

CUDA_EXTENSIONS = {".cu", ".cuh"}


def is_cuda_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in CUDA_EXTENSIONS


def find_cuda_files(project_path: str) -> list[str]:
    path = Path(project_path)
    ignore_dirs = {"build", "cmake-build-debug", "cmake-build-release", ".cache"}

    cuda_files = []
    for ext in CUDA_EXTENSIONS:
        for f in path.rglob(f"*{ext}"):
            if not any(d in f.parts for d in ignore_dirs):
                cuda_files.append(str(f))
    return cuda_files


def has_cuda_toolkit() -> bool:
    """CUDA toolkit available in system ?"""
    import shutil
    return shutil.which("nvcc") is not None or shutil.which("compute-sanitizer") is not None


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_cuda_tools(
    only: str | None = None,
    has_binary: bool = False,
    has_gpu: bool = False,
    skip_slow: bool = False,
) -> list[CudaToolConfig]:
    tools = CUDA_TOOLS.copy()

    if not has_binary:
        tools = [t for t in tools if not t.needs_compiled_binary]

    if not has_gpu:
        tools = [t for t in tools if not t.needs_gpu]

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"nsight-systems-cli", "compute-sanitizer-racecheck"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in CUDA_TOOLS}
