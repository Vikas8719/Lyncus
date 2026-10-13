"""
Lyncus Language Modules
Har language ke tools, parsers aur configs yahan hain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

# Language → module mapping
LANGUAGE_MODULE_MAP: dict[str, str] = {
    "python": "Lyncus.languages.python_checks",
    "javascript": "Lyncus.languages.js_checks",
    "typescript": "Lyncus.languages.js_checks",
    "rust": "Lyncus.languages.rust_checks",
    "go": "Lyncus.languages.go_checks",
    "cpp": "Lyncus.languages.cpp_checks",
    "cuda": "Lyncus.languages.cuda_checks",
    "csharp": "Lyncus.languages.csharp_checks",
    "java": "Lyncus.languages.java_checks",
    "ruby": "Lyncus.languages.ruby_checks",
    "php": "Lyncus.languages.php_checks",
    "kotlin": "Lyncus.languages.kotlin_checks",
    "swift": "Lyncus.languages.swift_checks",
    "dart": "Lyncus.languages.dart_checks",
}


def get_tools_for_language(language: str, **kwargs: Any) -> list[Any]:
    """
    Language ke tools ki list return karo.
    Dynamic import karta hai — sirf zaroorat pe module load hoga.

    Args:
        language: canonical language name (python, rust, go, etc.)
        **kwargs: language-specific options (only, skip_slow, etc.)

    Returns:
        List of tool configs ya empty list agar language unsupported ho
    """
    import importlib

    module_path = LANGUAGE_MODULE_MAP.get(language)
    if not module_path:
        return []

    try:
        module = importlib.import_module(module_path)

        # Har module mein get_{lang}_tools function hona chahiye
        getter_names = [
            f"get_{language}_tools",
            "get_js_tools",  # JS/TS dono ke liye
            "get_cpp_tools",
        ]

        # Module mein function dhundo
        getter: Callable[..., list[Any]] | None = None
        for name in getter_names:
            if hasattr(module, name):
                getter = cast("Callable[..., list[Any]]", getattr(module, name))
                break

        # js_checks.py JS aur TS dono handle karta hai
        if language == "typescript" and hasattr(module, "get_js_tools"):
            kwargs["is_typescript"] = True
            getter = cast("Callable[..., list[Any]]", module.get_js_tools)

        if getter:
            return getter(**kwargs)

    except ImportError as e:
        print(f"[WARNING] {language} module import failed: {e}")

    return []


def get_install_commands_for_language(language: str) -> dict[str, str]:
    """Language ke sab tools ke install commands."""
    import importlib

    module_path = LANGUAGE_MODULE_MAP.get(language)
    if not module_path:
        return {}

    try:
        module = importlib.import_module(module_path)
        if hasattr(module, "get_install_commands"):
            return cast("dict[str, str]", module.get_install_commands())
    except ImportError:
        pass

    return {}
