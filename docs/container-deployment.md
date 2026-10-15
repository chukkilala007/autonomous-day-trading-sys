# Docker deployment contract

Docker containers are a required implementation target, not a later packaging exercise. Use Docker Compose on one host initially: Docker Desktop on the development Mac, Docker Engine on an always-on Linux host for sustained operation. Support linux/arm64 and linux/amd64 after dependency compatibility and image tests. Docker Desktop does not keep trading services running while its host sleeps.

Status: S4 paper stack implemented. Root Compose launches `core`, `worker-tpr`, `worker-timer` and `simulator`, plus a one-shot volume ownership initializer. Use the [README](../README.md) commands. The service table below describes the target production architecture; gateway, dashboard, supervisor, external feeds and demo/live overrides are still future work.

## Implemented paper deployment and limits

The Python 3.12 base image is digest-pinned, dependencies have hashed locks, and the runtime runs as UID 10001 with a read-only root. Only the volume initializer briefly runs as root, without networking and with limited filesystem capabilities. Worker and broker networks are internal and publish no ports. RPC is authenticated with instance-scoped tokens and bounded JSON; transport is plaintext on the private single-host networks, not suitable for a hostile/multi-host deployment.

Core is the sole SQLite WAL writer. Event/snapshot evidence is stored in the same transactional database volume at this stage. Simulator state is atomically persisted on an independent volume. `status --state` reads SQLite without starting another writer. Restart reconciles broker events before evaluation; instances show WARMING until a fresh input event passes coverage/reconciliation checks. A failed worker latches its instance halt; operator resume controls and data repair are S7/S5 work.

Input is a versioned synthetic/recorded JSON event file. The service polls it and durably checkpoints completed events; it does not retrieve prices or run a wall-clock trading schedule. The default finite scenario ends with two closed paper orders and zero open risk. Quotes and valuations are synthetic, explicitly supplied, and validated against event time. Paper account currency is GBP with starting balance 10000; changing account economics requires a reviewed simulator/configuration change.

Daily loss and streak breakers block new entries while allowing owned risk reduction; automatic account-wide emergency flattening and operator controls are not implemented in S4. Existing paper protection/timed exits execute on subsequent supplied ticks. There is no guarantee of a close without a new executable quote. All contracts currently use the verified linear risk model; nonlinear instruments reject. Strategy packages are reviewed trusted code, not arbitrary untrusted programs.

CI builds the deployment, runs the container suite, and runs `scripts/paper_smoke.py`, an isolated open-exposure crash/restart drill. ARM64 local verification does not establish AMD64 qualification; CI results must be inspected separately. Backups, retention, log rotation, load/soak testing, TLS across hosts and disaster recovery remain S7 release gates.

## Services

| Service | Contents | Persistent access | Connectivity |
|---|---|---|---|
| core | Scheduler, registry, account risk, order lifecycle and single database writer | State and evidence volumes | Worker, broker and control networks |
| strategy-INSTANCE | One configured strategy instance and its runtime dependencies | No operational database or broker credentials; state supplied by core | Worker network only |
| gateway | cTrader SDK, broker connection and fenced command transport | Restricted token-rotation volume; injected broker secrets | Broker network plus external egress |
| dashboard | Read-only status UI initially | None; queries core | Control network; host loopback port only |
| supervisor | Heartbeat and reconciliation checks; entry-inhibition requests | None | Control network |
| replay/test | One-shot replay, simulator and test commands | Isolated test volume or read-only fixtures | No broker access |

Use one reviewed image with separate targets/commands where dependencies overlap. A strategy with incompatible ML dependencies can have its own pinned image while retaining the same protocol. Scale analysis by adding explicit instance services; do not replicate the core or gateway. The core enforces instance identity and rejects duplicate registration.

Default Compose launches offline/paper mode with a simulator and no broker credentials. Explicit demo and live override files select the real gateway and bind the matching account/environment. A profile or environment variable alone is not authorization to trade: core and gateway must validate the immutable deployment mandate and account identity. Separate Compose project names and volumes for each account/mode. Never mount a paper database into a live stack.

## Networking and isolation

Use internal worker, broker and control networks. Only the gateway joins an egress-enabled network for broker/authentication traffic. No host ports for core, gateway or workers; publish the optional dashboard on 127.0.0.1 only. Internal services authenticate clients and enforce role/instance permissions; network separation is not a substitute for authorization.

Core/worker and core/gateway messages use bounded, versioned, length-framed JSON over TCP with acknowledgements, sequence numbers, deadlines and replay/reconciliation behavior. Reconnect through Compose service DNS. Cross-container transport replaces the earlier host-local Unix-socket proposal.

If a strategy needs an external model or data provider, add a scoped service with controlled egress and its own secrets. Workers do not receive broker credentials or unrestricted provider keys. Docker networks alone do not implement destination allowlists; enforce any required allowlists through host/network policy or an egress proxy.

Run non-root with a read-only root filesystem, explicit writable mounts, tmpfs for temporary files, dropped Linux capabilities, no-new-privileges, resource/PID limits and bounded logs. No privileged mode, host networking or Docker socket mounts. Containers are intended for reviewed strategy packages; arbitrary untrusted code requires an additional isolation design.

## Durable storage and secrets

Keep SQLite, its WAL and shared-memory files together in a named volume mounted only by core. SQLite remains suitable for the initial single-writer, single-host topology. On Docker Desktop use a named Linux volume rather than a source-tree bind mount for the database. Dashboard access goes through the core API. Explicitly initialize volume ownership for the runtime UID.

Store immutable evidence in a separate named volume. Export consistent database backups through the core using SQLite's backup API, paired with evidence references and manifest hashes. Copy completed backups off the host and test restore plus broker reconciliation. Named volumes are persistence, not backups; normal operations must not use destructive volume-removal commands.

Mount broker credentials only into gateway using Compose secrets. Local file-backed Compose secrets do not themselves provide an encrypted secret store: protect their source files or provision them from a host secret manager. Keep credentials out of Git, build context, image layers, logs and command-line arguments. Treat .env as non-secret deployment settings. Read-only injected secrets cannot store rotated OAuth tokens; gateway writes refreshed tokens atomically to its restricted volume or a suitable external secret store. Protect and back up that state separately from public artifacts.

Source: [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets).

## Readiness, restart and shutdown

Define distinct liveness and readiness checks. A running process is not trading-ready: core requires completed migrations, valid configuration, data coverage and broker reconciliation. Gateway readiness requires account authorization and a healthy connection; analysis readiness requires a loaded package and warm-up history. Closed markets are normal states, not restart triggers.

Use health-gated startup dependencies where appropriate, without circular core/gateway readiness requirements: gateway can establish transport/account connectivity independently; core subsequently reconciles. Every service must also handle dependency loss after startup. Compose startup health ordering does not provide continuous application recovery. [Docker startup-order documentation](https://docs.docker.com/compose/how-tos/startup-order/).

Set restart policies for long-running services, for example unless-stopped. A Docker healthcheck marking a container unhealthy does not itself restart it. Fatal unrecoverable process errors may exit for restart; stale data or policy breaches inhibit trading and retain diagnostics. No restart resets daily loss limits, ownership, reservations or a latched halt.

Use init/signal handling and an explicit stop grace period. On planned shutdown: inhibit entries, persist intent/state, request cancellation of owned pending orders when connected, reconcile acknowledgements, and flush storage. Existing protected positions remain governed by their recorded policy; stopping a container is not a command to flatten. Unconfirmed cancellation stays unresolved for startup reconciliation. Broker-side protection and pending expiry are mandatory for profiles that rely on them during outages.

Before upgrade, drain new entries and preserve old strategy management versions for open exposure. Back up, apply compatible versioned migrations, replace containers, reconcile and then resume if policy allows. A rollback must be schema-compatible; replacing an image is not sufficient if migrations cannot be reversed. Do not run blue/green order executors against the same account. Compose itself does not enforce a cross-host single-writer guarantee: restrict account credentials to the designated deployment; multi-host failover requires external fencing before it is supported.

## Implementation acceptance

1. Build images from a clean checkout with pinned dependencies/base image; no host Python or personal skill installation is required.
2. A single documented Compose invocation starts a functioning paper-mode stack and strategy fixture without credentials.
3. Validate merged paper/demo/live Compose configuration in CI; test both target architectures before claiming support.
4. Kill and recreate core/worker/gateway containers during simulated submission and fill events; prove preserved risk state, reconciliation and no duplicate orders.
5. Verify named-volume persistence, backup/restore, resource exhaustion behavior and loopback-only UI exposure.
6. Verify workers cannot reach gateway directly or access its secrets/database; malformed messages fail closed.
7. Demonstrate that unhealthy/stale services inhibit entries, and that restarts do not bypass trading halts.
8. Demonstrate shutdown with unresolved broker acknowledgements and recovery without assuming an order was cancelled.

The offline scaffold supplies Dockerfile, .dockerignore, Compose validation and container test execution. The first runtime milestone adds service build targets, a functioning paper stack and startup/restart smoke tests. Broker-connected overrides follow when the real gateway is implemented.
