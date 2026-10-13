# ════════════════════════════════════════════════════════════════════════════
#  🐺 Lyncus — Multi-Language Code Quality Scanner
#  Docker image — production ready, minimal, secure
# ════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only pyproject.toml pehle — layer caching ke liye
COPY pyproject.toml README.md LICENSE ./
COPY Lyncus/ ./Lyncus/

# Wheel banao
RUN pip install --upgrade pip build \
    && python -m build --wheel --outdir /dist

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Lyncus Team <lyncus@example.com>" \
      org.opencontainers.image.title="Lyncus" \
      org.opencontainers.image.description="Multi-language code quality CLI — fake tests, hardcoded values aur dead code pakadta hai" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/yourname/Lyncus"

# Runtime dependencies (Node, Rust, Go, PHP, Ruby, Java lite tools ke liye)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # --- Core utils ---
    curl \
    git \
    # --- Node.js (JS/TS tools ke liye: eslint, tsc, stryker) ---
    nodejs \
    npm \
    # --- Java runtime (checkstyle, spotbugs ke liye) ---
    default-jre-headless \
    # --- Ruby (rubocop, brakeman ke liye) ---
    ruby \
    ruby-dev \
    # --- PHP (phpcs, phpstan ke liye) ---
    php \
    php-cli \
    && rm -rf /var/lib/apt/lists/*

# Go install (staticcheck, gosec ke liye)
ENV GOVERSION=1.22.3
RUN curl -fsSL "https://go.dev/dl/go${GOVERSION}.linux-amd64.tar.gz" \
    | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

# Rust install (clippy, cargo-audit ke liye)
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable
RUN rustup component add clippy rustfmt

# Non-root user — security best practice
RUN useradd -r -u 1001 -m -s /sbin/nologin lyncus

WORKDIR /app

# Wheel install — builder se copy karo
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl[python] \
    && rm /tmp/*.whl

# Python tools
RUN pip install --no-cache-dir \
    ruff \
    mypy \
    bandit \
    vulture \
    mutmut \
    pytest-cov \
    pip-audit \
    radon

# Go tools
RUN go install honnef.co/go/tools/cmd/staticcheck@latest \
    && go install github.com/securego/gosec/v2/cmd/gosec@latest \
    && go install github.com/nishanths/exhaustive@latest

# Rust tools
RUN cargo install cargo-audit cargo-machete

# Node.js tools (global)
RUN npm install -g \
    eslint \
    typescript \
    ts-prune \
    @stryker-mutator/core \
    @stryker-mutator/typescript-checker

# Ruby gems
RUN gem install rubocop brakeman --no-document

# Composer (PHP)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer
RUN composer global require --no-interaction \
    squizlabs/php_codesniffer \
    phpstan/phpstan \
    vimeo/psalm

ENV PATH="${PATH}:/root/.composer/vendor/bin"

# Scan target ko volume se mount karenge
VOLUME ["/scan"]
WORKDIR /scan

USER lyncus

# Default: help dikhao
ENTRYPOINT ["Lyncus"]
CMD ["--help"]
