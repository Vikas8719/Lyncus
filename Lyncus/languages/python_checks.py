"""
Python Language Checks — ruff, mypy, bandit, vulture, mutmut, radon, pip-audit
Har tool ki exact command, arguments aur output format yahan define hain.
"""

from __future__ import annotations

from dataclasses import dataclass

_PATH_ARGUMENT = "{path}"


@dataclass
class PythonToolConfig:
    name: str
    command: list[str]
    check_type: str        # quality / security / deadcode / complexity / deps / faketests
    output_format: str     # text / json
    description: str
    min_version: str
    install_cmd: str


# ── PYTHON TOOL DEFINITIONS ───────────────────────────────────────────────────

PYTHON_TOOLS: list[PythonToolConfig] = [

    PythonToolConfig(
        name="ruff",
        command=["ruff", "check", _PATH_ARGUMENT, "--output-format", "text", "--no-cache"],
        check_type="quality",
        output_format="text",
        description="Fast Python linter — syntax, style, unused imports",
        min_version="0.4.0",
        install_cmd="pip install ruff>=0.4",
    ),

    PythonToolConfig(
        name="mypy",
        command=[
            "mypy", _PATH_ARGUMENT,
            "--ignore-missing-imports",
            "--no-error-summary",
            "--show-column-numbers",
            "--show-error-codes",
        ],
        check_type="quality",
        output_format="text",
        description="Static type checker — type mismatch, missing annotations",
        min_version="1.10.0",
        install_cmd="pip install mypy>=1.10",
    ),

    PythonToolConfig(
        name="bandit",
        command=[
            "bandit", "-r", _PATH_ARGUMENT,
            "--severity-level", "low",
            "--confidence-level", "low",
            "-q",
        ],
        check_type="security",
        output_format="text",
        description="Security issues — SQL injection, hardcoded passwords, eval use",
        min_version="1.7.9",
        install_cmd="pip install bandit>=1.7",
    ),

    PythonToolConfig(
        name="vulture",
        command=["vulture", _PATH_ARGUMENT, "--min-confidence", "70"],
        check_type="deadcode",
        output_format="text",
        description="Dead code detector — unused functions, variables, imports",
        min_version="2.11.0",
        install_cmd="pip install vulture>=2.11",
    ),

    PythonToolConfig(
        name="radon",
        command=["radon", "cc", _PATH_ARGUMENT, "-s", "-a", "-nb"],
        check_type="complexity",
        output_format="text",
        description="Cyclomatic complexity — bahut complex functions pakadta hai",
        min_version="6.0.0",
        install_cmd="pip install radon>=6.0",
    ),

    PythonToolConfig(
        name="pip-audit",
        command=["pip-audit", "--format", "columns", "--progress-spinner", "off"],
        check_type="deps",
        output_format="text",
        description="Dependency vulnerability scanner — CVE check karta hai",
        min_version="2.7.0",
        install_cmd="pip install pip-audit>=2.7",
    ),

    PythonToolConfig(
        name="mutmut",
        command=["mutmut", "run"],
        check_type="faketests",
        output_format="text",
        description="Mutation testing — fake/weak tests pakadta hai",
        min_version="3.0.0",
        install_cmd="pip install 'mutmut>=3.0,<4'",
    ),
]


# ── RUFF RULES MAPPING ────────────────────────────────────────────────────────
# Ruff rule code → human-friendly category

RUFF_CATEGORY_MAP: dict[str, str] = {
    "E":  "STYLE",       # pycodestyle errors
    "W":  "STYLE",       # pycodestyle warnings
    "F":  "QUALITY",     # pyflakes
    "I":  "IMPORTS",     # isort
    "N":  "NAMING",      # pep8-naming
    "UP": "UPGRADE",     # pyupgrade — purani syntax
    "B":  "BUGPRONE",    # flake8-bugbear
    "C":  "COMPLEXITY",  # mccabe complexity
    "S":  "SECURITY",    # flake8-bandit
    "T":  "PRINT",       # flake8-print (print statements)
    "Q":  "QUOTES",      # flake8-quotes
    "RUF": "RUFF",       # ruff-specific rules
    "ANN": "TYPES",      # annotations
    "D":  "DOCSTRING",   # pydocstyle
    "ERA": "DEADCODE",   # eradicate (commented-out code)
    "PL": "PYLINT",      # pylint rules
    "PT": "PYTEST",      # flake8-pytest-style
    "SIM": "SIMPLIFY",   # flake8-simplify
    "TID": "TIDY",       # flake8-tidy-imports
    "TCH": "TYPECHECK",  # flake8-type-checking
    "ARG": "UNUSED",     # flake8-unused-arguments
    "PTH": "PATHLIB",    # flake8-use-pathlib
    "FLY": "FSTRING",    # flynt — f-string conversion
    "PERF": "PERF",      # perflint
    "FURB": "REFACTOR",  # refurb
    "LOG": "LOGGING",    # flake8-logging
    "RET": "RETURN",     # flake8-return
}


def get_ruff_category(rule_code: str) -> str:
    """Ruff rule code se category nikalo."""
    for prefix, category in sorted(RUFF_CATEGORY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if rule_code.startswith(prefix):
            return category
    return "QUALITY"


def get_ruff_severity(rule_code: str) -> str:
    """Ruff rule code se severity nikalo."""
    # Security aur bug-prone rules critical hain
    critical_prefixes = {"S", "B", "E9", "F8"}
    warning_prefixes  = {"F", "W", "B", "N", "UP", "PL", "SIM", "RET"}

    for prefix in critical_prefixes:
        if prefix == "S" and rule_code.startswith("SIM"):
            continue
        if rule_code.startswith(prefix):
            return "critical"
    for prefix in warning_prefixes:
        if rule_code.startswith(prefix):
            return "warning"
    return "info"


# ── MYPY ERROR CODES ──────────────────────────────────────────────────────────

MYPY_SEVERITY_MAP: dict[str, str] = {
    "error":   "critical",
    "warning": "warning",
    "note":    "info",
}

MYPY_CATEGORY_MAP: dict[str, str] = {
    "return-value":      "TYPE",
    "arg-type":          "TYPE",
    "assignment":        "TYPE",
    "attr-defined":      "TYPE",
    "name-defined":      "QUALITY",
    "import":            "IMPORTS",
    "no-untyped-def":    "TYPES",
    "no-untyped-call":   "TYPES",
    "union-attr":        "TYPE",
    "operator":          "TYPE",
    "index":             "TYPE",
    "misc":              "QUALITY",
    "override":          "TYPE",
    "type-arg":          "TYPE",
    "valid-type":        "TYPE",
}


def get_mypy_category(error_code: str) -> str:
    """Mypy error code se category nikalo."""
    return MYPY_CATEGORY_MAP.get(error_code, "TYPE")


# ── BANDIT SEVERITY ───────────────────────────────────────────────────────────

BANDIT_SEVERITY_MAP: dict[str, str] = {
    "HIGH":   "critical",
    "MEDIUM": "warning",
    "LOW":    "info",
}

# Bandit test IDs jo common hain
BANDIT_RULE_DESCRIPTIONS: dict[str, str] = {
    "B101": "assert statement use — production mein disable ho sakta hai",
    "B102": "exec() use — dangerous code execution",
    "B103": "File permission too permissive",
    "B104": "Possible binding to all interfaces",
    "B105": "Hardcoded password string",
    "B106": "Hardcoded password as function argument",
    "B107": "Hardcoded password as default argument",
    "B108": "Probable insecure usage of temp file",
    "B110": "Try/except/pass detected — error silently ignored",
    "B112": "Try/except/continue detected",
    "B201": "Flask debug mode enabled",
    "B301": "Pickle use — arbitrary code execution risk",
    "B302": "marshal.loads use",
    "B303": "MD5/SHA1 use — weak hash",
    "B304": "Cipher modes without IV",
    "B305": "Cipher with ECB mode",
    "B306": "mktemp use — insecure temp file",
    "B307": "eval() use — code injection risk",
    "B308": "mark_safe() use — XSS risk",
    "B310": "urllib.urlopen use — SSRF risk",
    "B311": "Standard pseudo-random generator — not cryptographically secure",
    "B312": "telnetlib use — plaintext protocol",
    "B313": "xml.etree.ElementTree — XXE vulnerable",
    "B314": "xml.etree.cElementTree — XXE vulnerable",
    "B315": "xml.etree.ElementTree.parse — XXE vulnerable",
    "B316": "xml.etree.cElementTree.parse — XXE vulnerable",
    "B317": "xml.etree.ElementTree.iterparse — XXE vulnerable",
    "B318": "xml.etree.ElementTree.XMLParser — XXE vulnerable",
    "B319": "xml.sax.make_parser — XXE vulnerable",
    "B320": "xml.dom.expatbuilder use — XXE vulnerable",
    "B321": "FTP use — plaintext protocol",
    "B322": "input() Python 2 vulnerability",
    "B323": "unverified SSL context",
    "B324": "hashlib with weak algorithm",
    "B325": "tempnam use — deprecated",
    "B401": "import telnetlib — insecure",
    "B402": "import ftplib — plaintext",
    "B403": "import pickle — code exec risk",
    "B404": "import subprocess — potential injection",
    "B405": "import xml.etree — XXE risk",
    "B501": "SSL with no cert verification",
    "B502": "ssl._create_unverified_context use",
    "B503": "ssl.wrap_socket without cert required",
    "B504": "ssl context with no TLS/SSL",
    "B505": "Weak cryptographic key",
    "B506": "yaml.load use — code exec risk",
    "B507": "Paramiko host key not verified",
    "B601": "Shell injection via paramiko",
    "B602": "subprocess with shell=True",
    "B603": "subprocess without shell — ok but check input",
    "B604": "Function call with shell=True",
    "B605": "os.system use",
    "B606": "os.popen use",
    "B607": "Starting process with partial path",
    "B608": "SQL injection risk",
    "B609": "Wildcard injection",
    "B610": "Django extra use — SQL injection",
    "B611": "Django RawSQL use — SQL injection",
    "B701": "jinja2 autoescape disabled",
    "B702": "mako template use",
    "B703": "Django mark_safe use",
}


def get_bandit_description(rule_id: str) -> str:
    """Bandit rule ID se readable description nikalo."""
    return BANDIT_RULE_DESCRIPTIONS.get(rule_id, f"Security issue: {rule_id}")


# ── RADON COMPLEXITY ──────────────────────────────────────────────────────────

RADON_GRADE_SEVERITY: dict[str, str] = {
    "A": "info",      # 1-5: simple
    "B": "info",      # 6-10: ok
    "C": "warning",   # 11-15: moderate complexity — refactor consider karo
    "D": "warning",   # 16-20: high complexity — refactor karo
    "E": "critical",  # 21-25: very high — production mein acceptable nahi
    "F": "critical",  # 26+: extreme complexity — production unacceptable
}

RADON_GRADE_DESCRIPTION: dict[str, str] = {
    "A": "Simple function",
    "B": "Acceptable complexity",
    "C": "Moderate complexity — refactor consider karo",
    "D": "High complexity — refactor karo",
    "E": "Very high complexity — refactor karo",
    "F": "Extreme complexity — production ke liye unacceptable",
}


def get_radon_severity(grade: str) -> str:
    return RADON_GRADE_SEVERITY.get(grade.upper(), "info")


def get_radon_description(grade: str) -> str:
    return RADON_GRADE_DESCRIPTION.get(grade.upper(), f"Complexity grade: {grade}")


# ── VULTURE CONFIDENCE ────────────────────────────────────────────────────────

def get_vulture_severity(confidence: int) -> str:
    """Vulture confidence percentage se severity."""
    if confidence >= 90:
        return "critical"
    if confidence >= 70:
        return "warning"
    return "info"


# ── TOOL LIST GETTER ──────────────────────────────────────────────────────────

def get_python_tools(
    only: str | None = None,
    skip_slow: bool = False,
) -> list[PythonToolConfig]:
    """
    Python tools ki filtered list return karo.

    Args:
        only: Sirf ek type ke tools — quality/security/deadcode/complexity/deps
        skip_slow: Slow tools (mutmut) skip karo

    Returns:
        List of PythonToolConfig
    """
    tools = PYTHON_TOOLS.copy()

    if only:
        tools = [t for t in tools if t.check_type == only]

    if skip_slow:
        slow_tools = {"mutmut"}
        tools = [t for t in tools if t.name not in slow_tools]

    return tools


def get_install_commands() -> dict[str, str]:
    """Sab Python tools ke install commands."""
    return {t.name: t.install_cmd for t in PYTHON_TOOLS}
