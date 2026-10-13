# 🐺 Lyncus — Multi-Language Code Quality CLI Tool
__version__ = "1.0.0"
__author__ = "Lyncus Contributors"

# Language modules — lazy import karo (optional deps ke liye)
__all__ = [
    "__version__",
    "__author__",
    "SUPPORTED_LANGUAGES",
    "LANGUAGE_ALIASES",
    "resolve_language",
]

SUPPORTED_LANGUAGES = [
    "python",
    "javascript",
    "typescript",
    "rust",
    "go",
    "cpp",
    "cuda",
    "csharp",
    "java",
    "ruby",
    "php",
]

LANGUAGE_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "c++": "cpp",
    "c": "cpp",
    "cs": "csharp",
    "c#": "csharp",
    "dotnet": "csharp",
    "rb": "ruby",
    "golang": "go",
    "rs": "rust",
    "node": "javascript",
    "nodejs": "javascript",
    "cu": "cuda",
    "java": "java",
    "php": "php",
}


def resolve_language(lang: str) -> str:
    """Language alias ko canonical name mein convert karo."""
    return LANGUAGE_ALIASES.get(lang.lower(), lang.lower())
