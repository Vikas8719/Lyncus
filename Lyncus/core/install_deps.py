"""
install_deps.py — Language tools auto-installer
Lyncus install-deps --lang python → missing tools install kar deta hai
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass

from rich.console import Console

console = Console()


@dataclass
class InstallSpec:
    name: str
    language: str
    check_cmd: str  # Tool detect karne ka command
    install_cmds: list[str]  # Install commands (ek ya zyada)
    post_check: str = ""  # Install ke baad verify command
    notes: str = ""  # Extra notes


# ── INSTALL SPECS ─────────────────────────────────────────────────────────────

ALL_TOOLS: list[InstallSpec] = [
    # ── Python ────────────────────────────────────────────────────────────────
    InstallSpec(
        "ruff",
        "python",
        "ruff",
        ["pip install ruff>=0.4"],
        notes="Python linter — ruff replaces flake8+isort",
    ),
    InstallSpec("mypy", "python", "mypy", ["pip install mypy>=1.10"], notes="Type checker"),
    InstallSpec(
        "bandit", "python", "bandit", ["pip install bandit>=1.7"], notes="Security scanner"
    ),
    InstallSpec(
        "vulture", "python", "vulture", ["pip install vulture>=2.11"], notes="Dead code finder"
    ),
    InstallSpec(
        "mutmut",
        "python",
        "mutmut",
        ["pip install 'mutmut>=3.0,<4'"],
        notes="Mutation testing — PERMANENTLY SKIPPED (too slow; use cargo-mutants/stryker instead)",
    ),
    InstallSpec("radon", "python", "radon", ["pip install radon>=6.0"], notes="Complexity metrics"),
    InstallSpec(
        "hypothesis",
        "python",
        "hypothesis",
        ["pip install hypothesis"],
        notes="Property-based testing — 1000 random examples per @given test (runs via pytest-cov)",
    ),
    InstallSpec(
        "pip-audit",
        "python",
        "pip-audit",
        ["pip install pip-audit>=2.7"],
        notes="Dependency vulnerabilities",
    ),
    # ── JavaScript / TypeScript ───────────────────────────────────────────────
    InstallSpec("eslint", "javascript", "eslint", ["npm install -g eslint@9"], notes="JS/TS linter"),
    InstallSpec("tsc", "javascript", "tsc", ["npm install -g typescript@5"], notes="TypeScript compiler"),
    InstallSpec(
        "ts-prune",
        "javascript",
        "ts-prune",
        ["npm install -g ts-prune"],
        notes="Dead code — unused exports",
    ),
    InstallSpec("c8", "javascript", "c8", ["npm install -g c8@10"], notes="Code coverage"),
    # ── Rust ──────────────────────────────────────────────────────────────────
    InstallSpec(
        "clippy",
        "rust",
        "cargo-clippy",
        ["rustup component add clippy"],
        notes="Rust linter — built-in",
    ),
    InstallSpec(
        "rustfmt", "rust", "rustfmt", ["rustup component add rustfmt"], notes="Rust formatter"
    ),
    InstallSpec(
        "cargo-audit", "rust", "cargo-audit", ["cargo install cargo-audit"], notes="Dependency CVEs"
    ),
    InstallSpec(
        "cargo-tarpaulin",
        "rust",
        "cargo-tarpaulin",
        ["cargo install cargo-tarpaulin"],
        notes="Code coverage (Linux only)",
    ),
    InstallSpec(
        "cargo-machete",
        "rust",
        "cargo-machete",
        ["cargo install cargo-machete"],
        notes="Unused dependencies",
    ),
    # ── Rust Sanitizers ───────────────────────────────────────────────────────
    InstallSpec(
        "asan-rust",
        "rust",
        "rustup",
        ["rustup toolchain install nightly"],
        notes="AddressSanitizer — unsafe Rust heap/stack errors (nightly required, Linux only)",
    ),
    InstallSpec(
        "ubsan-rust",
        "rust",
        "rustup",
        ["rustup toolchain install nightly"],
        notes="UndefinedBehaviorSanitizer — Rust UB detection (nightly required, Linux only)",
    ),
    InstallSpec(
        "compsan-rust",
        "rust",
        "rustup",
        ["rustup toolchain install nightly"],
        notes="ThreadSanitizer — data races in unsafe/async Rust (nightly, Linux/macOS only)",
    ),
    # ── Go ────────────────────────────────────────────────────────────────────
    InstallSpec(
        "staticcheck",
        "go",
        "staticcheck",
        ["go install honnef.co/go/tools/cmd/staticcheck@latest"],
        notes="Go static analysis",
    ),
    InstallSpec(
        "gosec",
        "go",
        "gosec",
        ["go install github.com/securego/gosec/v2/cmd/gosec@latest"],
        notes="Go security",
    ),
    InstallSpec(
        "golangci-lint",
        "go",
        "golangci-lint",
        ["go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"],
        notes="Go linter aggregator",
    ),
    InstallSpec(
        "deadcode",
        "go",
        "deadcode",
        ["go install golang.org/x/tools/cmd/deadcode@latest"],
        notes="Go dead code",
    ),
    # ── C++ ───────────────────────────────────────────────────────────────────
    InstallSpec(
        "cppcheck",
        "cpp",
        "cppcheck",
        [
            "apt-get install -y cppcheck",
            "brew install cppcheck",
            "winget install --id Cppcheck.Cppcheck --exact --silent --accept-package-agreements --accept-source-agreements",
            "choco install cppcheck -y",
        ],
        notes="C++ static analysis",
    ),
    InstallSpec(
        "clang-tidy",
        "cpp",
        "clang-tidy",
        [
            "apt-get install -y clang-tidy",
            "brew install llvm",
            "winget install --id LLVM.LLVM --exact --silent --accept-package-agreements --accept-source-agreements",
            "choco install llvm -y",
        ],
        notes="C++ linter",
    ),
    InstallSpec(
        "flawfinder",
        "cpp",
        "flawfinder",
        ["pip install flawfinder>=2.0"],
        notes="C++ security scanner",
    ),
    InstallSpec(
        "lizard", "cpp", "lizard", ["pip install lizard>=1.17"], notes="Complexity analyzer"
    ),
    InstallSpec(
        "cpplint",
        "cpp",
        "cpplint",
        ["pip install cpplint>=1.6"],
        notes="Google C++ style guide checker",
    ),
    # ── C++ Sanitizers ────────────────────────────────────────────────────────
    InstallSpec(
        "asan-cpp",
        "cpp",
        "clang++",
        [
            "apt-get install -y clang",
            "brew install llvm",
            "winget install --id LLVM.LLVM --exact --silent --accept-package-agreements --accept-source-agreements",
            "choco install llvm -y",
        ],
        notes="AddressSanitizer — heap/stack/global buffer overflow (clang++ required)",
    ),
    InstallSpec(
        "ubsan-cpp",
        "cpp",
        "clang++",
        [
            "apt-get install -y clang",
            "brew install llvm",
            "winget install --id LLVM.LLVM --exact --silent --accept-package-agreements --accept-source-agreements",
            "choco install llvm -y",
        ],
        notes="UndefinedBehaviorSanitizer — null deref, signed overflow (clang++ required)",
    ),
    InstallSpec(
        "msan-cpp",
        "cpp",
        "clang++",
        [
            "apt-get install -y clang",
            # macOS: msan officially Linux-only, brew install optional
            "brew install llvm",
        ],
        notes="MemorySanitizer — uninitialized memory reads (Linux only; valgrind replacement, 3x faster)",
    ),
    InstallSpec(
        "tsan-cpp",
        "cpp",
        "clang++",
        [
            "apt-get install -y clang",
            "brew install llvm",   # macOS pe supported
        ],
        notes="ThreadSanitizer — data races, deadlocks in multi-threaded C++ (Linux/macOS)",
    ),
    InstallSpec(
        "compsan-cpp",
        "cpp",
        "clang++",
        [
            "apt-get install -y clang",
            "brew install llvm",
            # Windows pe: LLVM install karo, phir bash (WSL/Git-bash) se chalao
            # Native Windows pe compsan-cpp nahi chalega — WSL2 recommend hai
            "winget install --id LLVM.LLVM --exact --silent --accept-package-agreements --accept-source-agreements",
        ],
        notes="Combined ASan+UBSan — maximum runtime error coverage (Linux/macOS; Windows: WSL2 recommended)",
    ),
    # ── CUDA ──────────────────────────────────────────────────────────────────
    InstallSpec(
        "asan-cuda",
        "cuda",
        "clang++",
        [
            "apt-get install -y clang nvidia-cuda-toolkit",
            "winget install --id Nvidia.CUDA --exact --silent --accept-package-agreements --accept-source-agreements",
        ],
        notes="ASan — CUDA host-side memory errors (clang++ + CUDA toolkit required)",
    ),
    InstallSpec(
        "ubsan-cuda",
        "cuda",
        "clang++",
        [
            "apt-get install -y clang nvidia-cuda-toolkit",
        ],
        notes="UBSan — CUDA host-side undefined behavior (Linux only)",
    ),
    InstallSpec(
        "compute-sanitizer",
        "cuda",
        "compute-sanitizer",
        [
            "apt-get install -y nvidia-cuda-toolkit",
            "winget install --id Nvidia.CUDA --exact --silent --accept-package-agreements --accept-source-agreements",
            "choco install cuda -y",
        ],
        notes="NVIDIA Compute Sanitizer — GPU memory errors, races, OOB (CUDA toolkit)",
    ),
    # ── C# ────────────────────────────────────────────────────────────────────
    InstallSpec(
        "dotnet-format",
        "csharp",
        "dotnet-format",
        ["dotnet tool install -g dotnet-format"],
        notes=".NET formatter",
    ),
    InstallSpec(
        "dotnet-stryker",
        "csharp",
        "dotnet-stryker",
        ["dotnet tool install -g dotnet-stryker"],
        notes="C# mutation testing",
    ),
    InstallSpec(
        "security-scan",
        "csharp",
        "security-scan",
        ["dotnet tool install -g security-scan"],
        notes="C# security scanner",
    ),
    InstallSpec(
        "roslynator",
        "csharp",
        "roslynator",
        ["dotnet tool install -g roslynator.dotnet.cli"],
        notes="Roslyn analyzers",
    ),
    InstallSpec(
        "semgrep",
        "csharp",
        "semgrep",
        [
            "pip install semgrep",                          # Linux / WSL / macOS (pip)
            "brew install semgrep",                         # macOS (Homebrew)
            "winget install --id Semgrep.Semgrep --exact --silent "
            "--accept-package-agreements --accept-source-agreements",  # Windows
        ],
        post_check="semgrep --version",
        notes=(
            "C# SAST — OWASP rules, hardcoded secrets, injection "
            "(Linux/WSL: pip install semgrep | macOS: brew install semgrep | "
            "Windows: winget install Semgrep.Semgrep)"
        ),
    ),
    # ── Java ──────────────────────────────────────────────────────────────────
    InstallSpec(
        "pmd",
        "java",
        "pmd",
        ["brew install pmd", "# Download: https://pmd.github.io"],
        notes="Java static analysis",
    ),
    InstallSpec("lizard", "java", "lizard", ["pip install lizard>=1.17"], notes="Java complexity"),
    # ── Ruby ──────────────────────────────────────────────────────────────────
    InstallSpec("rubocop", "ruby", "rubocop", ["gem install rubocop"], notes="Ruby style guide"),
    InstallSpec(
        "brakeman", "ruby", "brakeman", ["gem install brakeman"], notes="Rails security scanner"
    ),
    InstallSpec("debride", "ruby", "debride", ["gem install debride"], notes="Ruby dead code"),
    InstallSpec("reek", "ruby", "reek", ["gem install reek"], notes="Ruby code smells"),
    InstallSpec("flog", "ruby", "flog", ["gem install flog"], notes="Ruby complexity"),
    InstallSpec(
        "bundler-audit",
        "ruby",
        "bundle-audit",
        ["gem install bundler-audit"],
        notes="Gem vulnerability audit",
    ),
    # ── PHP ───────────────────────────────────────────────────────────────────
    InstallSpec(
        "phpcs",
        "php",
        "phpcs",
        ["composer global require squizlabs/php_codesniffer"],
        notes="PHP CodeSniffer",
    ),
    InstallSpec(
        "phpstan",
        "php",
        "phpstan",
        ["composer global require phpstan/phpstan"],
        notes="PHP static analysis",
    ),
    InstallSpec(
        "psalm", "php", "psalm", ["composer global require vimeo/psalm"], notes="PHP security+types"
    ),
    InstallSpec(
        "phpcpd", "php", "phpcpd", ["phive install phpcpd"], notes="PHP copy-paste detector"
    ),
]


def _refresh_importlib_caches() -> None:
    """
    importlib aur shutil.which caches invalidate karo.
    Manual install ke baad same process mein naye tools detect ho sakein.
    """
    import importlib as _il
    _il.invalidate_caches()
    # CPython internal which cache bhi clear karo
    _wg = shutil.__dict__.get("_which_cache") or shutil.which.__globals__.get("_which_cache", {})
    _wg.clear()


def check_tool(tool: InstallSpec) -> bool:
    """Tool installed hai ya nahi check karo — platform-aware smart detection."""
    import importlib
    import platform

    name = tool.name
    cmd = tool.check_cmd

    # ── Dotnet global tools — PATH + ~/.dotnet/tools/ + dotnet tool list --global ──
    # WSL/Linux + macOS pe PATH automatically update nahi hoti after `dotnet tool install -g`
    # Isliye sirf shutil.which() se miss hota hai — ~/.dotnet/tools/ direct check zaroori hai.
    _DOTNET_GLOBAL_TOOLS = {
        "roslynator":    "roslynator.dotnet.cli",
        "dotnet-format": "dotnet-format",
        "dotnet-stryker":"dotnet-stryker",
        "security-scan": "security-scan",
    }
    if name in _DOTNET_GLOBAL_TOOLS:
        # Layer 1: PATH check
        if shutil.which(cmd) is not None:
            return True
        # Layer 2: ~/.dotnet/tools/ direct file check (WSL/macOS pe PATH nahi hoti)
        import platform as _plat
        home = os.path.expanduser("~")
        dotnet_tools_dirs = [
            os.path.join(home, ".dotnet", "tools"),
        ]
        dotnet_root = os.environ.get("DOTNET_ROOT", "")
        if dotnet_root:
            dotnet_tools_dirs.insert(0, os.path.join(dotnet_root, "tools"))
        exe_suffix = ".exe" if _plat.system().lower() == "windows" else ""
        for tools_dir in dotnet_tools_dirs:
            candidate = os.path.join(tools_dir, f"{cmd}{exe_suffix}")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return True
            # Windows: .exe extension
            candidate_exe = os.path.join(tools_dir, f"{cmd}.exe")
            if os.path.isfile(candidate_exe):
                return True
        # Layer 3: dotnet tool list --global (definitive but ~0.5s)
        try:
            result = subprocess.run(
                ["dotnet", "tool", "list", "--global"],
                capture_output=True, text=True, timeout=15,
            )
            pkg_id = _DOTNET_GLOBAL_TOOLS.get(name, name)
            return pkg_id.lower() in result.stdout.lower() or name.lower() in result.stdout.lower()
        except Exception:
            return False

    # ── Python packages — importlib.find_spec() check (works in venv too) ──
    _PYTHON_PACKAGES = {
        "hypothesis": "hypothesis",
        "mutmut": "mutmut",
        "pytest-cov": "pytest_cov",
        "radon": "radon",
        "bandit": "bandit",
        "vulture": "vulture",
        "mypy": "mypy",
        "ruff": "ruff",
        "pip-audit": "pip_audit",
        "flawfinder": "flawfinder",
        "lizard": "lizard",
        "cpplint": "cpplint",
    }
    if name in _PYTHON_PACKAGES:
        # importlib cache pehle fresh karo taaki manual install reflect ho
        _refresh_importlib_caches()
        module_name = _PYTHON_PACKAGES[name]
        if importlib.util.find_spec(module_name) is not None:
            return True
        # shutil.which fallback — PATH mein dhundo
        if shutil.which(cmd) is not None:
            return True
        # venv paths check karo (Windows: Scripts, Linux: bin)
        venv_paths = _get_venv_paths()
        for venv_bin in venv_paths:
            candidate = os.path.join(venv_bin, cmd)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return True
        # WSL / Linux: pip install --user → ~/.local/bin/ bhi check karo
        if sys.platform != "win32":
            home_local_bin = os.path.join(os.path.expanduser("~"), ".local", "bin", cmd)
            if os.path.isfile(home_local_bin) and os.access(home_local_bin, os.X_OK):
                return True
            # System-level install: /usr/local/bin/ ya /usr/bin/
            for sys_bin in ("/usr/local/bin", "/usr/bin"):
                sys_candidate = os.path.join(sys_bin, cmd)
                if os.path.isfile(sys_candidate) and os.access(sys_candidate, os.X_OK):
                    return True
        return False

    # ── Windows-specific paths check karo for system tools ──
    if platform.system().lower() == "windows":
        _WINDOWS_PATHS: dict[str, list[str]] = {
            "cppcheck": [
                r"C:\Program Files\Cppcheck\cppcheck.exe",
                r"C:\Program Files (x86)\Cppcheck\cppcheck.exe",
            ],
            "clang-tidy": [
                r"C:\Program Files\LLVM\bin\clang-tidy.exe",
                r"C:\Program Files (x86)\LLVM\bin\clang-tidy.exe",
            ],
            "clang++": [
                r"C:\Program Files\LLVM\bin\clang++.exe",
                r"C:\Program Files (x86)\LLVM\bin\clang++.exe",
            ],
            "compute-sanitizer": [
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin\compute-sanitizer.exe",
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin\compute-sanitizer.exe",
            ],
        }
        if cmd in _WINDOWS_PATHS:
            for path in _WINDOWS_PATHS[cmd]:
                if os.path.isfile(path):
                    return True

    # ── Default: shutil.which check ──
    return shutil.which(cmd) is not None


def _get_venv_paths() -> list[str]:
    """
    Venv bin/Scripts directories collect karo jo PATH mein nahi hain.
    WSL/Linux pe user-local aur system paths bhi include karo.
    """
    paths: list[str] = []
    # Active venv check karo
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        if sys.platform == "win32":
            paths.append(os.path.join(venv, "Scripts"))
        else:
            paths.append(os.path.join(venv, "bin"))
    # sys.prefix se bhi check karo (conda environments etc.)
    prefix = getattr(sys, "prefix", None)
    base_prefix = getattr(sys, "base_prefix", None)
    if prefix and prefix != base_prefix:
        if sys.platform == "win32":
            paths.append(os.path.join(prefix, "Scripts"))
        else:
            paths.append(os.path.join(prefix, "bin"))
    # sys.executable ke directory — pip install ke baad same dir mein tool jaata hai
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir and exe_dir not in paths:
        paths.append(exe_dir)
    # WSL / Linux: pip install --user ke baad ~/.local/bin/ mein jaata hai
    if sys.platform != "win32":
        home_local_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
        if home_local_bin not in paths:
            paths.append(home_local_bin)
        # System-level install paths bhi check karo
        for sys_bin in ("/usr/local/bin", "/usr/bin"):
            if sys_bin not in paths:
                paths.append(sys_bin)
    return paths


def get_tools_for_language(language: str) -> list[InstallSpec]:
    if language.lower() == "all":
        return ALL_TOOLS
    return [t for t in ALL_TOOLS if t.language == language.lower()]


def get_missing_tools(language: str = "all") -> list[InstallSpec]:
    return [t for t in get_tools_for_language(language) if not check_tool(t)]


def get_available_tools(language: str = "all") -> list[InstallSpec]:
    return [t for t in get_tools_for_language(language) if check_tool(t)]


def print_doctor_table(language: str = "all") -> None:
    """Print a doctor-style table of tool status."""
    import platform

    tools = get_tools_for_language(language)
    if not tools:
        console.print(f"[red]Unknown language: {language}[/red]")
        return

    current_os = platform.system().lower()
    is_windows = current_os == "windows"

    # Tools jo Windows pe Linux/macOS par hi kaam karte hain
    _LINUX_ONLY_TOOLS = frozenset({
        "asan-cpp", "ubsan-cpp", "compsan-cpp",
        "tsan-cpp",            # tsan: Linux/macOS, not Windows
        "msan-cpp",            # msan: Linux only
        "asan-rust", "ubsan-rust", "compsan-rust",
        "asan-cuda", "ubsan-cuda",
        "cargo-tarpaulin",
    })
    # Tools jo macOS pe bhi chalte hain (Linux-only se exclude)
    _MACOS_COMPATIBLE_SANITIZERS = frozenset({
        "asan-cpp", "ubsan-cpp", "tsan-cpp", "compsan-cpp",
    })
    # C++/CUDA tools jo Windows pe system installer (winget/choco) chahiye
    _WINDOWS_SYSTEM_INSTALL_TOOLS = frozenset({
        "cppcheck", "clang-tidy", "clang++",
        "compute-sanitizer", "nvcc", "nvcc-warnings",
    })

    # Group by language
    by_lang: dict[str, list[tuple[InstallSpec, bool]]] = {}
    for t in tools:
        available = check_tool(t)
        by_lang.setdefault(t.language, []).append((t, available))

    total = len(tools)
    available_count = sum(1 for t in tools if check_tool(t))

    console.print()
    for lang, tool_list in by_lang.items():
        console.print(f"\n  [bold cyan]{lang.upper()} Tools:[/bold cyan]")
        for tool, ok in tool_list:
            if ok:
                console.print(f"    [green]✅[/green]  {tool.name:<22} [dim]{tool.notes}[/dim]")
            elif is_windows and tool.name in _LINUX_ONLY_TOOLS:
                # Linux/macOS-only tools — Windows pe skip hote hain
                console.print(
                    f"    [dim]⏭️   {tool.name:<22} "
                    f"Linux/macOS only — not available on Windows (use WSL2)[/dim]"
                )
            elif current_os == "darwin" and tool.name in _LINUX_ONLY_TOOLS and tool.name not in _MACOS_COMPATIBLE_SANITIZERS:
                # macOS pe bhi nahi chalte (msan-cpp, cuda sanitizers etc.)
                console.print(
                    f"    [dim]⏭️   {tool.name:<22} "
                    f"Linux only — not available on macOS[/dim]"
                )
            elif is_windows and tool.name in _WINDOWS_SYSTEM_INSTALL_TOOLS:
                # Windows pe system installer chahiye — winget/choco
                win_cmd = next(
                    (c for c in tool.install_cmds if c.lower().startswith(("winget ", "choco "))),
                    tool.install_cmds[0] if tool.install_cmds else "",
                )
                console.print(
                    f"    [red]❌[/red]  {tool.name:<22} "
                    f"[dim]NOT INSTALLED[/dim]  → [yellow]{win_cmd}[/yellow]"
                )
                console.print(
                    "    [dim]     💡 Or use WSL2 for full Linux toolchain: "
                    "wsl --install[/dim]"
                )
            else:
                # Normal case — best install command dikhao
                install_hint = _pick_install_cmd(tool.install_cmds) or (
                    tool.install_cmds[0] if tool.install_cmds else ""
                )
                console.print(
                    f"    [red]❌[/red]  {tool.name:<22} "
                    f"[dim]NOT INSTALLED[/dim]  → [yellow]{install_hint}[/yellow]"
                )
                # dotnet global tools ke liye PATH hint — WSL/macOS pe common issue
                _DOTNET_GLOBAL = {"roslynator", "dotnet-stryker", "security-scan", "dotnet-format"}
                if tool.name in _DOTNET_GLOBAL and not is_windows:
                    console.print(
                        "    [dim]     💡 After install, add to PATH: "
                        "export PATH=$PATH:~/.dotnet/tools  (add to ~/.bashrc or ~/.zshrc)[/dim]"
                    )

    console.print()
    console.rule()
    console.print(f"\n  [bold]{available_count}/{total}[/bold] tools available")
    if available_count < total:
        if is_windows:
            console.print(
                "  Run [bold cyan]Lyncus install-deps[/bold cyan] to install missing tools"
            )
            console.print(
                "  [dim]💡 Windows tip: C++/CUDA tools ke liye WSL2 recommend hai "
                "→ [bold]wsl --install[/bold] → full Linux toolchain available hogi[/dim]\n"
            )
        else:
            console.print(
                "  Run [bold cyan]Lyncus install-deps[/bold cyan] to install missing tools\n"
            )


def _needs_sudo(cmd: str) -> bool:
    """Check karo ki command sudo chahta hai ya nahi (Linux apt-get/apt)."""
    return cmd.lower().startswith(("apt-get ", "apt "))


def _prepend_sudo_if_needed(cmd: str) -> str:
    """
    Linux pe apt-get/apt commands ke liye sudo prepend karo — agar:
      1. sudo available hai PATH mein
      2. Current user root nahi hai (UID != 0)
    WSL users typically sudo access rakhte hain lekin root nahi hote.
    Windows pe yeh function kabhi call nahi hona chahiye.
    """
    import platform as _p
    if _p.system().lower() != "linux":
        return cmd  # Non-Linux pe sudo concept nahi
    if not _needs_sudo(cmd):
        return cmd
    # Already root? sudo ki zaroorat nahi (getuid only Linux/macOS pe available)
    _getuid = getattr(os, "getuid", None)
    if _getuid is not None and _getuid() == 0:
        return cmd
    # sudo available hai?
    if shutil.which("sudo"):
        return f"sudo {cmd}"
    # sudo nahi — as-is return karo (fail hoga, user ko batao)
    return cmd


def _show_manual_install_hint(tool: "InstallSpec") -> None:
    """
    System-installer tools ke liye platform-specific manual install instructions dikhao.
    Windows → winget/choco, Linux → sudo apt-get, macOS → brew
    """
    import platform
    os_name = platform.system().lower()

    if os_name == "linux":
        apt_cmd = next((c for c in tool.install_cmds if c.lower().startswith(("apt-get ", "apt "))), None)
        if apt_cmd:
            console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: System installer chahiye")
            console.print(f"     Manual: [bold]sudo {apt_cmd}[/bold]")
            console.print(f"     WSL tip: [bold]sudo {apt_cmd}[/bold] — requires sudo/root access\n")
        else:
            console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: No Linux installer available")
            console.print(f"     Commands: {' / '.join(tool.install_cmds)}\n")

    elif os_name == "darwin":
        brew_cmd = next((c for c in tool.install_cmds if c.lower().startswith("brew ")), None)
        if brew_cmd:
            console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: Homebrew chahiye")
            console.print(f"     Manual: [bold]{brew_cmd}[/bold]\n")
        else:
            console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: No macOS installer available")
            console.print(f"     Commands: {' / '.join(tool.install_cmds)}\n")

    elif os_name == "windows":
        win_cmd = next(
            (c for c in tool.install_cmds if c.lower().startswith(("winget ", "choco "))), None
        )
        if win_cmd:
            console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: System installer chahiye")
            console.print(f"     Manual: [bold]{win_cmd}[/bold]\n")
        else:
            console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: No Windows installer available")
            console.print(f"     Commands: {' / '.join(tool.install_cmds)}\n")

    else:
        console.print(f"  [yellow]ℹ  {tool.name}[/yellow]: Manual install required")
        console.print(f"     Commands: {' / '.join(tool.install_cmds)}\n")


def install_missing(language: str = "all", dry_run: bool = False) -> None:
    """Install all missing tools for the given language."""
    import platform

    missing = get_missing_tools(language)

    if not missing:
        console.print("  [green]✅  All tools are already installed![/green]")
        return

    console.print(f"\n  [bold]Installing {len(missing)} missing tools...[/bold]\n")

    os_name = platform.system().lower()

    # Linux pe: agar non-root hai aur sudo available hai toh auto-sudo use karo
    # Windows pe: system tools (winget/choco) seedha run karo
    # macOS pe: brew commands seedha run karo

    for tool in missing:
        # Pick best install command for current OS
        cmd = _pick_install_cmd(tool.install_cmds)

        # System installer commands (apt/brew/winget) — special handling
        _SYSTEM_INSTALLER_PREFIXES = ("apt-get ", "apt ", "brew ", "winget ", "choco ")
        is_system_cmd = cmd and cmd.lower().startswith(_SYSTEM_INSTALLER_PREFIXES) if cmd else False

        if not cmd:
            _show_manual_install_hint(tool)
            continue

        # Linux apt commands: sudo prepend karo automatically
        if os_name == "linux" and cmd.lower().startswith(("apt-get ", "apt ")):
            cmd = _prepend_sudo_if_needed(cmd)
            # Agar sudo nahi mila aur root bhi nahi — manual hint deke skip karo
            _getuid2 = getattr(os, "getuid", None)
            is_root = _getuid2 is not None and _getuid2() == 0
            if not cmd.startswith("sudo") and not is_root:
                console.print(
                    f"  [yellow]⚠️   {tool.name}[/yellow]: "
                    f"sudo required for apt-get — run manually:"
                )
                console.print(f"     [bold]sudo {tool.install_cmds[0]}[/bold]\n")
                continue

        # Windows pe system tools (winget/choco) — elevated prompt needed ka check
        if os_name == "windows" and cmd.lower().startswith(("winget ", "choco ")):
            console.print(f"  [cyan]Installing {tool.name}...[/cyan]")
            console.print(f"  [dim]$ {cmd}[/dim]")
            # winget/choco require admin — try karo, fail pe helpful message
        else:
            console.print(f"  [cyan]Installing {tool.name}...[/cyan]")
            console.print(f"  [dim]$ {cmd}[/dim]")

        if dry_run:
            console.print("  [dim]  (dry-run — not actually running)[/dim]\n")
            continue

        try:
            # shell=False + shlex.split — safe from shell injection
            # Use sys.executable for pip commands to ensure the right pip is used
            safe_cmd = _make_safe_cmd(cmd)
            result = subprocess.run(
                safe_cmd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                console.print(f"  [green]✅  {tool.name} installed successfully[/green]\n")
                _refresh_importlib_caches()
            else:
                stderr_msg = result.stderr.strip()
                # Linux apt-get permission error — helpful message
                if "Permission denied" in stderr_msg or "lock" in stderr_msg.lower():
                    console.print(f"  [red]❌  {tool.name} install failed (permission denied):[/red]")
                    console.print(f"  [dim]{stderr_msg[:300]}[/dim]")
                    # sudo ke sath original command dikhao
                    apt_cmd = next(
                        (c for c in tool.install_cmds if c.lower().startswith(("apt-get ", "apt "))),
                        None
                    )
                    if apt_cmd and not apt_cmd.startswith("sudo"):
                        console.print(f"  [yellow]💡  Manually run:[/yellow] [bold]sudo {apt_cmd}[/bold]\n")
                    else:
                        console.print(f"  [yellow]💡  Manually run as root:[/yellow] [bold]{cmd}[/bold]\n")
                # Windows winget/choco admin error
                elif os_name == "windows" and ("administrator" in stderr_msg.lower() or "elevated" in stderr_msg.lower()):
                    console.print(f"  [red]❌  {tool.name} install failed (admin required):[/red]")
                    console.print(f"  [dim]{stderr_msg[:300]}[/dim]")
                    console.print(
                        f"  [yellow]💡  PowerShell as Administrator mein run karo:[/yellow] "
                        f"[bold]{cmd}[/bold]\n"
                    )
                else:
                    console.print(f"  [red]❌  {tool.name} install failed:[/red]")
                    console.print(f"  [dim]{stderr_msg[:200]}[/dim]\n")
        except subprocess.TimeoutExpired:
            console.print(f"  [red]❌  {tool.name} install timed out[/red]\n")
        except FileNotFoundError as e:
            console.print(f"  [red]❌  {tool.name}: executable not found — {e}[/red]")
            _show_manual_install_hint(tool)
        except Exception as e:
            console.print(f"  [red]❌  {tool.name}: {e}[/red]\n")


def install_tool_commands(commands: dict[str, str]) -> dict[str, bool]:
    """
    Install only the detected missing tools supplied by the scan pipeline.

    IMPORTANT — scan-safe auto-install policy:
      Scan ke dauraan SIRF lightweight package-manager commands chalte hain:
        pip, npm, cargo, go, rustup, gem, composer, dotnet, dart, vcpkg
      System package managers (winget, choco, brew, apt, apt-get, snap) KABHI
      AUTO-INSTALL NAHI HOTE scan ke time pe — yeh user ko prompt kiye bina
      system-level changes kar sakte hain aur bahut slow hote hain (timeout).
      Inke liye: 'Lyncus install-deps --lang <language>' manually chalao.
    """
    outcomes: dict[str, bool] = {}
    completed_commands: dict[str, bool] = {}

    # Sirf ye prefixes scan ke dauraan auto-install ke liye allowed hain
    # System package managers (winget/choco/brew/apt) BILKUL NAHI — woh:
    #   1. System-level changes karte hain bina user approval ke
    #   2. Bahut slow hote hain (winget = minutes, timeout hota hai)
    #   3. User ko Ctrl+C karna padta hai
    #
    # NOTE: "dotnet tool install" yahan se INTENTIONALLY HATA DIYA GAYA hai.
    # Reason: `dotnet tool install -g <pkg>` tab kaam karta hai jab .NET SDK
    # already installed ho. Scan ke time pe dotnet SDK install nahi kar sakte
    # (yeh system-level runtime hai, pip ki tarah nahi).
    # Agar dotnet available ho to dotnet tools Windows pe automatically detect
    # ho jaate hain. WSL/Linux mein dotnet install karna chahiye pehle:
    #   https://learn.microsoft.com/en-us/dotnet/core/install/linux
    # Phir: Lyncus install-deps --lang csharp
    SCAN_SAFE_PREFIXES = (
        "pip ", "pip3 ",
        "npm ",
        "cargo ",
        "go ",
        "rustup ",
        "gem ",
        "composer ",
        "dart ",
        "vcpkg ",
    )

    # System-level managers jo scan mein kabhi auto-run nahi honge
    SYSTEM_MANAGER_PREFIXES = (
        "winget ", "choco ", "brew ",
        "apt ", "apt-get ", "snap ",
    )

    # .NET tool installer — sirf tab kaam karta hai jab dotnet SDK installed ho.
    # SDK nahi hai to gracefully skip karo with install instructions.
    DOTNET_TOOL_PREFIX = "dotnet tool install"

    for name, install_text in commands.items():
        candidates = [part.strip() for part in install_text.split(" / ") if part.strip()]
        command = _select_platform_install_cmd(candidates)

        # System manager check — skip with clear message
        if command and command.lower().startswith(SYSTEM_MANAGER_PREFIXES):
            manager = command.split()[0]
            lang = _guess_language(name)
            # Linux pe: sudo hint deke skip karo
            import platform as _p
            if _p.system().lower() == "linux" and manager.lower() in ("apt", "apt-get"):
                console.print(
                    f"  [dim]ℹ  {name}: requires sudo apt-get — "
                    f"run manually: [bold]sudo {command}[/bold] "
                    f"or [bold]Lyncus install-deps --lang {lang}[/bold][/dim]"
                )
            else:
                console.print(
                    f"  [dim]ℹ  {name}: requires {manager} (system installer) — "
                    f"run [bold]Lyncus install-deps --lang {lang}[/bold] manually.[/dim]"
                )
            outcomes[name] = False
            continue

        # dotnet tool install — sirf tab chalao jab dotnet SDK available ho.
        # Agar dotnet nahi hai to gracefully skip karo with helpful message.
        if command and command.lower().startswith(DOTNET_TOOL_PREFIX.lower()):
            if shutil.which("dotnet") is None:
                console.print(
                    f"  [dim]ℹ  {name}: requires .NET SDK — "
                    f"install from https://aka.ms/dotnet-install then run "
                    f"[bold]Lyncus install-deps --lang csharp[/bold][/dim]"
                )
                outcomes[name] = False
                continue
            # dotnet available hai — proceed normally (dotnet tool install run karo)

        if not command or not command.lower().startswith(SCAN_SAFE_PREFIXES + (DOTNET_TOOL_PREFIX.lower(),)):
            console.print(f"  [dim]ℹ  {name}: no automatic installer available — "
                          f"run [bold]Lyncus install-deps[/bold] manually.[/dim]")
            outcomes[name] = False
            continue

        if command in completed_commands:
            outcomes[name] = completed_commands[command]
            console.print(f"  [dim]ℹ  {name}: shared package already handled.[/dim]")
            continue

        console.print(f"  [cyan]Installing {name}...[/cyan]")
        console.print(f"  [dim]$ {command}[/dim]")
        try:
            result = subprocess.run(
                _make_safe_cmd(command),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,   # 2 min max — pip/npm/cargo fast hote hain; winget blocked upar
                env={**os.environ, "PYTHONUTF8": "1"},
            )
        except subprocess.TimeoutExpired:
            console.print(f"  [red]❌  {name} install timed out[/red]")
            outcomes[name] = False
            completed_commands[command] = False
            continue
        except (OSError, ValueError) as error:
            console.print(f"  [red]❌  {name} install failed: {error}[/red]")
            outcomes[name] = False
            completed_commands[command] = False
            continue

        outcomes[name] = result.returncode == 0
        completed_commands[command] = outcomes[name]
        if result.returncode == 0:
            console.print(f"  [green]✅  {name} installed successfully[/green]")
            # importlib + shutil.which caches refresh karo taki same process mein
            # check_tool() naya installed package ko turant detect kar sake.
            _refresh_importlib_caches()
        else:
            details = result.stderr.strip() or result.stdout.strip()
            console.print(f"  [red]❌  {name} install failed: {details[:240]}[/red]")

    return outcomes


def _guess_language(tool_name: str) -> str:
    """Tool name se language guess karo — install-deps hint ke liye."""
    _tool_lang: dict[str, str] = {
        "cppcheck": "cpp", "clang-tidy": "cpp", "clang-tidy-cuda": "cpp",
        "cppcheck-cuda": "cpp", "nvcc": "cuda", "nvcc-warnings": "cuda",
        "compute-sanitizer": "cuda", "asan-cpp": "cpp", "ubsan-cpp": "cpp",
        "compsan-cpp": "cpp", "asan-cuda": "cuda", "ubsan-cuda": "cuda",
        "staticcheck": "go", "gosec": "go", "golangci-lint": "go", "deadcode": "go",
        "eslint": "javascript", "tsc": "javascript", "ts-prune": "javascript",
        "rubocop": "ruby", "brakeman": "ruby", "debride": "ruby",
        "phpcs": "php", "phpstan": "php", "psalm": "php",
        "pmd": "java", "spotbugs": "java",
        "detekt": "kotlin", "ktlint": "kotlin",
        "swiftlint": "swift",
        "semgrep": "csharp",   # C# SAST — semgrep csharp mein use hota hai
    }
    for key, lang in _tool_lang.items():
        if tool_name.startswith(key) or tool_name == key:
            return lang
    return "cpp"  # C++/CUDA most likely for system tools


def _select_platform_install_cmd(candidates: list[str]) -> str | None:
    """
    Choose a native package-manager command without falling back to another OS.
    Linux pe: apt commands ko sudo ke sath return karta hai agar non-root user hai.
    """
    import platform

    manager_prefixes = ("apt ", "apt-get ", "brew ", "choco ", "snap ", "winget ")
    manager_commands = [command for command in candidates if command.lower().startswith(manager_prefixes)]
    if manager_commands:
        os_name = platform.system().lower()
        expected_prefix = {
            "linux": ("snap ", "apt-get ", "apt "),
            "darwin": ("brew ",),
            "windows": ("winget ", "choco "),
        }.get(os_name, ())
        selected = next(
            (
                command
                for prefix in expected_prefix
                for command in manager_commands
                if command.lower().startswith(prefix) and shutil.which(prefix.strip())
            ),
            None,
        )
        # Linux: apt/apt-get command ko sudo ke sath return karo if non-root
        if selected and os_name == "linux":
            return _prepend_sudo_if_needed(selected)
        return selected

    return next(
        (command for command in candidates if command.lower().startswith((
            "pip ", "pip3 ", "npm ", "cargo ", "go ", "rustup ", "gem ",
            "composer ", "dotnet ", "dart ", "vcpkg ", "snap ", "winget ",
        ))),
        None,
    )


def _pick_install_cmd(cmds: list[str]) -> str | None:
    """
    Select the best install command for the current OS.
    Linux pe: apt commands ko sudo ke sath return karta hai agar non-root user hai.
    """
    import platform

    platform_prefixes = {
        "linux": ("apt-get ", "apt ", "snap "),
        "darwin": ("brew ",),
        "windows": ("winget ", "choco "),
    }.get(platform.system().lower(), ())
    platform_independent_prefixes = (
        "pip ",
        "npm ",
        "cargo ",
        "go ",
        "gem ",
        "composer ",
        "dotnet ",
        "rustup ",
        "phive ",
    )

    os_name = platform.system().lower()

    for prefix in platform_prefixes:
        for cmd in cmds:
            if cmd.lower().startswith(prefix) and shutil.which(prefix.strip()):
                # Linux apt commands: sudo prepend karo if needed
                if os_name == "linux":
                    return _prepend_sudo_if_needed(cmd)
                return cmd

    if any(cmd.lower().startswith(("apt ", "apt-get ", "brew ", "choco ", "winget ", "snap ")) for cmd in cmds):
        return None
    # Platform-independent package managers check karo
    match = next(
        (cmd for cmd in cmds if cmd.lower().startswith(platform_independent_prefixes)),
        None,
    )
    if match:
        return match
    # Fallback: koi known prefix nahi mila — pehla command return karo
    return cmds[0] if cmds else None


def _make_safe_cmd(cmd: str) -> list[str]:
    """
    Convert a string command to a safe list for subprocess.
    - Use sys.executable for pip commands (ensures the right pip is used on all platforms)
    - sudo prefix ko preserve karo (Linux apt-get ke liye)
    - Use shlex.split to avoid shell injection
    """
    parts = shlex.split(cmd)
    if not parts:
        return parts
    # sudo prefix — as-is rakhna hai (sudo pip3 → sudo pip3, etc.)
    if parts[0] == "sudo" and len(parts) >= 2:
        inner_cmd = parts[1]
        if inner_cmd in ("pip", "pip3"):
            # sudo pip → sudo python -m pip
            return ["sudo", sys.executable, "-m", "pip"] + parts[2:]
        return parts  # sudo apt-get etc. — as-is
    # 'pip' → sys.executable -m pip (correct pip on Windows too)
    if parts[0] == "pip":
        return [sys.executable, "-m", "pip"] + parts[1:]
    # also handle 'pip3'
    if parts[0] == "pip3":
        return [sys.executable, "-m", "pip"] + parts[1:]
    return parts
