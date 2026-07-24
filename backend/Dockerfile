FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

FROM base AS production

RUN pip install . && \
    groupadd --gid 10001 reka && \
    useradd --uid 10001 --gid reka --create-home reka && \
    mkdir -p /app/data && \
    chown -R reka:reka /app

COPY run.py ./run.py

USER reka
EXPOSE 5001

CMD ["python", "run.py"]

FROM base AS test

RUN pip install ".[test]"
COPY tests ./tests

CMD ["python", "-m", "pytest", "-vv"]
