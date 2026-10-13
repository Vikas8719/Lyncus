"""
Hardcoded Value Rules — Sab languages ke liye regex patterns.
Ye Lyncus ka apna engine hai jo kisi bhi tool pe depend nahi karta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class HardcodeMatch:
    file: str
    rule_id: str
    category: str
    description: str
    line: int
    column: int
    matched_text: str
    severity: str  # critical / warning / info


# ── CREDENTIAL PATTERNS ─────────────────────────────────────────────────────
#
# Multi-language support ke liye patterns:
#   Python/JS/Go:  password = "val"          (key = "val")
#   Rust:          const DB_PASSWORD: &str = "val"   (TYPE_ANNOTATION ke baad =)
#   Swift/Kotlin:  let apiKey = "val"        (let/var + name = "val")
#   C#:            string password = "val";  (type + name = "val")
#   Java:          String PASSWORD = "val";  (type + name = "val")
#
# Pattern logic:
#   \w+ matches RUST ke const name ya kisi bhi language ka variable naam
#   (?:[:\s]\s*\S+\s*)? optional type annotation (Rust: `: &str`, C#: String type already consumed)
#   \s*=\s* assignment operator
#
CREDENTIAL_PATTERNS: list[tuple[str, str, str]] = [
    # password / passwd / pwd — sab languages + camelCase (adminPassword, userPassword, etc.)
    # Matches: password = "x", DB_PASSWORD: &str = "x", let adminPassword = "x"
    (
        r'(?i)(?:^|[_\W])(?:admin|user|new|old|my|db|root)?(?:password|passwd|pwd)(?:[_\W]|$)(?:[^=\n]{0,30}?)=\s*["\'][^"\']{3,}["\']',
        "HC001",
        "Hardcoded password detected",
    ),
    # api_key / apikey / api-key / APIKEY / camelCase apiKey
    (
        r'(?i)\b(api[_\-]?key|apikey)\b(?:[^=\n]{0,30}?)=\s*["\'][^"\']{8,}["\']',
        "HC002",
        "Hardcoded API key detected",
    ),
    # secret / secret_key / JWT_SECRET / jwtSecret / appSecret
    (
        r'(?i)\b(secret[_\-]?key?|jwt[_\-]?secret|app[_\-]?secret)\b(?:[^=\n]{0,30}?)=\s*["\'][^"\']{8,}["\']',
        "HC003",
        "Hardcoded secret detected",
    ),
    # auth_token / access_token / api_token / bearerToken
    (
        r'(?i)\b(auth[_\-]?token|access[_\-]?token|api[_\-]?token|bearer[_\-]?token)\b(?:[^=\n]{0,30}?)=\s*["\'][^"\']{8,}["\']',
        "HC004",
        "Hardcoded token detected",
    ),
    # db_password / database_password / DB_PASS / DbPassword (camelCase)
    (
        r'(?i)\b(db[_\-]?pass(?:word)?|database[_\-]?pass(?:word)?)\b(?:[^=\n]{0,30}?)=\s*["\'][^"\']{3,}["\']',
        "HC005",
        "Hardcoded database password detected",
    ),
    # APISecret, api_secret, APP_SECRET — standalone "secret" word (Go/Rust const style)
    (
        r'(?i)\b(\w*[_]?secret[_]?\w*)\b(?:[^=\n]{0,20}?)=\s*["\'][^"\']{8,}["\']',
        "HC008",
        "Hardcoded secret value detected",
    ),
    # Connection strings — postgres://, mysql://, mongodb://, redis:// with credentials
    (
        r'["\'](?:postgres|mysql|mongodb|redis|mssql|oracle)://[^"\']*:[^"\']+@[^"\']+["\']',
        "HC009",
        "Hardcoded database connection string with credentials",
    ),
    # AWS credentials
    (
        r'(?i)\b(aws[_\-]?secret|aws[_\-]?key|aws[_\-]?access)\b(?:[^=\n]{0,30}?)=\s*["\'][^"\']{8,}["\']',
        "HC006",
        "Hardcoded AWS credential detected",
    ),
    # private_key / credentials / client_secret / oauth_secret
    (
        r'(?i)\b(private[_\-]?key|credentials?|client[_\-]?secret|oauth[_\-]?secret)\b(?:[^=\n]{0,30}?)=\s*["\'][^"\']{8,}["\']',
        "HC007",
        "Hardcoded credential detected",
    ),
]

# ── PATH PATTERNS ────────────────────────────────────────────────────────────
PATH_PATTERNS: list[tuple[str, str, str]] = [
    (
        r'["\'][/\\]home[/\\][a-zA-Z0-9_.-]+[/\\][^"\']*["\']',
        "HC010",
        "Hardcoded Unix home path detected",
    ),
    (
        r'["\']C:[/\\][Uu]sers[/\\][a-zA-Z0-9_.-]+[/\\][^"\']*["\']',
        "HC011",
        "Hardcoded Windows user path detected",
    ),
    (r'["\'][/\\]root[/\\][^"\']*["\']', "HC012", "Hardcoded /root path detected"),
    (
        r'["\'][/\\]tmp[/\\][a-zA-Z0-9_.-]+[^"\']*["\']',
        "HC013",
        "Hardcoded /tmp path — use tempfile module",
    ),
    (r'["\'][/\\]var[/\\]log[/\\][^"\']*["\']', "HC014", "Hardcoded log path detected"),
    (r'["\'][/\\]etc[/\\][^"\']*["\']', "HC015", "Hardcoded /etc path detected"),
]

# ── URL / HOST PATTERNS ──────────────────────────────────────────────────────
#
# Multi-language support:
#   Python/Go:   url = "http://localhost:8080"
#   Rust:        const URL: &str = "http://192.168.x.x/..."
#   Swift:       let serverURL = "http://10.0.0.5:3000/..."
#   C#/Java:     string BaseUrl = "http://localhost/..."
#
URL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r'["\']https?://localhost[:/][^"\']*["\']',
        "HC020",
        "Hardcoded localhost URL — use config/env variable",
    ),
    (
        r'["\']https?://127\.0\.0\.1[:/][^"\']*["\']',
        "HC021",
        "Hardcoded 127.0.0.1 URL detected",
    ),
    (
        r'["\']https?://192\.168\.\d{1,3}\.\d{1,3}[^"\']*["\']',
        "HC022",
        "Hardcoded private IP address detected",
    ),
    (
        r'["\']https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}[^"\']*["\']',
        "HC023",
        "Hardcoded private network IP detected",
    ),
    (
        r'["\']https?://172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}[^"\']*["\']',
        "HC024",
        "Hardcoded private network IP (172.16-31.x.x) detected",
    ),
]

# ── MAGIC NUMBER PATTERNS ────────────────────────────────────────────────────
MAGIC_NUMBER_PATTERNS: list[tuple[str, str, str]] = [
    # 3+ digit numbers jo variable assignment mein hain
    (
        r"(?<![.\d])\b([0-9]{4,})\b(?![.\d])",
        "HC030",
        "Magic number detected — naam wala constant use karo",
    ),
    # Float magic numbers
    (r"=\s*0\.[0-9]{4,}", "HC031", "Magic float constant — naam wala constant use karo"),
    # Port numbers hardcoded
    (r"(?i)(port)\s*=\s*\d{4,5}", "HC032", "Hardcoded port number — use config/env variable"),
]

# ── TODO / FIXME PATTERNS ────────────────────────────────────────────────────
TODO_PATTERNS: list[tuple[str, str, str]] = [
    (r"(?i)#\s*(TODO|FIXME|HACK|XXX|BUG|TEMP)\b", "HC040", "Unresolved TODO/FIXME marker found"),
    (r"(?i)//\s*(TODO|FIXME|HACK|XXX|BUG|TEMP)\b", "HC041", "Unresolved TODO/FIXME marker found"),
    (r"(?i)/\*\s*(TODO|FIXME|HACK|XXX)\b", "HC042", "Unresolved TODO/FIXME in block comment"),
]

# ── DATABASE PATTERNS ────────────────────────────────────────────────────────
DATABASE_PATTERNS: list[tuple[str, str, str]] = [
    (
        r'(?i)(host|db_host|database_host)\s*=\s*["\'][a-zA-Z0-9._-]{3,}["\']',
        "HC050",
        "Hardcoded database host — use env variable",
    ),
    (
        r'(?i)(connection_string|conn_str|db_url)\s*=\s*["\'][^"\']{10,}["\']',
        "HC051",
        "Hardcoded connection string detected",
    ),
]


def scan_file_for_hardcode(
    file_path: str,
    content: str,
    check_credentials: bool = True,
    check_paths: bool = True,
    check_urls: bool = True,
    check_magic_nums: bool = True,
) -> list[HardcodeMatch]:
    """
    Ek file ka content scan karo hardcoded values ke liye.

    Args:
        file_path: File ka path (sirf display ke liye)
        content: File ka poora content (string)
        check_*: Kaun se checks enable hain

    Returns:
        List of HardcodeMatch — sab problems, per-line deduplicated
    """
    matches: list[HardcodeMatch] = []
    lines = content.splitlines()

    def _scan_patterns(
        patterns: list[tuple[str, str, str]],
        severity: str,
        category: str,
    ) -> None:
        for pattern, rule_id, description in patterns:
            compiled = re.compile(pattern)
            for line_num, line_text in enumerate(lines, start=1):
                for m in compiled.finditer(line_text):
                    matches.append(
                        HardcodeMatch(
                            file=file_path,
                            rule_id=rule_id,
                            category=category,
                            description=description,
                            line=line_num,
                            column=m.start() + 1,
                            matched_text=m.group()[:60],
                            severity=severity,
                        )
                    )

    if check_credentials:
        _scan_patterns(CREDENTIAL_PATTERNS, "critical", "CREDENTIAL")
        _scan_patterns(DATABASE_PATTERNS, "critical", "DATABASE")

    if check_paths:
        _scan_patterns(PATH_PATTERNS, "warning", "HARDPATH")

    if check_urls:
        _scan_patterns(URL_PATTERNS, "warning", "HARDURL")

    if check_magic_nums:
        _scan_patterns(MAGIC_NUMBER_PATTERNS, "info", "MAGICNUM")

    # Always scan marker patterns.
    _scan_patterns(TODO_PATTERNS, "info", "TODO")

    return _deduplicate_matches(matches)


# ── RULE PRIORITY — specificity order (lower index = more specific = wins) ───
# Zyada specific rule ID ko prefer karo jab same line pe multiple CREDENTIAL matches hon.
# Example: DB_PASSWORD line pe HC005 (db_password) > HC001 (generic password)
_CREDENTIAL_PRIORITY: list[str] = [
    "HC009",  # connection string (most specific — full URL)
    "HC006",  # AWS
    "HC007",  # private_key / oauth_secret
    "HC005",  # db_password
    "HC004",  # token
    "HC003",  # secret_key / jwt_secret
    "HC002",  # api_key
    "HC008",  # generic *secret* (broad)
    "HC001",  # generic password (broadest)
]


def _deduplicate_matches(matches: list[HardcodeMatch]) -> list[HardcodeMatch]:
    """
    Same (file, line, category) pe multiple matches aane pe sirf sabse specific ek rakho.

    Strategy:
    - CREDENTIAL category: _CREDENTIAL_PRIORITY ke hisaab se sabse specific rule jeetega.
      Same line pe HC001 + HC005 → sirf HC005 rakho (db_password more specific than password).
    - Baaki categories (HARDPATH, HARDURL, MAGICNUM, TODO): column bhi dekho —
      same line+column pe duplicate → ek hi rakho; alag columns par multiple theek hain.
    """
    # Step 1: CREDENTIAL same-line dedup — priority list se winner chuno
    cred_by_line: dict[tuple[str, int], HardcodeMatch] = {}
    non_cred: list[HardcodeMatch] = []

    for m in matches:
        if m.category in ("CREDENTIAL", "DATABASE"):
            key = (m.file, m.line)
            existing = cred_by_line.get(key)
            if existing is None:
                cred_by_line[key] = m
            else:
                # Lower priority index = more specific = wins
                existing_priority = _rule_priority(existing.rule_id)
                current_priority  = _rule_priority(m.rule_id)
                if current_priority < existing_priority:
                    cred_by_line[key] = m
        else:
            non_cred.append(m)

    # Step 2: Non-credential same line+col dedup (exact duplicate guard)
    seen_non_cred: set[tuple[str, int, int, str]] = set()
    deduped_non_cred: list[HardcodeMatch] = []
    for m in non_cred:
        key = (m.file, m.line, m.column, m.category)
        if key not in seen_non_cred:
            seen_non_cred.add(key)
            deduped_non_cred.append(m)

    # Step 3: Merge aur original order restore karo (line number se sort)
    result = list(cred_by_line.values()) + deduped_non_cred
    result.sort(key=lambda m: (m.file, m.line, m.column))
    return result


def _rule_priority(rule_id: str) -> int:
    """Lower = more specific = higher priority."""
    try:
        return _CREDENTIAL_PRIORITY.index(rule_id)
    except ValueError:
        return len(_CREDENTIAL_PRIORITY)  # unknown rules = lowest priority
