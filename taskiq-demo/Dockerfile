# syntax=docker/dockerfile:1.6

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_EDITABLE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_TOOL_BIN_DIR=/usr/local/bin \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml .

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv sync --no-dev

RUN chmod +x /app/entrypoint.sh

USER nonroot

ENTRYPOINT ["/app/entrypoint.sh"]
