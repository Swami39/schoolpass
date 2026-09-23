# SchoolPass API / worker image (local dev & demo).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install .

# Migrations, helper scripts, entrypoint.
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY infra/docker/entrypoint.sh /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["api"]
