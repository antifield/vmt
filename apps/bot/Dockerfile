# libsql publishes no linux/aarch64 wheel, so build with --platform linux/amd64
# on Apple Silicon until https://github.com/tursodatabase/libsql-python/issues/108
# ships (prod targets are amd64 anyway)
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src

# only dependencies are installed into the venv; the pure-Python project
# itself runs straight from src
ENV PYTHONPATH=/app/src

RUN groupadd --system vmt \
    && useradd --system --gid vmt --home-dir /app vmt \
    && mkdir -p /app/data \
    && chown -R vmt:vmt /app

USER vmt

CMD ["uv", "run", "--no-sync", "python", "-m", "vmt"]
