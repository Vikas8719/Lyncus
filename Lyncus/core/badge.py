"""
Lyncus/core/badge.py
SVG badge generator — README mein lagao ya CI artifact ki tarah use karo.
Shields.io style badges.
"""

from __future__ import annotations

from pathlib import Path

# Named score threshold constants — magic numbers nahi
_SCORE_EXCELLENT = 90   # >= 90 → excellent / green
_SCORE_GOOD = 75        # >= 75 → good / light green
_SCORE_FAIR = 60        # >= 60 → fair / yellow
_SCORE_POOR = 40        # >= 40 → poor / orange
# < 40 → critical / red

# SVG layout constants
_BADGE_LEFT_WIDTH = 80          # "🐺 Lyncus" section width in px
_BADGE_MIN_RIGHT_WIDTH = 60     # Minimum right section width in px
_BADGE_ISSUES_MIN_RIGHT = 70    # Issues badge minimum right width
_BADGE_LANG_TOTAL_WIDTH = 120   # Language badge total width
_BADGE_LANG_HALF_WIDTH = 60     # Language badge per-half width
_BADGE_CHARS_PER_PX = 7         # Estimated px width per character
_BADGE_PADDING_PX = 10          # Padding added to text width
_BADGE_FONT_SIZE = 110          # SVG font-size attribute value
_BADGE_HEIGHT = 20              # Badge height in px
_BADGE_SHADOW_Y = 150           # Shadow text y-coordinate (scaled)
_BADGE_TEXT_Y = 140             # Main text y-coordinate (scaled)
_BADGE_SVG_SCALE = 10           # SVG transform scale denominator


def _score_color(score: int) -> str:
    if score >= _SCORE_EXCELLENT:
        return "#22c55e"  # Green
    if score >= _SCORE_GOOD:
        return "#84cc16"  # Light green
    if score >= _SCORE_FAIR:
        return "#f59e0b"  # Yellow
    if score >= _SCORE_POOR:
        return "#f97316"  # Orange
    return "#ef4444"  # Red


def _score_label(score: int) -> str:
    if score >= _SCORE_EXCELLENT:
        return "excellent"
    if score >= _SCORE_GOOD:
        return "good"
    if score >= _SCORE_FAIR:
        return "fair"
    if score >= _SCORE_POOR:
        return "poor"
    return "critical"


def generate_score_badge(
    score: int,
    output_file: str = "Lyncus-badge.svg",
) -> str:
    """
    Score badge SVG banao — shields.io style.

    Example:
      [🐺 Lyncus | 87/100 · good]
    """
    color = _score_color(score)
    label = _score_label(score)
    text = f"{score}/100 · {label}"

    # Text width estimate (~7px per char + padding)
    left_w = _BADGE_LEFT_WIDTH
    right_w = max(_BADGE_MIN_RIGHT_WIDTH, len(text) * _BADGE_CHARS_PER_PX + _BADGE_PADDING_PX)
    total_w = left_w + right_w

    _pad = _BADGE_PADDING_PX
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{_BADGE_HEIGHT}" role="img" aria-label="Lyncus: {text}">
  <title>Lyncus: {text}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_w}" height="{_BADGE_HEIGHT}" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{left_w}" height="{_BADGE_HEIGHT}" fill="#555"/>
    <rect x="{left_w}" width="{right_w}" height="{_BADGE_HEIGHT}" fill="{color}"/>
    <rect width="{total_w}" height="{_BADGE_HEIGHT}" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="{_BADGE_FONT_SIZE}">
    <text x="{left_w // 2 * _BADGE_SVG_SCALE}" y="{_BADGE_SHADOW_Y}" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(left_w - _pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">🐺 Lyncus</text>
    <text x="{left_w // 2 * _BADGE_SVG_SCALE}" y="{_BADGE_TEXT_Y}" transform="scale(.1)" textLength="{(left_w - _pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">🐺 Lyncus</text>
    <text x="{(left_w + right_w // 2) * _BADGE_SVG_SCALE}" y="{_BADGE_SHADOW_Y}" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(right_w - _pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">{text}</text>
    <text x="{(left_w + right_w // 2) * _BADGE_SVG_SCALE}" y="{_BADGE_TEXT_Y}" transform="scale(.1)" textLength="{(right_w - _pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">{text}</text>
  </g>
</svg>"""

    Path(output_file).write_text(svg, encoding="utf-8")
    return svg


def generate_problems_badge(
    critical: int,
    warnings: int,
    output_file: str = "Lyncus-issues-badge.svg",
) -> str:
    """
    Issues count badge — [🐺 Lyncus | ❌3 ⚠️5]
    """
    total = critical + warnings
    if critical > 0:
        color = "#ef4444"
    elif warnings > 0:
        color = "#f59e0b"
    else:
        color = "#22c55e"
    text = f"❌ {critical}  ⚠️ {warnings}" if total > 0 else "✅ clean"

    _issues_extra_pad = 16  # Wider padding for emoji text
    left_w = _BADGE_LEFT_WIDTH
    right_w = max(_BADGE_ISSUES_MIN_RIGHT, len(text) * _BADGE_CHARS_PER_PX + _issues_extra_pad)
    total_w = left_w + right_w
    _pad = _BADGE_PADDING_PX

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{_BADGE_HEIGHT}" role="img" aria-label="Lyncus issues: {text}">
  <title>Lyncus issues: {text}</title>
  <clipPath id="r">
    <rect width="{total_w}" height="{_BADGE_HEIGHT}" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{left_w}" height="{_BADGE_HEIGHT}" fill="#555"/>
    <rect x="{left_w}" width="{right_w}" height="{_BADGE_HEIGHT}" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="{_BADGE_FONT_SIZE}">
    <text x="{left_w // 2 * _BADGE_SVG_SCALE}" y="{_BADGE_TEXT_Y}" transform="scale(.1)" textLength="{(left_w - _pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">🐺 Lyncus</text>
    <text x="{(left_w + right_w // 2) * _BADGE_SVG_SCALE}" y="{_BADGE_TEXT_Y}" transform="scale(.1)" textLength="{(right_w - _pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">{text}</text>
  </g>
</svg>"""

    Path(output_file).write_text(svg, encoding="utf-8")
    return svg


def generate_language_badge(language: str, output_file: str | None = None) -> str:
    """Language badge generate karo."""
    lang_colors = {
        "python": "#3776ab",
        "javascript": "#f7df1e",
        "typescript": "#3178c6",
        "rust": "#ce422b",
        "go": "#00add8",
        "java": "#ed8b00",
        "cpp": "#00599c",
        "csharp": "#68217a",
        "ruby": "#cc342d",
        "php": "#777bb4",
        "cuda": "#76b900",
        "kotlin": "#7f52ff",
        "swift": "#fa7343",
    }
    color = lang_colors.get(language.lower(), "#6b7280")
    text = language

    _lang_inner_pad = 6  # Tighter padding for language badge text
    total_w = _BADGE_LANG_TOTAL_WIDTH
    left_w = _BADGE_LANG_HALF_WIDTH
    right_w = _BADGE_LANG_HALF_WIDTH

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{_BADGE_HEIGHT}" role="img">
  <title>Lyncus | {text}</title>
  <clipPath id="r">
    <rect width="{total_w}" height="{_BADGE_HEIGHT}" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{left_w}" height="{_BADGE_HEIGHT}" fill="#555"/>
    <rect x="{left_w}" width="{right_w}" height="{_BADGE_HEIGHT}" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="{_BADGE_FONT_SIZE}">
    <text x="{left_w // 2 * _BADGE_SVG_SCALE}" y="{_BADGE_TEXT_Y}" transform="scale(.1)" textLength="{(left_w - _lang_inner_pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">Lyncus</text>
    <text x="{(left_w + right_w // 2) * _BADGE_SVG_SCALE}" y="{_BADGE_TEXT_Y}" transform="scale(.1)" textLength="{(right_w - _lang_inner_pad) * _BADGE_SVG_SCALE}" lengthAdjust="spacing">{text}</text>
  </g>
</svg>"""

    out = output_file or f"Lyncus-{language.lower()}-badge.svg"
    Path(out).write_text(svg, encoding="utf-8")
    return svg
