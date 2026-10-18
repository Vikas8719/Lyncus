"""
Language Auto-Detector — Project folder scan karke language detect karta hai.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DetectionResult:
    primary_language: str
    all_languages: list[str]
    file_counts: dict[str, int]
    has_cuda: bool = False
    confidence: str = "high"  # high / medium / low


# Extension → Language mapping
EXTENSION_MAP: dict[str, str] = {
    # Python
    ".py": "python", ".pyi": "python", ".pyw": "python",
    # C / C++
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".c": "cpp", ".h": "cpp", ".hpp": "cpp", ".hxx": "cpp", ".hh": "cpp",
    # CUDA
    ".cu": "cuda", ".cuh": "cuda",
    # C#
    ".cs": "csharp", ".cshtml": "csharp", ".razor": "csharp",
    # Java
    ".java": "java",
    # Rust
    ".rs": "rust",
    # Go
    ".go": "go",
    # JavaScript
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    # TypeScript
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    # Ruby
    ".rb": "ruby", ".rake": "ruby", ".gemspec": "ruby", ".ru": "ruby",
    # PHP
    ".php": "php", ".phtml": "php", ".php5": "php", ".php7": "php", ".php8": "php",
    # Kotlin
    ".kt": "kotlin", ".kts": "kotlin",
    # Swift
    ".swift": "swift",
    # Dart
    ".dart": "dart",
}

# Config file → Language hint
CONFIG_FILE_HINTS: dict[str, str] = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "package.json": "javascript",
    "tsconfig.json": "typescript",
    "pom.xml": "java",
    "build.gradle": "java",
    "*.csproj": "csharp",
    "*.sln": "csharp",
    "Gemfile": "ruby",
    "composer.json": "php",
    "pubspec.yaml": "dart",
}

# Ignore these folders
IGNORE_DIRS: set[str] = {
    "venv", ".venv", "env", "node_modules", ".git",
    ".env", "dist", "build", "__pycache__", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", ".hypothesis", ".cache", "cache",
    "target", "bin", "obj", "vendor", "packages", ".gradle", ".idea", ".vscode", ".vs", ".settings", ".metadata", ".xml", ".dockerignore",
}


def detect_language(project_path: str) -> DetectionResult:
    """
    Project folder scan karke primary language detect karta hai.

    Args:
        project_path: Project ka root folder path

    Returns:
        DetectionResult — primary language + sab languages + file counts
    """
    path = Path(project_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Path nahi mila: {project_path}")

    if path.is_file():
        return _detect_single_file(path)

    return _build_detection_result(_count_project_languages(path))


def _detect_single_file(path: Path) -> DetectionResult:
    is_env_file = path.name.lower() == ".env" or path.name.lower().startswith(".env.")
    language = "unknown" if is_env_file else EXTENSION_MAP.get(path.suffix.lower(), "unknown")
    return DetectionResult(
        primary_language=language,
        all_languages=[language],
        file_counts={language: 1},
        has_cuda=language == "cuda",
    )


def _count_project_languages(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, directories, files in os.walk(path):
        directories[:] = [directory for directory in directories if directory not in IGNORE_DIRS]
        for file_name in files:
            if file_name.lower() == ".env" or file_name.lower().startswith(".env."):
                continue
            language = EXTENSION_MAP.get(Path(file_name).suffix.lower())
            if language:
                counts[language] = counts.get(language, 0) + 1
    return counts


def _add_config_language_hints(path: Path, counts: dict[str, int]) -> None:
    for config_file, language in CONFIG_FILE_HINTS.items():
        config_path = path / config_file
        if config_path.exists() and language not in counts:
            counts[language] = counts.get(language, 0) + 1


def _build_detection_result(file_counts: dict[str, int]) -> DetectionResult:
    if not file_counts:
        return DetectionResult(
            primary_language="unknown",
            all_languages=[],
            file_counts={},
            confidence="low",
        )

    effective_counts = dict(file_counts)

    has_cuda = "cuda" in effective_counts
    if has_cuda and "cpp" not in effective_counts:
        effective_counts["cpp"] = 0

    sorted_langs = sorted(effective_counts.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_langs[0][0]
    if has_cuda and primary == "cpp":
        primary = "cuda"

    all_langs = [lang for lang, _ in sorted_langs]
    total_files = sum(effective_counts.values())
    top_count = sorted_langs[0][1]
    return DetectionResult(
        primary_language=primary,
        all_languages=all_langs,
        file_counts=file_counts,  # original counts preserve karo (caller ke liye)
        has_cuda=has_cuda,
        confidence=_confidence_level(top_count, total_files),
    )


def _confidence_level(top_count: int, total_count: int) -> str:
    share = top_count / max(total_count, 1)
    if share > 0.6:
        return "high"
    if share > 0.3:
        return "medium"
    return "low"


def get_supported_languages() -> list[str]:
    """Sab supported languages ki list."""
    _NON_SOURCE = {"yaml"}
    return sorted(set(EXTENSION_MAP.values()) - _NON_SOURCE)
