"""
C++ Language Checks — clang-tidy, cppcheck, flawfinder, lizard, AddressSanitizer
C++ tools individual files ya directories dono pe chalte hain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_ARGUMENT = "{path}"


@dataclass
class CppToolConfig:
    name: str
    command: list[str]
    check_type: str
    output_format: str
    description: str
    min_version: str
    install_cmd: str
    needs_compile_db: bool = False   # compile_commands.json chahiye


# ── C++ TOOL DEFINITIONS ──────────────────────────────────────────────────────

CPP_TOOLS: list[CppToolConfig] = [

    CppToolConfig(
        name="cppcheck",
        command=[
            "cppcheck",
            "--enable=all",
            "--inconclusive",
            "--xml",
            "--suppress=missingIncludeSystem",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="xml",
        description="Static analysis — memory leaks, null pointers, undefined behavior",
        min_version="2.14.0",
        install_cmd=(
            "apt-get install -y cppcheck / brew install cppcheck / "
            "winget install --id Cppcheck.Cppcheck --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install cppcheck -y"
        ),
    ),

    CppToolConfig(
        name="clang-tidy",
        command=[
            "clang-tidy",
            _PATH_ARGUMENT,
            "--checks=*",
            "--warnings-as-errors=*",
            "--",
            "-std=c++17",
        ],
        check_type="quality",
        output_format="text",
        description="Clang-based linter — modern C++ patterns, style, performance",
        min_version="18.0.0",
        install_cmd=(
            "apt-get install -y clang-tidy / brew install llvm / "
            "winget install --id LLVM.LLVM --exact --silent "
            "--accept-package-agreements --accept-source-agreements / choco install llvm -y"
        ),
        needs_compile_db=True,
    ),

    CppToolConfig(
        name="flawfinder",
        command=[
            "flawfinder",
            "--dataonly",
            "--quiet",
            _PATH_ARGUMENT,
        ],
        check_type="security",
        output_format="text",
        description="Security scanner — buffer overflows, format strings, race conditions",
        min_version="2.0.19",
        install_cmd="pip install flawfinder>=2.0",
    ),

    CppToolConfig(
        name="lizard",
        command=[
            "lizard",
            _PATH_ARGUMENT,
            "--CCN", "25",       # C++ ke liye realistic threshold (Python 10, C++ 25)
            "--length", "150",   # C++ functions naturally longer hoti hain
            "--arguments", "10", # Max arguments
            "-w",                # Warnings only
        ],
        check_type="complexity",
        output_format="text",
        description="Complexity analyzer — CCN, function length, argument count",
        min_version="1.17.10",
        install_cmd="pip install lizard>=1.17",
    ),

    CppToolConfig(
        name="cpplint",
        command=[
            "cpplint",
            "--recursive",
            _PATH_ARGUMENT,
        ],
        check_type="quality",
        output_format="text",
        description="Google C++ style guide checker",
        min_version="1.6.1",
        install_cmd="pip install cpplint>=1.6",
    ),

    CppToolConfig(
        name="valgrind",
        command=[
            "valgrind",
            "--leak-check=full",
            "--show-leak-kinds=all",
            "--track-origins=yes",
            "--xml=yes",
            "--xml-file=/tmp/valgrind_out.xml",
            "{binary}",
        ],
        check_type="memory",
        output_format="xml",
        description="Memory error detector — leaks, invalid reads/writes, use-after-free",
        min_version="3.23.0",
        install_cmd="# Ubuntu: apt install valgrind\n# macOS: brew install valgrind (limited)\n# Windows: WSL use karo",
    ),
]


# ── CPPCHECK XML PARSER ───────────────────────────────────────────────────────

def parse_cppcheck_xml(xml_output: str) -> list[dict[str, Any]]:
    """cppcheck --xml output parse karo."""
    from defusedxml import ElementTree as ET
    issues = []

    try:
        # stderr mein aata hai cppcheck ka XML
        root = ET.fromstring(xml_output)
        errors = root.findall(".//error")

        for error in errors:
            error_id = error.get("id", "")
            severity = error.get("severity", "warning")
            msg = error.get("msg", "")

            # Location
            location = error.find("location")
            file_path = location.get("file", "") if location is not None else ""
            line = int(location.get("line", "0")) if location is not None else 0
            col = int(location.get("column", "0")) if location is not None else 0

            # Skip non-issues
            if error_id in ("missingIncludeSystem", "unmatchedSuppression"):
                continue

            issues.append({
                "file":     file_path,
                "line":     line,
                "column":   col,
                "severity": _cppcheck_severity(severity),
                "rule_id":  f"CPP-{error_id.upper()}",
                "message":  msg,
                "category": _cppcheck_category(error_id),
            })

    except ET.ParseError:
        # XML parse error — text output try karo
        pass

    return issues


def _cppcheck_severity(sev: str) -> str:
    sev_map = {
        "error":       "critical",
        "warning":     "warning",
        "style":       "info",
        "performance": "warning",
        "portability": "info",
        "information": "info",
    }
    return sev_map.get(sev, "warning")


def _cppcheck_category(error_id: str) -> str:
    memory_ids = {
        "memleak", "resourceLeak", "leakReturnValNotUsed",
        "nullPointer", "uninitvar", "useInitializationOrder",
        "doubleFree", "deallocuse", "danglingLifetime",
    }
    security_ids = {
        "bufferAccessOutOfBounds", "outOfBounds", "arrayIndexOutOfBounds",
        "stringLiteralWritten", "formatString", "invalidFormatStr",
    }
    quality_ids = {
        "unusedVariable", "unusedFunction", "deadCode",
        "redundantAssignment", "duplicateExpression",
    }

    if error_id in memory_ids:
        return "MEMORY"
    if error_id in security_ids:
        return "SECURITY"
    if error_id in quality_ids:
        return "DEADCODE"
    return "QUALITY"


# ── CLANG-TIDY PARSER ─────────────────────────────────────────────────────────

def parse_clang_tidy_output(output: str) -> list[dict[str, Any]]:
    """clang-tidy text output parse karo."""
    issues = []
    for raw_line in output.splitlines():
        raw_line = raw_line.strip()
        before_check, separator, check = raw_line.rpartition(" [")
        if not separator or not check.endswith("]"):
            continue
        location, separator, msg = before_check.rpartition(": ")
        if not separator:
            continue
        fields = location.rsplit(":", 3)
        if len(fields) != 4:
            continue
        file, line, col, level = fields
        level = level.strip()
        if (
            not line.isdigit()
            or not col.isdigit()
            or level not in ("warning", "error", "note")
        ):
            continue
        check = check[:-1]

        # Notes ignore karo (context messages hain)
        if level == "note":
            continue

        issues.append({
            "file":     file.strip(),
            "line":     int(line),
            "column":   int(col),
            "severity": "critical" if level == "error" else "warning",
            "rule_id":  f"CLANG-{check.upper().replace('-', '_')}",
            "message":  msg.strip(),
            "category": _clang_tidy_category(check),
        })

    return issues


def _clang_tidy_category(check_name: str) -> str:
    cat_map = {
        "clang-diagnostic":  "QUALITY",
        "cppcoreguidelines": "QUALITY",
        "modernize":         "QUALITY",
        "performance":       "PERF",
        "readability":       "STYLE",
        "bugprone":          "BUGPRONE",
        "cert":              "SECURITY",
        "concurrency":       "BUGPRONE",
        "portability":       "QUALITY",
        "google":            "STYLE",
        "hicpp":             "QUALITY",
        "llvm":              "STYLE",
        "abseil":            "QUALITY",
        "android":           "SECURITY",
        "fuchsia":           "QUALITY",
        "linuxkernel":       "QUALITY",
        "objc":              "QUALITY",
        "zircon":            "QUALITY",
        "misc":              "QUALITY",
    }
    for prefix, cat in cat_map.items():
        if check_name.startswith(prefix):
            return cat
    return "QUALITY"


# ── FLAWFINDER PARSER ─────────────────────────────────────────────────────────

def parse_flawfinder_output(output: str) -> list[dict[str, Any]]:
    """flawfinder output parse karo."""
    issues = []
    for raw_line in output.splitlines():
        location, separator, detail = raw_line.rpartition(": [")
        if not separator:
            continue
        file, separator, line = location.rpartition(":")
        if not separator or not line.isdigit():
            continue
        risk, separator, detail = detail.partition("] ")
        if not separator:
            continue
        func, separator, detail = detail.partition(") ")
        if not separator or not func.startswith("("):
            continue
        _, separator, msg = detail.partition(": ")
        if not separator:
            continue
        try:
            risk_int = int(risk)
        except ValueError:
            continue
        func = func[1:]

        issues.append({
            "file":     file.strip(),
            "line":     int(line),
            "column":   0,
            "severity": _flawfinder_severity(risk_int),
            "rule_id":  f"FW-{func.upper()}",
            "message":  f"{func}() — {msg.strip()}",
            "category": "SECURITY",
        })

    return issues


def _flawfinder_severity(risk_level: int) -> str:
    if risk_level >= 4:
        return "critical"
    if risk_level >= 2:
        return "warning"
    return "info"


# ── LIZARD PARSER ─────────────────────────────────────────────────────────────

def parse_lizard_output(output: str) -> list[dict[str, Any]]:
    """lizard output parse karo."""
    issues = []
    for raw_line in output.splitlines():
        location, separator, msg = raw_line.rpartition(": warning:")
        if not separator:
            continue
        file, separator, line = location.rpartition(":")
        if not separator or not line.isdigit():
            continue
        issues.append({
            "file":     file.strip(),
            "line":     int(line),
            "column":   0,
            "severity": "warning",
            "rule_id":  "LIZ-COMPLEXITY",
            "message":  msg.strip(),
            "category": "COMPLEXITY",
        })

    return issues


# ── FILE EXTENSIONS ───────────────────────────────────────────────────────────

CPP_EXTENSIONS = {".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx", ".hh"}


def is_cpp_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in CPP_EXTENSIONS


def find_cpp_files(project_path: str) -> list[str]:
    """Project mein sab C++ files dhundo."""
    path = Path(project_path)
    cpp_files: list[str] = []

    for ext in CPP_EXTENSIONS:
        cpp_files.extend(str(f) for f in path.rglob(f"*{ext}"))

    # Build/cmake dirs ignore karo
    ignore_dirs = {"build", "cmake-build-debug", "cmake-build-release", ".cache"}
    return [f for f in cpp_files if not any(d in f for d in ignore_dirs)]


def has_compile_db(project_path: str) -> bool:
    """compile_commands.json available hai?"""
    return (Path(project_path) / "compile_commands.json").exists()


# ── CMAKE BUILD SYSTEM DETECT ─────────────────────────────────────────────────

def detect_build_system(project_path: str) -> str | None:
    """C++ project ka build system detect karo."""
    path = Path(project_path)
    if (path / "CMakeLists.txt").exists():
        return "cmake"
    if (path / "Makefile").exists() or (path / "makefile").exists():
        return "make"
    if (path / "meson.build").exists():
        return "meson"
    if (path / "BUILD").exists() or (path / "BUILD.bazel").exists():
        return "bazel"
    if (path / "WORKSPACE").exists():
        return "bazel"
    return None


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_cpp_tools(
    only: str | None = None,
    skip_slow: bool = False,
    has_binary: bool = False,
) -> list[CppToolConfig]:
    """
    C++ tools ki filtered list.

    Args:
        only: quality / security / complexity / memory
        skip_slow: valgrind (bahut slow) skip karo
        has_binary: compiled binary available hai (valgrind ke liye)
    """
    tools = CPP_TOOLS.copy()

    # Valgrind ko compiled binary chahiye
    if not has_binary:
        tools = [t for t in tools if t.name != "valgrind"]

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow = {"valgrind", "clang-tidy"}
        tools = [t for t in tools if t.name not in slow]

    return tools


def get_install_commands() -> dict[str, str]:
    return {t.name: t.install_cmd for t in CPP_TOOLS}
