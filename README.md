# Autonomous Day Trading System

Strategy-independent paper-trading platform running in Docker Compose. **S1–S4 are implemented:** versioned strategy packages, isolated analysis workers, durable decisions, shared portfolio risk, order reconciliation and a persistent simulated broker. TPR-1 and a different timer strategy exercise the same core.

## Run the paper stack

With Docker and Docker Compose installed, run from this repository:

```sh
docker compose up --build -d
docker compose logs -f core
```

The default stack processes four deterministic synthetic market events. Both strategies independently propose entries; core validates and sizes them; the simulator fills and closes the trades. After completion, the services remain running, waiting for new input. This is a reproducible paper scenario, not a live market feed or a strategy performance assessment.

```sh
docker compose exec core trading-platform status --state /state/core.db
docker compose --profile tools run --rm validate
docker compose --profile tools run --rm tests
python3 scripts/paper_smoke.py
docker compose down
```

`paper_smoke.py` launches a unique isolated test project, kills core with open exposure, restarts the workers and simulator, verifies closure without duplicate orders, and removes only that test project's volumes. Normal `docker compose down` preserves your state. Existing completed input events are skipped on restart; use a separate Compose project name for a fresh scenario.

The default stack has no external network, published ports, real broker endpoint or broker credentials. Checked-in RPC tokens are public **synthetic test credentials**, suitable only for this isolated paper setup. Workers have no operational database mount. Core and simulator use separate named volumes, non-root runtime users and read-only root filesystems.

## Implementation tracking

The [implementation tracker](docs/implementation-plan.md) records feature status, test evidence, limitations and the next concrete action. Each implemented feature has its own `feature/<name>` branch merged into `develop` after passing tests. See [repository working instructions](AGENTS.md).

S5–S7 implementation slices add a demo read-only gateway and isolated shadow workers, capability-gated demo transport and recovery components, authenticated dashboard/controls, hardened images, and paper backup/restore tooling. **S5–S7 are not qualified for autonomous broker trading.** Actual provider evidence, the integrated demo core adapter, authorized demo lifecycle tests and intended-host release checks remain open in the tracker.

See [provider setup](docs/evidence/provider-contract.md) for the separate read-only shadow Compose project, and [operations](deploy/operations.md) for the optional dashboard (`docker compose --profile ui up --build -d`), controls, backup and recovery. The demo order components are tested with fake transport; no enabled demo or live trading service is shipped.

## Layout

| Path | Purpose |
|---|---|
| `config/` | Versioned deployment mandates, reviewed manifests and paper topology |
| `src/trading_platform/contracts/` | Strict values, events, snapshots and decisions |
| `src/trading_platform/registry/` | Digest and capability validation |
| `src/trading_platform/runtime/` | Journal, recovery, worker RPC and paper orchestration |
| `src/trading_platform/portfolio/`, `risk/` | Ownership, arbitration, sizing and atomic reservations |
| `src/trading_platform/execution/` | Durable outbox, lifecycle and reconciliation |
| `src/trading_platform/strategies/` | Pinned TPR-1 adapter and timer fixture |
| `src/trading_platform/simulation/` | Causal replay and persistent tick-driven broker |
| `requirements/` | Hashed dependency locks for Python 3.12 |
| `tests/` | Contracts, causality, risk, execution and crash recovery |
| `docs/` | Design, implementation tracker and decisions |

The gateway contains TLS/authentication, normalized history/stream data, read-only snapshot RPC and opt-in demo execution components. Observability includes durable alerts; `api/` provides authenticated status and controls. Tests distinguish synthetic transport evidence from actual broker qualification.

## Design and extension

* [Architecture](docs/autonomous-scalping-agent.md)
* [Strategy API v1](docs/strategy-contract.md)
* [Docker deployment and current operating limits](docs/container-deployment.md)
* [Technical implementation notes](docs/implementation-notes.md)

Add a reviewed strategy package implementing the common interface, register its digest and capabilities, and configure its instance/worker. Core contains no concrete strategy imports. The timer fixture demonstrates a different timeframe and timed exit without changes to core risk/execution. TPR research code was ported with provenance into the repository; no personal skill directory is loaded at runtime.

Secrets, account records and runtime databases are excluded from Git and Docker build context. The existing repository [license](LICENSE) is preserved.
