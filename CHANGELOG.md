## [1.0.0] — 2026-10-07 🎉

### 🚀 Initial Release — Lyncus v1.0.0

**"Jo dikhta nahi, woh pakad lega"**

---

### ✨ Features

#### Languages Supported (10+)

- 🐍 **Python** — ruff, mypy, bandit, vulture, mutmut, radon, pip-audit
- ⚙️ **C++** — clang-tidy, cppcheck, flawfinder, lizard, valgrind
- 🎮 **CUDA** — compute-sanitizer, nvcc warnings, static pattern analyzer
- 🔷 **C#** — dotnet-format, Roslyn, Stryker, Coverlet, Roslynator
- ☕ **Java** — checkstyle, spotbugs, find-sec-bugs, pitest, jacoco, pmd
- 🦀 **Rust** — clippy, rustfmt, cargo-audit, cargo-tarpaulin, cargo-machete
- 🐹 **Go** — staticcheck, gosec, golangci-lint, deadcode
- 🌐 **JavaScript/TypeScript** — eslint, tsc, ts-prune, c8, stryker-js
- 💎 **Ruby** — rubocop, brakeman, debride, reek, flog, bundler-audit
- 🐘 **PHP** — phpcs, phpstan, psalm, phan, composer-audit, phpcpd

#### Core Features

- 🔍 **Auto language detection** — 14 languages detect karta hai
- 🚫 **Fake test detection** — mutmut, pitest, stryker se mutation testing
- 💉 **Hardcoded value scanner** — credentials, paths, magic numbers, URLs
- 💀 **Dead code finder** — vulture, ts-prune, deadcode, debride
- 🔒 **Security scanning** — bandit, gosec, brakeman, psalm taint analysis

#### Output Formats (Phase 3-4)

- 📊 **Terminal table** — Rich-powered colored output
- 📄 **JSON** — Machine-readable, CI/CD ke liye
- 🌐 **HTML** — Dark theme, interactive filter/sort/search
- 🔬 **SARIF** — GitHub Advanced Security ke saath integrate karo
- 🏷️ **SVG Badges** — README mein quality score dikhao

#### CLI Commands

```bash
Lyncus scan ./project              # Basic scan
Lyncus scan . --output all         # Sab formats generate karo
Lyncus scan . --only hardcode      # Sirf hardcoded values
Lyncus scan . --ci-mode            # CI/CD mode
Lyncus doctor                      # Tools check karo
Lyncus install-deps --lang python  # Missing tools install karo
Lyncus init                        # Lyncus.toml banao
Lyncus badge --score 87            # SVG badge generate karo
```

Lyncus
Lyncus

#### Configuration

- 📝 **Lyncus.toml** — Full config file support
- 🔧 **pyproject.toml** — `[tool.Lyncus]` section support
- 🌐 **~/.Lyncus.toml** — Global user config

#### CI/CD Integration

- 🔄 **GitHub Actions** — Built-in workflow template
- 💬 **PR Comments** — Automatic quality report on PRs
- ❌ **Fail on critical** — Configurable exit codes

---

### 📦 Install

```bashLyncus
pip install Lyncus
Lyncus --version
Lyncus doctor
```

---
