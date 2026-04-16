# ── Stage 1: Build ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools (uv for fast dependency resolution)
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Export locked dependency versions and install them
RUN uv export --frozen --no-dev --extra gcs --no-emit-project > requirements.txt \
    && uv pip install --system -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ src/
COPY knowledge/ knowledge/

# Create output directory (used as local cache even when GCS is primary)
RUN mkdir -p output/prds logs

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -m appuser \
    && chown -R appuser:appuser /app
USER appuser

# ── Environment defaults ──────────────────────────────────────────────
ARG VERSION=dev
ENV APP_VERSION=${VERSION}

# Cloud Run sets PORT automatically; fall back to 8000 locally
ENV PORT=8000 \
    # Structured JSON to stdout for GCP Cloud Logging
    LOG_TARGET=stdout \
    # Server environment — PROD disables ngrok/dev features
    SERVER_ENV=PROD \
    # Python optimisations
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Make src/ importable without pip install -e
    PYTHONPATH=/app/src

# Health check — Cloud Run also probes this
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')"

EXPOSE ${PORT}

# Start the FastAPI server via uvicorn
CMD ["sh", "-c", "uvicorn crewai_productfeature_planner.apis:app --host 0.0.0.0 --port ${PORT} --workers 1"]
