"""
Lyncus/config/config_loader.py
Lyncus.toml / pyproject.toml [tool.Lyncus] se config load karta hai.
Sab scan options yahan se aate hain — CLI flags override kar sakte hain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


# ── CONFIG DATACLASSES ────────────────────────────────────────────────────────


@dataclass
class ScanConfig:
    languages: list[str] = field(default_factory=lambda: ["auto"])
    severity: str = "all"
    output: str = "table"
    output_file: str | None = None
    ci_mode: bool = False
    parallel: bool = True
    timeout: int = 120  # seconds per tool


@dataclass
class ThresholdConfig:
    min_score: float = 70.0  # ✅ Fix #4: quality score threshold (CI mode ke liye)
    min_coverage: float = 80.0  # % branch coverage minimum (alag cheez!)
    max_complexity: int = 10  # cyclomatic complexity maximum
    mutation_score: float = 75.0  # % mutation score minimum
    max_line_length: int = 120  # max line length


@dataclass
class IgnoreConfig:
    paths: list[str] = field(
        default_factory=lambda: [
            "venv/",
            ".venv/",
            "node_modules/",
            ".git/",
            "dist/",
            "build/",
            "__pycache__/",
            "target/",
        ]
    )
    rules: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class HardcodeConfig:
    check_paths: bool = True
    check_credentials: bool = True
    check_magic_numbers: bool = True
    check_urls: bool = True
    check_todo: bool = True
    custom_patterns: list[str] = field(default_factory=list)


@dataclass
class ToolsConfig:
    skip_unavailable: bool = True
    skip_slow: bool = False
    extra_args: dict[str, list[str]] = field(default_factory=dict)
    # Per-tool timeouts — C++ tools naturally zyada time lete hain
    timeouts: dict[str, int] = field(default_factory=lambda: {
        "cpplint":    300,  # Large C++ projects mein bahut files scan hoti hain
        "lizard":     180,  # Complexity scan — poora project
        "flawfinder": 180,  # Security scan — recursive
        "cppcheck":   300,  # Deep static analysis
        "clang-tidy": 600,  # Bahut slow — compile + analyze
        "pytest-cov": 600,  # Full test suite + coverage — large projects mein zyada time
    })


@dataclass
class ReportConfig:
    html_file: str = "Lyncus-report.html"
    json_file: str = "Lyncus-report.json"
    sarif_file: str = "Lyncus-report.sarif"
    badge_file: str = "Lyncus-badge.svg"
    show_score: bool = True
    show_suggestions: bool = True


@dataclass
class LyncusConfig:
    version: str = "1.0"
    scan: ScanConfig = field(default_factory=ScanConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    ignore: IgnoreConfig = field(default_factory=IgnoreConfig)
    hardcode: HardcodeConfig = field(default_factory=HardcodeConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    report: ReportConfig = field(default_factory=ReportConfig)


# ── LOADER ────────────────────────────────────────────────────────────────────


def load_config(project_path: str | None = None, config_file: str | None = None) -> LyncusConfig:
    """
    Config load karo — priority order:
    1. --config flag se given file
    2. ./Lyncus.toml
    3. ./pyproject.toml [tool.Lyncus]
    4. ~/.Lyncus.toml (global)
    5. Default config
    """
    raw: dict[str, Any] = {}

    # Explicit config file
    if config_file and Path(config_file).exists():
        raw = _load_toml(config_file)

    # Project-level Lyncus.toml
    elif project_path:
        project_root = (
            Path(project_path) if Path(project_path).is_dir() else Path(project_path).parent
        )

        Lyncus_toml = project_root / "Lyncus.toml"
        pyproject = project_root / "pyproject.toml"

        if Lyncus_toml.exists():
            raw = _load_toml(str(Lyncus_toml))
        elif pyproject.exists():
            full = _load_toml(str(pyproject))
            raw = full.get("tool", {}).get("Lyncus", {})

    # Global ~/.Lyncus.toml
    if not raw:
        global_cfg = Path.home() / ".Lyncus.toml"
        if global_cfg.exists():
            raw = _load_toml(str(global_cfg))

    return _parse_config(raw)


def _load_toml(path: str) -> dict[str, Any]:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _parse_config(raw: dict[str, Any]) -> LyncusConfig:
    """Raw TOML dict se LyncusConfig banao."""
    cfg = LyncusConfig()

    # [Lyncus] section ke andar bhi ho sakta hai ya top-level bhi.
    # Merge strategy: agar [Lyncus] hai to usse base lo, phir top-level
    # sections ([scan], [thresholds], etc.) se override karo — dono cases handle ho jaate hain.
    Lyncus_block = raw.get("Lyncus", {})

    def _get(section: str) -> dict[str, Any]:
        """Top-level section pehle, phir [Lyncus] block ka fallback."""
        return raw.get(section) or Lyncus_block.get(section) or {}

    # version — [Lyncus] block mein hota hai
    cfg.version = Lyncus_block.get("version", raw.get("version", "1.0"))

    # [scan]
    scan_raw = _get("scan")
    cfg.scan = ScanConfig(
        languages=scan_raw.get("languages", ["auto"]),
        severity=scan_raw.get("severity", "all"),
        output=scan_raw.get("output", "table"),
        output_file=scan_raw.get("output_file", None),
        ci_mode=scan_raw.get("ci_mode", False),
        parallel=scan_raw.get("parallel", True),
        timeout=scan_raw.get("timeout", 120),
    )

    # [thresholds] — Named constants use karo, raw default values nahi
    _DEFAULT_MIN_SCORE = 70.0
    _DEFAULT_MIN_COVERAGE = 80.0
    _DEFAULT_MAX_COMPLEXITY = 10
    _DEFAULT_MUTATION_SCORE = 75.0
    _DEFAULT_MAX_LINE_LEN = 120
    thr_raw = _get("thresholds")
    cfg.thresholds = ThresholdConfig(
        min_score=float(thr_raw.get("min_score", _DEFAULT_MIN_SCORE)),
        min_coverage=float(thr_raw.get("min_coverage", _DEFAULT_MIN_COVERAGE)),
        max_complexity=int(thr_raw.get("max_complexity", _DEFAULT_MAX_COMPLEXITY)),
        mutation_score=float(thr_raw.get("mutation_score", _DEFAULT_MUTATION_SCORE)),
        max_line_length=int(thr_raw.get("max_line_length", _DEFAULT_MAX_LINE_LEN)),
    )

    # [ignore]
    ign_raw = _get("ignore")
    cfg.ignore = IgnoreConfig(
        paths=ign_raw.get("paths", IgnoreConfig().paths),
        rules=ign_raw.get("rules", []),
        files=ign_raw.get("files", []),
    )

    # [hardcode]
    hc_raw = _get("hardcode")
    cfg.hardcode = HardcodeConfig(
        check_paths=hc_raw.get("check_paths", True),
        check_credentials=hc_raw.get("check_credentials", True),
        check_magic_numbers=hc_raw.get("check_magic_numbers", True),
        check_urls=hc_raw.get("check_urls", True),
        check_todo=hc_raw.get("check_todo", True),
        custom_patterns=hc_raw.get("custom_patterns", []),
    )

    # [tools]
    # IMPORTANT: timeouts ka default ToolsConfig mein define hai (pytest-cov=300 etc.)
    # Agar TOML mein [tools.timeouts] nahi diya to default use karo — {} se override mat karo
    tools_raw = _get("tools")
    _default_timeouts = ToolsConfig().timeouts  # default timeouts preserve karo
    _custom_timeouts = tools_raw.get("timeouts", {})
    # Merge: defaults ke upar user overrides
    _merged_timeouts = {**_default_timeouts, **_custom_timeouts}
    cfg.tools = ToolsConfig(
        skip_unavailable=tools_raw.get("skip_unavailable", True),
        skip_slow=tools_raw.get("skip_slow", False),
        extra_args=tools_raw.get("extra_args", {}),
        timeouts=_merged_timeouts,
    )

    # [report]
    rep_raw = _get("report")
    cfg.report = ReportConfig(
        html_file=rep_raw.get("html_file", "Lyncus-report.html"),
        json_file=rep_raw.get("json_file", "Lyncus-report.json"),
        sarif_file=rep_raw.get("sarif_file", "Lyncus-report.sarif"),
        badge_file=rep_raw.get("badge_file", "Lyncus-badge.svg"),
        show_score=rep_raw.get("show_score", True),
        show_suggestions=rep_raw.get("show_suggestions", True),
    )

    return cfg


# ── TOML WRITER (init command ke liye) ───────────────────────────────────────

DEFAULT_TOML = """\
# 🐺 Lyncus Configuration File
# Docs: https://github.com/yourname/Lyncus#configuration

[Lyncus]
version = "1.0"

[scan]
languages = ["auto"]        # auto | python | cpp | rust | go | js | java | csharp | ruby | php
severity  = "all"           # all | critical | warning | info
output    = "table"         # table | json | html | sarif
parallel  = true            # Run Tools parallel  (faster)
timeout   = 120             # Seconds per tool

[thresholds]
min_score       = 70        # Quality score minimum (%) — CI mode fail threshold
min_coverage    = 80        # Branch coverage minimum (%) — alag cheez!
max_complexity  = 10        # Cyclomatic complexity maximum
mutation_score  = 75        # Mutation testing score minimum (%)
max_line_length = 120       # Max line length

[ignore]
paths = [
  "venv/", ".venv/", "node_modules/", ".git/",
  "dist/", "build/", "__pycache__/", "target/",
]
rules = []                  # Specific rule IDs ignore : ["HC001", "FT001"]
files = []                  # Specific files ignore : ["migrations/*.py"]

[hardcode]
check_paths         = true  # /home/, C:\\Users jaise paths
check_credentials   = true  # password=, api_key=, secret=
check_magic_numbers = true  # Magic numbers: = 42, = 9999
check_urls          = true  # localhost, 192.168. jaise URLs
check_todo          = true  # TODO, FIXME, HACK, XXX comments
custom_patterns     = []    # Apne regex patterns add karo

[tools]
skip_unavailable = true     # Missing tools silently skip
skip_slow        = false    # Slow tools (valgrind, stryker) skip

[report]
html_file  = "Lyncus-report.html"
json_file  = "Lyncus-report.json"
sarif_file = "Lyncus-report.sarif"
badge_file = "Lyncus-badge.svg"
show_score       = true
show_suggestions = true
"""


def write_default_config(output_path: str = "Lyncus.toml") -> None:
    """Default Lyncus.toml file create karo."""
    Path(output_path).write_text(DEFAULT_TOML, encoding="utf-8")
