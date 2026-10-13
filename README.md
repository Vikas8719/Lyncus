# 🐺 Lyncus — Multi-Language Code Quality CLI Tool
> *"Jo dikhta nahi, woh pakad lega"*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI version](https://img.shields.io/badge/pypi-v1.0.0-green.svg)](https://pypi.org/project/Lyncus/)

---

## 🧠 Kya Hai Lyncus?

**Lyncus** ek powerful CLI tool hai jo aapke code ki teen sabse badi problems automatically pakad leta hai — chahe language koi bhi ho.

Jab aap AI se code likhwate hain ya khud likhte hain, teen cheezein hamesha galat hoti hain:

```
❌ PROBLEM 1 — Fake Tests     : assert True jaisa test jo kuch prove nahi karta
❌ PROBLEM 2 — Hardcoded Values: "/home/rahul/data.csv" ya password="admin123"
❌ PROBLEM 3 — Dead/Old Code  : Purane functions jo kabhi use nahi hote
```

**Lyncus in teeno ko terminal mein hi pakad leta hai — bina manual review ke.**

---

## ⚡ Quick Start

```bash
# Install
pip install Lyncus

# Apna project scan karo
Lyncus scan ./my-project

# Language specify karo
Lyncus scan ./src --lang python

# Sirf critical problems dikhao
Lyncus scan ./src --severity critical

# System check karo
Lyncus doctor
```

---

## 🎯 Core Philosophy

```
User → Project folder do
       ↓
Lyncus → Language automatically detect karta hai
       → Sahi tools automatically chalata hai
       → Output parse karta hai
       → Sirf problems dikhata hai
       ↓
Clean, readable terminal report milti hai
```

---

## 🌍 Supported Languages

| Language | Status | Tools Used |
|---|---|---|
| 🐍 Python | ✅ Full Support | ruff, mypy, bandit, vulture, mutmut, pytest-cov, pip-audit, radon |
| ⚙️ C++ | ✅ Full Support | clang-tidy, cppcheck, valgrind, flawfinder, lizard, AddressSanitizer |
| 🎮 CUDA | ✅ Full Support | compute-sanitizer, nsight-systems, nsight-compute, clang-tidy |
| 🔷 C# | ✅ Full Support | dotnet format, Roslyn, StyleCop, Stryker, security-scan, coverlet |
| ☕ Java | ✅ Full Support | checkstyle, spotbugs, find-sec-bugs, pitest, jacoco, pmd |
| 🦀 Rust | ✅ Full Support | clippy, rustfmt, cargo-audit, cargo-tarpaulin, cargo-machete |
| 🐹 Go | ✅ Full Support | staticcheck, gosec, golangci-lint, deadcode, gocognit |
| 🌐 JavaScript | ✅ Full Support | eslint, npm audit, ts-prune, c8, stryker-js |
| 📘 TypeScript | ✅ Full Support | tsc, eslint, ts-prune, c8, stryker-js |
| 💎 Ruby | ✅ Full Support | rubocop, brakeman, debride, simplecov |
| 🐘 PHP | ✅ Full Support | phpcs, phpstan, psalm, phan |
| 🎯 Kotlin | ✅ Full Support | detekt, ktlint |
| 🍎 Swift | ✅ Full Support | swiftlint, periphery |
| 🎯 Dart/Flutter | ✅ Full Support | dart analyze, flutter analyze |

---

## 🛠️ Teen Badi Problems — Har Language Mein

### ❌ Problem 1: Fake Tests
Test likha gaya lekin kuch prove nahi karta — `assert True` ya `assert result is not None` jaisa.

| Language | Tool | Version |
|---|---|---|
| Python | `mutmut` | 2.4+ |
| Java | `pitest` | 1.16+ |
| C# | `Stryker` | 3.13+ |
| JS/TS | `stryker-js` | 8.2+ |
| Rust | `cargo-mutants` | Latest |
| C++ | `mutate-cpp` | Latest |

### ❌ Problem 2: Hardcoded Values
Lyncus ka apna **custom regex engine** hai jo sab languages mein ye patterns dhundta hai:

```
🔴 Hardcoded paths    : /home/user/, C:\Users\, /root/
🔴 Credentials        : password=, api_key=, secret=, token=
🔴 Magic numbers      : = 42, = 9999, = 0.0034
🔴 Hardcoded URLs     : localhost:, http://192.168.
🔴 TODO/FIXME markers : TODO, FIXME, HACK, XXX
```

### ❌ Problem 3: Dead / Old Code
Purana code jo codebase mein pada hai lekin kabhi use nahi hota.

| Language | Tool |
|---|---|
| Python | `vulture` |
| C++ | `cppcheck` |
| Java | `PMD` |
| JS/TS | `ts-prune` |
| Rust | `cargo check` |
| Go | `deadcode` |
| C# | `Roslyn Analyzers` |

---

## 💻 Commands Reference

```bash
# ── SCAN COMMANDS ──────────────────────────────────────

# Basic scan — language auto detect karega
Lyncus scan ./my-project

# Specific language
Lyncus scan ./src --lang python
Lyncus scan ./src --lang cpp
Lyncus scan ./src --lang rust
Lyncus scan ./src --lang go
Lyncus scan ./src --lang java
Lyncus scan ./src --lang csharp
Lyncus scan ./src --lang javascript
Lyncus scan ./src --lang typescript

# Sirf ek type ki problem dikhao
Lyncus scan ./src --only hardcode
Lyncus scan ./src --only fake-tests
Lyncus scan ./src --only dead-code
Lyncus scan ./src --only security
Lyncus scan ./src --only coverage

# Severity filter
Lyncus scan ./src --severity critical
Lyncus scan ./src --severity warning
Lyncus scan ./src --severity all

# Output format
Lyncus scan ./src --output table     # default — terminal table
Lyncus scan ./src --output json      # JSON file
Lyncus scan ./src --output html      # HTML report

# Config file se
Lyncus scan ./src --config Lyncus.toml

# ── UTILITY COMMANDS ───────────────────────────────────

# System check — kaun se tools installed hain
Lyncus doctor

# Missing tools install karo
Lyncus install-deps --lang python
Lyncus install-deps --all

# Version
Lyncus --version

# Help
Lyncus --help
Lyncus scan --help
```

---

## 📊 Terminal Output — Kaisa Dikhega

```
🐺 Lyncus v1.0.0 — Code Quality Scanner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Project  : ./my-ml-project
🔍 Language : Python (auto-detected)
🛠  Tools    : ruff, mypy, bandit, vulture, mutmut, pytest-cov

Scanning... ████████████████████ 100%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ CRITICAL PROBLEMS (3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HARDCODE]   src/model.py:45   → "/home/rahul/data.csv" hardcoded path
[SECURITY]   src/auth.py:12    → password="admin123" hardcoded credential
[FAKE-TEST]  tests/test.py:67  → assert True — test kuch prove nahi karta

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  WARNINGS (5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[DEAD-CODE]  src/utils.py:23   → 'old_train()' function unused since 6 months
[TYPE]       src/model.py:89   → Return type annotation missing
[COMPLEX]    src/train.py:34   → Function complexity too high (score: 15/10)
[MAGIC-NUM]  src/config.py:5   → Magic number 0.0034 — naam wala constant use karo
[UNUSED]     src/utils.py:67   → Import 'os' declared but never used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  INFO (2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[COVERAGE]   tests/            → Branch coverage 45% (minimum: 80%)
[OUTDATED]   requirements.txt  → numpy 1.24 → 2.0 available

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Critical  :  3    ❌
  Warnings  :  5    ⚠️
  Info      :  2    ℹ️
  Score     :  42/100  🔴

  Time taken: 4.2s
  Files scanned: 23
```

---

## 🏗️ Project Architecture

```
Lyncus/
├── cli.py                    ← Entry point (Click commands)
├── core/
│   ├── detector.py           ← Language auto-detect engine
│   ├── runner.py             ← Tools ko async run karna
│   ├── parser.py             ← Tool output parse karna
│   └── reporter.py           ← Terminal/JSON/HTML report
├── languages/
│   ├── python_checks.py      ← Python ke tools config
│   ├── cpp_checks.py         ← C++ ke tools config
│   ├── cuda_checks.py        ← CUDA ke tools config
│   ├── csharp_checks.py      ← C# ke tools config
│   ├── java_checks.py        ← Java ke tools config
│   ├── rust_checks.py        ← Rust ke tools config
│   ├── go_checks.py          ← Go ke tools config
│   ├── js_checks.py          ← JS/TS ke tools config
│   ├── ruby_checks.py        ← Ruby ke tools config
│   └── php_checks.py         ← PHP ke tools config
├── rules/
│   ├── hardcode_rules.py     ← Hardcoded value regex patterns
│   ├── fake_test_rules.py    ← Fake test detection patterns
│   └── security_rules.py     ← Security vulnerability patterns
└── config/
    └── Lyncus.toml           ← Default config file
```

---

## ⚙️ Configuration — Lyncus.toml

```toml
[Lyncus]
version = "1.0"

[scan]
languages = ["auto"]        # ya ["python", "cpp", "rust"]
severity  = "all"           # critical / warning / all
output    = "table"         # table / json / html

[thresholds]
min_coverage     = 80       # % branch coverage minimum
max_complexity   = 10       # cyclomatic complexity maximum
mutation_score   = 75       # % mutation score minimum

[ignore]
paths = ["venv/", "node_modules/", ".git/", "dist/", "build/"]
rules = []                  # specific rules ignore karna ho toh

[hardcode]
check_paths       = true    # /home/, C:\Users detect karo
check_credentials = true    # password=, api_key= detect karo
check_magic_nums  = true    # = 42, = 9999 detect karo
check_urls        = true    # localhost, 192.168. detect karo

[tools]
skip_unavailable = true     # Jo tools install nahi hain unhe skip karo
```

---

## 🩺 Lyncus doctor — System Check

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
  ✅ pip-audit     2.7.3

C++ Tools:
  ✅ clang-tidy    18.0.0
  ✅ cppcheck      2.14.0
  ❌ valgrind      NOT INSTALLED → sudo apt install valgrind
  ✅ flawfinder    2.0.19

Rust Tools:
  ✅ clippy        (rustup component)
  ✅ rustfmt       (rustup component)
  ❌ cargo-audit   NOT INSTALLED → cargo install cargo-audit
  ❌ cargo-machete NOT INSTALLED → cargo install cargo-machete

Go Tools:
  ✅ staticcheck   2024.1
  ✅ gosec         2.20.0
  ❌ golangci-lint NOT INSTALLED → brew install golangci-lint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12/20 tools available
Run: Lyncus install-deps --all
```

---

## 🚀 Tech Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| CLI Framework | Click | 8.1+ |
| Terminal UI | Rich | 13.7+ |
| Config | TOML | Built-in |
| Async Runner | asyncio + subprocess | Built-in |
| Output Formats | Rich + JSON + HTML | — |
| Distribution | PyPI | pip install Lyncus |
| Testing | pytest + Hypothesis | pytest 8.0+, Hypothesis 6.100+ |

---

## 📅 Development Phases

```
Phase 1 — Core Engine           [🔄 In Progress]
  ✅ CLI framework (Click)
  ✅ Language auto-detector
  ✅ Tool runner (subprocess + asyncio)
  ✅ Output parser
  ✅ Terminal reporter (Rich)

Phase 2 — Main Languages        [📋 Planned]
  ⬜ Python (sabse pehle)
  ⬜ JavaScript / TypeScript
  ⬜ Rust
  ⬜ Go

Phase 3 — More Languages        [📋 Planned]
  ⬜ C++ + CUDA
  ⬜ C#
  ⬜ Java
  ⬜ Ruby, PHP

Phase 4 — Polish & Distribution [📋 Planned]
  ⬜ HTML report export
  ⬜ JSON output
  ⬜ CI/CD integration (GitHub Actions)
  ⬜ Lyncus.toml config support
  ⬜ PyPI publish
  ⬜ Lyncus install-deps command
```

---

## 🔄 Recommended Workflow

```
AI se code likhwao
        ↓
Lyncus scan ./src
        ↓
Problems list aa gayi terminal mein
        ↓
AI ko paste karo — "ye fix karo"
        ↓
Lyncus scan ./src  (dobara)
        ↓
Sab green ✅ = Production Ready
```

---

## 🤝 Contributing

```bash
git clone https://github.com/yourname/Lyncus
cd Lyncus
pip install -e ".[dev]"
pytest tests/
```

Naya language add karna ho toh:
1. `Lyncus/languages/newlang_checks.py` banao
2. Blueprint follow karo jo existing files mein hai
3. `detector.py` mein language register karo
4. PR bhejo!

---

## 📄 License

MIT License — Free to use, modify, and distribute.

---

## 👤 Author

**Lyncus** — Built with ❤️ for developers jo chahte hain ki unka code pehli baar hi sahi ho.

---

*🐺 Lyncus — Kyunki code review sirf insaan ka kaam nahi hona chahiye.*
