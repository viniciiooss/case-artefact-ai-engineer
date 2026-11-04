FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.3 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    EMPORIO_DATA_DIR=/app/data \
    EMPORIO_STATE_DIR=/app/var
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 emporio \
    && useradd --uid 10001 --gid emporio --no-create-home emporio

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-editable --extra observability \
    && mkdir -p /app/var \
    && chown emporio:emporio /app/var
COPY data/ ./data/

USER emporio
VOLUME ["/app/var"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"]
CMD ["/app/.venv/bin/emporio", "serve", "--host", "0.0.0.0", "--port", "8000"]
