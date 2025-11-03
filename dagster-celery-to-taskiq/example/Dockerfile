# Adapted from: https://github.com/astral-sh/uv-docker-example/blob/5748835918ec293d547bbe0e42df34e140aca1eb/Dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

WORKDIR /app

RUN apt-get update \
    && apt-get install -y libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_EDITABLE=1 \
    UV_NO_SYNC=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_TOOL_BIN_DIR=/usr/local/bin \
    PATH="/opt/venv/bin:${PATH}" \
    UV_PROJECT_ENVIRONMENT=/opt/venv

ENV DAGSTER_HOME=/opt/dagster/dagster_home
RUN mkdir -p $DAGSTER_HOME \
    && chown -R nonroot:nonroot /opt/dagster

COPY ../uv.lock /dagster-taskiq/uv.lock
COPY ../pyproject.toml /dagster-taskiq/pyproject.toml
COPY ../src/dagster_taskiq/__init__.py /dagster-taskiq/src/dagster_taskiq/__init__.py
RUN --mount=type=cache,id=uv-cache,sharing=locked,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,readonly \
    uv sync --locked --no-dev --no-install-project

COPY ../ . /dagster-taskiq/
COPY --chown=nonroot:nonroot . /app
RUN --mount=type=cache,id=uv-cache,sharing=locked,target=/root/.cache/uv \
    uv sync --locked --no-dev --offline

USER nonroot

EXPOSE 3030

CMD ["dagster", "api", "grpc", "--host", "0.0.0.0", "--port", "3030", "--python-file", "./src/dagster_celery_example/definitions.py"]