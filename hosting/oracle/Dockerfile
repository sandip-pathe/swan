FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.12.5 \
    && groupadd --gid 10001 swan \
    && useradd --uid 10001 --gid swan --create-home swan
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python
COPY --chown=10001:10001 services ./services
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 alembic.ini ./
RUN mkdir -p /app/.local && chown 10001:10001 /app/.local
ENV PATH="/app/.venv/bin:$PATH"
USER 10001:10001
CMD ["python", "-m", "uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
