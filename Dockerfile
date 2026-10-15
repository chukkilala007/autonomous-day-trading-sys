# Scaffold image; pin a verified base digest before executable deployment.
FROM python:3.12-slim AS scaffold
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
RUN groupadd --gid 10001 trading && useradd --uid 10001 --gid trading --no-create-home trading
COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/
USER 10001:10001
CMD ["python", "-m", "trading_platform", "validate-config", "/app/config/instances/paper.example.json"]
