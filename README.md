# Autonomous Day Trading System

Strategy-independent trading platform targeting Docker Compose. **Current stage: repository scaffold.** The CLI validates an offline configuration example; strategy loading, simulation, broker connectivity and trading are not implemented yet.

## Quick start

With Docker and Docker Compose installed, run from this repository:

```sh
docker compose up --build --abort-on-container-exit --exit-code-from validate
docker compose --profile tools run --rm tests
```

The first command builds the image, validates the example configuration and exits. No credentials, network access from the container, or broker connection are required. A successful validation does not mean the named strategy exists or that the configuration is executable.

Optional local checks with Python 3.12 or newer:

```sh
PYTHONPATH=src python3 -m trading_platform status
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Layout

```text
config/                  Account-policy and strategy-instance examples
deploy/                  Deployment guidance
src/trading_platform/
  contracts/             Typed inputs and decisions
  registry/              Strategy packages and capability checks
  runtime/               Worker scheduling and transport
  market_data/           Feed normalization and validation
  portfolio/             Ownership and capital allocation
  risk/                  Limits, sizing and reservations
  execution/             Order lifecycle and reconciliation
  persistence/           Durable state and migrations
  gateways/ctrader/      cTrader integration boundary
  strategies/tpr1/       First strategy adapter boundary
  simulation/            Replay and paper execution
  observability/         Health and operational metrics
tests/                   Scaffold tests and future acceptance-test areas
docs/                    Architecture, contracts and build plan
.github/workflows/       Container-based CI
```

Module directories are explicit implementation boundaries, not completed services. The scaffold has no third-party runtime dependencies. The Python base image and build-tool versions must be locked after the broker compatibility spike; the current Docker tag is not a reproducible digest pin.

## Design documents

* [Architecture](docs/autonomous-scalping-agent.md)
* [Strategy API v1](docs/strategy-contract.md)
* [Implementation plan](docs/implementation-plan.md)
* [Docker deployment](docs/container-deployment.md)
* [Initial artifact migration record](artifact-migration.json)

Next milestone: generic strategy registry, causal replay, isolated workers and durable state, tested using TPR-1 and a different timer-based fixture. Then add shared risk and paper execution before real broker integration.

## Existing research dependencies

Design references to `skills/` and `reporting/` describe the original private research workspace. Those resources are not part of this repository and are not required for the scaffold checks. Port a reviewed, pinned TPR baseline with provenance and fixtures when implementing the first adapter. Do not import mutable personal skill folders or existing alert-monitor state at runtime.

Secrets, account records and runtime databases are excluded from Git and Docker build context. Future demo/live deployment requires explicit account binding and separate configuration. The existing repository license is preserved in [LICENSE](LICENSE).
