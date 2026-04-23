# ─────────────────────────────────────────────────────────────
# URGP — Multi-stage Dockerfile (API + Worker)
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install Poetry
RUN pip install poetry==1.8.5 && \
    poetry config virtualenvs.create false

# Copy dependency files first for caching
COPY pyproject.toml poetry.lock* README.md ./

# Install dependencies (no dev deps for production)
RUN poetry install --no-interaction --no-ansi --no-root --only main || \
    poetry install --no-interaction --no-ansi --no-root

# Copy source code
COPY src/ ./src/

# Install the project itself
RUN poetry install --no-interaction --no-ansi --only-root

# ── Stage 2: Runtime ───────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Create non-root user
RUN groupadd --gid 1000 urgp && \
    useradd --uid 1000 --gid urgp --shell /bin/bash --create-home urgp

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Set ownership
RUN chown -R urgp:urgp /app

USER urgp

EXPOSE 8000

# Default command: run the API server
CMD ["uvicorn", "urgp.main:app", "--host", "0.0.0.0", "--port", "8000"]
