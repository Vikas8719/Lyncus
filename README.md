<div align="center">

# 🐺 Lyncus

### Multi-Language Code Quality CLI Tool

*Catch fake tests, hardcoded values, and dead code — automatically, across any language.*

[![PyPI version](https://img.shields.io/pypi/v/Lyncus?color=brightgreen&logo=pypi&logoColor=white)](https://pypi.org/project/Lyncus/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PyPI Downloads](https://img.shields.io/pypi/dm/Lyncus?color=blue)](https://pypi.org/project/Lyncus/)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-red?logo=github-sponsors)](https://github.com/sponsors/Vikas8719)

[Installation](#-installation) · [Quick Start](#-quick-start) · [Commands](#-commands-reference) · [Configuration](#-configuration) · [Contributing](#-contributing)

</div>

---

## What is Lyncus?

**Lyncus** is a fast, language-agnostic CLI tool that automatically detects the three most common code quality problems that slip through manual review — whether you wrote the code yourself or generated it with AI.

| Problem | What Lyncus Catches |
|---|---|
| 🔴 **Fake Tests** | `assert True`, `assert result is not None` — tests that prove nothing |
| 🟠 **Hardcoded Values** | Paths, credentials, magic numbers, localhost URLs |
| 🟡 **Dead Code** | Unused functions, imports, and variables rotting in your codebase |

```bash
$ Lyncus scan ./my-project

🐺 Lyncus v1.0.0 — Code Quality Scanner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Project  : ./my-project
🔍 Language : Python (auto-detected)
🛠  Tools    : ruff, mypy, bandit, vulture

❌ CRITICAL (3)
[HARDCODE]  src/model.py:45   → "/home/user/data.csv" hardcoded path
[SECURITY]  src/auth.py:12    → password="admin123" hardcoded credential
[FAKE-TEST] tests/test.py:67  → assert True — test proves nothing

⚠️  WARNINGS (5)
[DEAD-CODE] src/utils.py:23   → 'old_train()' unused since 6 months
[MAGIC-NUM] src/config.py:5   → Magic number 0.0034 — use a named constant

📊 Score: 42/100 🔴  |  Files: 23  |  Time: 4.2s
```

---

## 🌍 Supported Languages

| Language | Status | Tools |
|---|---|---|
| 🐍 Python | ✅ Full Support | ruff, mypy, bandit, vulture, mutmut, pytest-cov, pip-audit, radon |
| 🌐 JavaScript | ✅ Full Support | eslint, npm audit, ts-prune, c8, stryker-js |
| 📘 TypeScript | ✅ Full Support | tsc, eslint, ts-prune, c8, stryker-js |
| 🦀 Rust | ✅ Full Support | clippy, rustfmt, cargo-audit, cargo-tarpaulin, cargo-machete |
| 🐹 Go | ✅ Full Support | staticcheck, gosec, golangci-lint, deadcode, gocognit |
| ☕ Java | ✅ Full Support | checkstyle, spotbugs, find-sec-bugs, pitest, jacoco, pmd |
| ⚙️ C++ | ✅ Full Support | clang-tidy, cppcheck, valgrind, flawfinder, lizard |
| 🎮 CUDA | ✅ Full Support | compute-sanitizer, nsight-systems, clang-tidy |
| 🔷 C# | ✅ Full Support | dotnet format, Roslyn, StyleCop, Stryker, coverlet |
| 💎 Ruby | ✅ Full Support | rubocop, brakeman, debride, simplecov |
| 🐘 PHP | ✅ Full Support | phpcs, phpstan, psalm, phan |
| 🎯 Kotlin | ✅ Full Support | detekt, ktlint |
| 🍎 Swift | ✅ Full Support | swiftlint, periphery |
| 🎯 Dart / Flutter | ✅ Full Support | dart analyze, flutter analyze |

---

## 📦 Installation

```bash
pip install Lyncus
```

**Verify installation:**

```bash
Lyncus --version
Lyncus doctor        # check which tools are available on your system
```

---

## ⚡ Quick Start

```bash
# Scan a project — language is auto-detected
Lyncus scan ./my-project

# Scan with a specific language
Lyncus scan ./src --lang python

# Show only critical issues
Lyncus scan ./src --severity critical

# Check only one problem type
Lyncus scan ./src --only fake-tests
Lyncus scan ./src --only hardcode
Lyncus scan ./src --only dead-code

# Export report
Lyncus scan ./src --output json
Lyncus scan ./src --output html

# System health check
Lyncus doctor
```

---

## 🛠 Commands Reference

```bash
# ── SCAN ──────────────────────────────────────────────────────────

Lyncus scan <path>                          # auto-detect language
Lyncus scan <path> --lang python            # force a specific language
Lyncus scan <path> --lang cpp
Lyncus scan <path> --lang rust
Lyncus scan <path> --lang go
Lyncus scan <path> --lang java
Lyncus scan <path> --lang csharp
Lyncus scan <path> --lang javascript
Lyncus scan <path> --lang typescript

# Filter by problem type
Lyncus scan <path> --only hardcode
Lyncus scan <path> --only fake-tests
Lyncus scan <path> --only dead-code
Lyncus scan <path> --only security
Lyncus scan <path> --only coverage

# Filter by severity
Lyncus scan <path> --severity critical
Lyncus scan <path> --severity warning
Lyncus scan <path> --severity all           # default

# Output formats
Lyncus scan <path> --output table           # default — terminal table
Lyncus scan <path> --output json            # machine-readable JSON
Lyncus scan <path> --output html            # shareable HTML report

# Use a config file
Lyncus scan <path> --config lyncus.toml

# ── UTILITY ────────────────────────────────────────────────────────

Lyncus doctor                               # show installed tools & versions
Lyncus install-deps --lang python           # install deps for a language
Lyncus install-deps --all                   # install all available deps
Lyncus --version
Lyncus --help
```

---

## ⚙️ Configuration

Create a `lyncus.toml` in your project root:

```toml
[lyncus]
version = "1.0"

[scan]
languages = ["auto"]          # or ["python", "rust", "go"]
severity  = "all"             # critical | warning | all
output    = "table"           # table | json | html

[thresholds]
min_coverage   = 80           # minimum branch coverage %
max_complexity = 10           # maximum cyclomatic complexity
mutation_score = 75           # minimum mutation score %

[ignore]
paths = ["venv/", "node_modules/", ".git/", "dist/", "build/"]
rules = []                    # specific rule IDs to suppress

[hardcode]
check_paths       = true      # detect /home/, C:\Users\
check_credentials = true      # detect password=, api_key=
check_magic_nums  = true      # detect = 42, = 9999
check_urls        = true      # detect localhost, 192.168.

[tools]
skip_unavailable = true       # skip tools that are not installed
```

---

## 🩺 System Check — `Lyncus doctor`

```
🐺 Lyncus — System Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Python Tools:
  ✅ ruff          0.4.2
  ✅ mypy          1.10.0
  ✅ bandit        1.7.9
  ✅ vulture       2.11.0
  ❌ mutmut        NOT INSTALLED → pip install mutmut
  ✅ pytest-cov    5.0.0

C++ Tools:
  ✅ clang-tidy    18.0.0
  ✅ cppcheck      2.14.0
  ❌ valgrind      NOT INSTALLED → sudo apt install valgrind

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12 / 20 tools available
Run: Lyncus install-deps --all
```

---

## 🏗 Project Architecture

```
Lyncus/
├── cli.py                    ← Entry point (Click commands)
├── core/
│   ├── detector.py           ← Language auto-detection engine
│   ├── runner.py             ← Async tool runner (subprocess + asyncio)
│   ├── parser.py             ← Tool output parser
│   └── reporter.py           ← Terminal / JSON / HTML reporter
├── languages/
│   ├── python_checks.py
│   ├── cpp_checks.py
│   ├── cuda_checks.py
│   ├── csharp_checks.py
│   ├── java_checks.py
│   ├── rust_checks.py
│   ├── go_checks.py
│   ├── js_checks.py
│   ├── ruby_checks.py
│   └── php_checks.py
├── rules/
│   ├── hardcode_rules.py     ← Regex patterns for hardcoded values
│   ├── fake_test_rules.py    ← Fake test detection patterns
│   └── security_rules.py     ← Security vulnerability patterns
└── config/
    └── lyncus.toml           ← Default configuration
```

---

## 🚀 Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| CLI Framework | Click 8.1+ |
| Terminal UI | Rich 13.7+ |
| Config Format | TOML (built-in) |
| Async Runner | asyncio + subprocess |
| Testing | pytest + Hypothesis |
| Distribution | PyPI |

---

## 🤝 Contributing

```bash
git clone https://github.com/Vikas8719/Lyncus
cd Lyncus
pip install -e ".[dev]"
pytest tests/
```

**Adding a new language:**
1. Create `Lyncus/languages/newlang_checks.py` — follow an existing file as blueprint
2. Register the language in `core/detector.py`
3. Add tests in `tests/`
4. Open a pull request

All contributions are welcome — bug reports, feature requests, and language support additions.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

Built with ❤️ by [Vikas8719](https://github.com/Vikas8719)

---

<div align="center">

**🐺 Lyncus — Because code review shouldn't be entirely a human job.**

[Report a Bug](https://github.com/Vikas8719/Lyncus/issues) · [Request a Feature](https://github.com/Vikas8719/Lyncus/issues) · [PyPI](https://pypi.org/project/Lyncus/)

</div>
