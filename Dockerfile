FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 trading && useradd --uid 10001 --gid trading --no-create-home trading

FROM python-base AS base
COPY requirements/ requirements/
RUN pip install --no-cache-dir --require-hashes -r requirements/test.lock
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-build-isolation --no-deps .
COPY config/ config/
COPY tests/ tests/
COPY scripts/ scripts/
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS gateway-check
USER root
RUN pip install --no-cache-dir --require-hashes -r requirements/gateway.lock
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM python-base AS runtime
COPY requirements/core.lock /tmp/core.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/core.lock && rm /tmp/core.lock
COPY --from=base /usr/local/lib/python3.12/site-packages/trading_platform /usr/local/lib/python3.12/site-packages/trading_platform
COPY --from=base /usr/local/lib/python3.12/site-packages/autonomous_day_trading_sys-0.1.0.dist-info /usr/local/lib/python3.12/site-packages/autonomous_day_trading_sys-0.1.0.dist-info
COPY --from=base /usr/local/bin/trading-platform /usr/local/bin/trading-platform
COPY config/ config/
COPY tests/fixtures/ tests/fixtures/
USER 10001:10001
CMD ["trading-platform", "status"]

FROM runtime AS gateway
USER root
COPY requirements/gateway.lock /tmp/gateway.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/gateway.lock && rm /tmp/gateway.lock
USER 10001:10001
CMD ["python", "-m", "trading_platform.gateways.ctrader.service", "--help"]

FROM runtime AS final
