FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 trading && useradd --uid 10001 --gid trading --no-create-home trading
COPY requirements/ requirements/
RUN pip install --no-cache-dir --require-hashes -r requirements/test.lock
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-build-isolation --no-deps .
COPY config/ config/
COPY tests/ tests/
COPY scripts/ scripts/
USER 10001:10001
CMD ["trading-platform", "validate-config", "/app/config/instances/paper.example.json"]
FROM base AS gateway-check
USER root
RUN pip install --no-cache-dir --require-hashes -r requirements/gateway.lock
USER 10001:10001
CMD ["python", "-c", "import ctrader_open_api; import twisted; import google.protobuf; print('Gateway imports OK')"]
FROM base AS runtime
