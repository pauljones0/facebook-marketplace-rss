# --- Build Stage ---
FROM rust:latest AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y pkg-config libssl-dev sqlite3 libsqlite3-dev build-essential

COPY . .
RUN cargo build --release

# --- Final Stage ---
FROM debian:bookworm-slim

LABEL maintainer="bethekind"
ENV CONFIG_FILE="/app/config.json"

WORKDIR /app

# Install runtime dependencies: Firefox and required libs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    gpg \
    ca-certificates \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    sqlite3 && \
    install -d -m 0755 /etc/apt/keyrings && \
    wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null && \
    echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null && \
    echo 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' | tee /etc/apt/preferences.d/mozilla && \
    apt-get update && \
    apt-get install -y firefox && \
    apt-get purge -y wget gpg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy the binary from the builder
COPY --from=builder /app/target/release/facebook-marketplace-rss /app/fb_ad_monitor

# Copy static assets and templates
COPY static /app/static
COPY templates /app/templates

# Install curl for HEALTHCHECK (must be done as root before USER switch)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose the server port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["./fb_ad_monitor"]
