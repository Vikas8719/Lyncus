"""
Lyncus/core/utils.py — Shared utility functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Lyncus.core.parser import Problem


def calc_score(problems: list[Problem]) -> int:
    """
    Quality score calculate karo (0–100).

    Scoring philosophy:
      - Critical issues: -15  (production mein serious risk)
      - Warning  issues: -5   (code smell / bad practice)
      - Info     issues:  0   (informational only — score penalise nahi)

    COMPLEXITY warnings (radon grade C/D) ab 'info' hain (python_checks.py mein),
    isliye score penalise nahi hoga. Grade E = warning, Grade F = critical.

    Rationale: C-grade complexity (score 11-15) common hai bade codebases mein.
    Grade E/F hi genuinely unacceptable hain.
    """
    if not problems:
        return 100
    # COMPLEXITY category — radon/lizard refactor hints — score penalise nahi karte.
    # Sirf real bugs aur security issues ko count karo.
    critical = sum(
        1 for p in problems
        if p.severity == "critical" and p.category != "COMPLEXITY"
    )
    warnings = sum(
        1 for p in problems
        if p.severity == "warning" and p.category != "COMPLEXITY"
    )
    # info: intentionally excluded from penalty
    return max(0, 100 - (critical * 15) - (warnings * 5))
