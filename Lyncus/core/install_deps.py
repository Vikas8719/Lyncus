"""
install_deps.py — Language tools auto-installer
Lyncus install-deps --lang python → missing tools install kar deta hai
"""

from __future__ import annotations

import shlex
import os
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
        "mutmut", "python", "mutmut", ["pip install 'mutmut>=3.0,<4'"], notes="Mutation testing"
    ),
    InstallSpec("radon", "python", "radon", ["pip install radon>=6.0"], notes="Complexity metrics"),
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
        "compsan-cpp",
        "cpp",
        "clang++",
        [
            "apt-get install -y clang",
            "brew install llvm",
        ],
        notes="Combined ASan+UBSan — maximum runtime error coverage (Linux/macOS only)",
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


def check_tool(tool: InstallSpec) -> bool:
    """Tool installed hai ya nahi check karo."""
    return shutil.which(tool.check_cmd) is not None


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
    tools = get_tools_for_language(language)
    if not tools:
        console.print(f"[red]Unknown language: {language}[/red]")
        return

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
            else:
                install_hint = tool.install_cmds[0] if tool.install_cmds else ""
                console.print(
                    f"    [red]❌[/red]  {tool.name:<22} "
                    f"[dim]NOT INSTALLED[/dim]  → [yellow]{install_hint}[/yellow]"
                )

    console.print()
    console.rule()
    console.print(f"\n  [bold]{available_count}/{total}[/bold] tools available")
    if available_count < total:
        console.print("  Run [bold cyan]Lyncus install-deps[/bold cyan] to install missing tools\n")


def install_missing(language: str = "all", dry_run: bool = False) -> None:
    """Install all missing tools for the given language."""
    missing = get_missing_tools(language)

    if not missing:
        console.print("  [green]✅  All tools are already installed![/green]")
        return

    console.print(f"\n  [bold]Installing {len(missing)} missing tools...[/bold]\n")

    for tool in missing:
        # Pick best install command for current OS
        cmd = _pick_install_cmd(tool.install_cmds)
        if not cmd:
            console.print(f"  [yellow]⚠️  {tool.name}[/yellow]: No auto-install available")
            console.print(f"     Manual install: {tool.install_cmds[0]}\n")
            continue

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
            else:
                console.print(f"  [red]❌  {tool.name} install failed:[/red]")
                console.print(f"  [dim]{result.stderr[:200]}[/dim]\n")
        except subprocess.TimeoutExpired:
            console.print(f"  [red]❌  {tool.name} install timed out[/red]\n")
        except FileNotFoundError as e:
            console.print(f"  [red]❌  {tool.name}: executable not found — {e}[/red]\n")
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
    #   3. User ko Ctrl+C karna padta hai (jaise LOGOS case mein hua)
    SCAN_SAFE_PREFIXES = (
        "pip ", "pip3 ",
        "npm ",
        "cargo ",
        "go ",
        "rustup ",
        "gem ",
        "composer ",
        "dotnet ",
        "dart ",
        "vcpkg ",
    )

    # System-level managers jo scan mein kabhi auto-run nahi honge
    SYSTEM_MANAGER_PREFIXES = (
        "winget ", "choco ", "brew ",
        "apt ", "apt-get ", "snap ",
    )

    for name, install_text in commands.items():
        candidates = [part.strip() for part in install_text.split(" / ") if part.strip()]
        command = _select_platform_install_cmd(candidates)

        # System manager check — skip with clear message
        if command and command.lower().startswith(SYSTEM_MANAGER_PREFIXES):
            manager = command.split()[0]
            console.print(
                f"  [dim]ℹ  {name}: requires {manager} (system installer) — "
                f"run [bold]Lyncus install-deps --lang {_guess_language(name)}[/bold] manually.[/dim]"
            )
            outcomes[name] = False
            continue

        if not command or not command.lower().startswith(SCAN_SAFE_PREFIXES):
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
    }
    for key, lang in _tool_lang.items():
        if tool_name.startswith(key) or tool_name == key:
            return lang
    return "cpp"  # C++/CUDA most likely for system tools


def _select_platform_install_cmd(candidates: list[str]) -> str | None:
    """Choose a native package-manager command without falling back to another OS."""
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
        return next(
            (
                command
                for prefix in expected_prefix
                for command in manager_commands
                if command.lower().startswith(prefix) and shutil.which(prefix.strip())
            ),
            None,
        )

    return next(
        (command for command in candidates if command.lower().startswith((
            "pip ", "pip3 ", "npm ", "cargo ", "go ", "rustup ", "gem ",
            "composer ", "dotnet ", "dart ", "vcpkg ", "snap ", "winget ",
        ))),
        None,
    )


def _pick_install_cmd(cmds: list[str]) -> str | None:
    """Select the best install command for the current OS."""
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

    for prefix in platform_prefixes:
        for cmd in cmds:
            if cmd.lower().startswith(prefix) and shutil.which(prefix.strip()):
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
    - Use shlex.split to avoid shell injection
    """
    parts = shlex.split(cmd)
    if not parts:
        return parts
    # 'pip' → sys.executable -m pip (correct pip on Windows too)
    if parts[0] == "pip":
        return [sys.executable, "-m", "pip"] + parts[1:]
    # also handle 'pip3'
    if parts[0] == "pip3":
        return [sys.executable, "-m", "pip"] + parts[1:]
    return parts
