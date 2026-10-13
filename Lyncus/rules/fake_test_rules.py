"""
Fake Test Detection Rules — Sab languages mein worthless tests pakadta hai.

NOTE: Ye file rule *definitions* store karti hai — actual test file nahi.
Patterns mein intentional "bad" assert examples hain (string literals ke roop mein),
jo self-scan mein false positive denge isliye `Lyncus/rules/` folder ko ignore karo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FakeTestMatch:
    rule_id: str
    description: str
    line: int
    matched_text: str
    severity: str
    suggestion: str


_WRITE_TEST_BODY = "Test body likho"

# ── Pattern building helpers ─────────────────────────────────────────────────
# Patterns ko parts mein todha gaya hai taaki self-scan mein trigger na hon.
# Agar ye file scan ho to bhi only regex string ke roop mein stored hai,
# actual Python assertion nahi.

_ASSERT_KEYWORD = r"\b" + "assert" + r"\s+"
_TRUE_LITERAL = "True" + r"\b"
_FALSE_LITERAL = "False" + r"\b"
_NOT_NONE_PATTERN = r"\w+\s+is\s+not\s+None\b"
_NEQ_NONE_PATTERN = r"\w+\s+!=\s+None\b"
_LEN_GT_ZERO = r"len\(\w+\)\s*[>!]=?\s*0\b"


# ── PYTHON FAKE TEST PATTERNS ────────────────────────────────────────────────
PYTHON_FAKE_PATTERNS: list[tuple[str, str, str, str]] = [
    # (pattern, rule_id, description, suggestion)
    (_ASSERT_KEYWORD + _TRUE_LITERAL,
     "FT001",
     "assert True — test kuch bhi prove nahi karta",
     "Real value check karo: assert result == expected_value"),

    (_ASSERT_KEYWORD + _FALSE_LITERAL,
     "FT002",
     "assert False — test hamesha fail hoga",
     "pytest.raises() use karo exception test ke liye"),

    (_ASSERT_KEYWORD + _NOT_NONE_PATTERN,
     "FT003",
     "assert x is not None — bahut weak check hai",
     "Actual value ya type check karo"),

    (_ASSERT_KEYWORD + _NEQ_NONE_PATTERN,
     "FT004",
     "assert x != None — weak check, `is not None` use karo + value check",
     "Actual content verify karo"),

    (_ASSERT_KEYWORD + _LEN_GT_ZERO,
     "FT005",
     "assert len(x) > 0 — sirf empty check, content verify nahi",
     "Specific length ya items check karo"),

    (r'\bassert\s+\w+\b\s*$',
     "FT006",
     "assert variable — sirf truthiness check, value nahi",
     "assert variable == expected_value use karo"),

    (r'def\s+test_\w+\(\w*\)\s*:\s*\n\s*pass\b',
     "FT007",
     "Empty test function — koi assertion hi nahi",
     "Test body likho ya delete karo"),

    (r'def\s+test_\w+\(\w*\)\s*:\s*\n\s*\.\.\.',
     "FT008",
     "Placeholder test (...)  — koi assertion nahi",
     "Real test logic likho"),

    (r'#\s*(noqa|type:\s*ignore|pragma:\s*no cover)',
     "FT009",
     "Test mein noqa/no cover — problem chhupa rahe ho",
     "Problem fix karo, suppress mat karo"),
]

# ── JAVA FAKE TEST PATTERNS ──────────────────────────────────────────────────
# Patterns are broken into parts to avoid self-scan false positives.
_JAVA_ASSERT_TRUE_PAT = r"assert" + r"True\s*\(\s*true\s*\)"
_JAVA_ASSERT_NOT_NULL_PAT = r"assert" + r"NotNull\s*\(\s*\w+\s*\)"
_JAVA_ASSERT_EQ_NULL_PAT = r"assert" + r"Equals\s*\(\s*null\s*,\s*null\s*\)"

JAVA_FAKE_PATTERNS: list[tuple[str, str, str, str]] = [
    (_JAVA_ASSERT_TRUE_PAT,
     "FT101",
     "assertTrue(true) — always passes, kuch prove nahi",
     "Real condition check karo"),

    (_JAVA_ASSERT_NOT_NULL_PAT,
     "FT102",
     "assertNotNull only — value verify nahi hoti",
     "assertEquals ya specific field check karo"),

    (r'@Test\s*\n\s*public\s+void\s+\w+\s*\(\s*\)\s*\{\s*\}',
     "FT103",
     "Empty @Test method — koi assertion nahi",
     _WRITE_TEST_BODY),

    (_JAVA_ASSERT_EQ_NULL_PAT,
     "FT104",
     "assertEquals(null, null) — meaningless test",
     "Real values compare karo"),
]

# ── JAVASCRIPT / TYPESCRIPT FAKE TEST PATTERNS ───────────────────────────────
# Patterns split to avoid self-triggering on literal strings.
_JS_EXPECT_TRUE_PAT = r"expect\s*\(\s*" + "true" + r"\s*\)\s*\.\s*toBe\s*\(\s*" + "true" + r"\s*\)"

JS_FAKE_PATTERNS: list[tuple[str, str, str, str]] = [
    (_JS_EXPECT_TRUE_PAT,
     "FT201",
     "expect(true).toBe(true) — always passes",
     "Real value test karo"),

    (r'expect\s*\(\s*\w+\s*\)\s*\.\s*toBeDefined\s*\(\s*\)',
     "FT202",
     "toBeDefined() only — value verify nahi hoti",
     "toEqual ya specific property check karo"),

    (r'it\s*\(\s*["\'][^"\']+["\']\s*,\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)',
     "FT203",
     "Empty it() block — koi assertion nahi",
     _WRITE_TEST_BODY),

    (r'test\s*\(\s*["\'][^"\']+["\']\s*,\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)',
     "FT204",
     "Empty test() block — koi assertion nahi",
     _WRITE_TEST_BODY),

    (r'expect\s*\(\s*\w+\s*\)\s*\.\s*not\s*\.\s*toBeNull\s*\(\s*\)',
     "FT205",
     "not.toBeNull() only — weak check",
     "Actual value ya structure verify karo"),
]

# ── C# FAKE TEST PATTERNS ────────────────────────────────────────────────────
# Patterns split to avoid self-triggering on literal strings.
_CS_IS_TRUE_PAT = r"Assert\.IsTrue\s*\(\s*" + "true" + r"\s*\)"
_CS_IS_NOT_NULL_PAT = r"Assert\.IsNotNull\s*\(\s*\w+\s*\)"

CSHARP_FAKE_PATTERNS: list[tuple[str, str, str, str]] = [
    (_CS_IS_TRUE_PAT,
     "FT301",
     "Assert.IsTrue(true) — always passes",
     "Real condition check karo"),

    (_CS_IS_NOT_NULL_PAT,
     "FT302",
     "Assert.IsNotNull only — value verify nahi hoti",
     "Assert.AreEqual ya specific property check karo"),

    (r'\[Test(?:Method)?\]\s*\n\s*public\s+void\s+\w+\s*\(\s*\)\s*\{\s*\}',
     "FT303",
     "Empty [Test] method — koi assertion nahi",
     _WRITE_TEST_BODY),
]

# ── RUST FAKE TEST PATTERNS ──────────────────────────────────────────────────
# assert!(true) pattern split to avoid self-scan trigger
_RUST_ASSERT_TRUE_PAT = r"assert!\s*\(\s*" + "true" + r"\s*\)"

RUST_FAKE_PATTERNS: list[tuple[str, str, str, str]] = [
    (_RUST_ASSERT_TRUE_PAT,
     "FT401",
     "assert!(true) — always passes",
     "Real condition assert karo"),

    (r'#\[test\]\s*\n\s*fn\s+\w+\s*\(\s*\)\s*\{\s*\}',
     "FT402",
     "Empty #[test] function — koi assertion nahi",
     _WRITE_TEST_BODY),

    (r'assert!\s*\(\w+\.is_some\(\)\)',
     "FT403",
     "assert!(x.is_some()) — value check nahi hoti",
     "assert_eq!(x.unwrap(), expected) use karo"),
]

# ── GO FAKE TEST PATTERNS ────────────────────────────────────────────────────
GO_FAKE_PATTERNS: list[tuple[str, str, str, str]] = [
    (r'func\s+Test\w+\s*\(\s*t\s*\*testing\.T\s*\)\s*\{\s*\}',
     "FT501",
     "Empty Test function — koi assertion nahi",
     "t.Error ya t.Fatal se check karo"),

    (r'if\s+\w+\s*==\s*nil\s*\{\s*t\.Error',
     "FT502",
     "Sirf nil check — value verify nahi hoti",
     "Actual value compare karo"),
]


def scan_file_for_fake_tests(
    content: str,
    language: str,
) -> list[FakeTestMatch]:
    """
    File mein fake/weak tests dhundo.

    Args:
        content: File ka poora content
        language: Programming language

    Returns:
        List of FakeTestMatch
    """
    matches: list[FakeTestMatch] = []
    lines = content.splitlines()

    # Language ke hisaab se patterns choose karo
    lang_patterns: dict[str, list[tuple[str, str, str, str]]] = {
        "python": PYTHON_FAKE_PATTERNS,
        "java": JAVA_FAKE_PATTERNS,
        "javascript": JS_FAKE_PATTERNS,
        "typescript": JS_FAKE_PATTERNS,
        "csharp": CSHARP_FAKE_PATTERNS,
        "rust": RUST_FAKE_PATTERNS,
        "go": GO_FAKE_PATTERNS,
    }

    patterns = lang_patterns.get(language, [])

    for pattern, rule_id, description, suggestion in patterns:
        compiled = re.compile(pattern, re.MULTILINE)
        for m in compiled.finditer(content):
            # Line number nikalo
            line_num = content[:m.start()].count("\n") + 1
            line_text = lines[line_num - 1] if line_num <= len(lines) else ""

            matches.append(FakeTestMatch(
                rule_id=rule_id,
                description=description,
                line=line_num,
                matched_text=line_text.strip()[:60],
                severity="critical",
                suggestion=suggestion,
            ))

    return matches
