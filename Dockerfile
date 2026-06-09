FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml ./
COPY app/ ./app/

# Install production dependencies only
RUN pip install --no-cache-dir \
    fastapi>=0.111.0 \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "kubernetes>=30.1.0" \
    "httpx>=0.27.0" \
    "python-multipart>=0.0.9"

# ── Final image ────────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="BB-8 Kubernetes Sidekick" \
      org.opencontainers.image.description="Air-gapped Kubernetes sidekick with local LLM reasoning" \
      org.opencontainers.image.source="https://github.com/h3ow3d/bb-8" \
      org.opencontainers.image.licenses="MIT"

# Create non-root user
RUN groupadd --gid 1001 bb8 && \
    useradd --uid 1001 --gid bb8 --no-create-home --shell /sbin/nologin bb8

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy application code
COPY app/ ./app/

# Create data and knowledge directories
RUN mkdir -p /data/audit /knowledge && \
    chown -R bb8:bb8 /data /knowledge /app

USER bb8

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
