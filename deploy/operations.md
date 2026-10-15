# Single-host operating runbook

Release state: paper operations are implemented; actual demo/production qualification remains blocked. Do not use this runbook to activate live trading. The only headless broker process currently exposed is demo read-only collection. No live endpoint is configured.

## Paper services and dashboard

Run `docker compose --profile ui up --build -d` on a Linux Docker host or Docker Desktop. The dashboard is at `http://127.0.0.1:8080`. Enter the reader token from `tests/smoke/reader-token.txt` for the public synthetic paper fixture only. Real deployments must replace test token files with unique private secrets. Dashboard has no DB/credential mount and can be restarted independently. Its proxy forwards authentication to core; it never embeds a token in HTML or browser storage.

Core `/health` reports process liveness; authenticated `/ready` requires fresh market events and ready, unhalted instances. A completed synthetic scenario is correctly stale. Docker health status does not itself restart an unhealthy container or make trading ready. Reconciliation, data freshness and entry gates remain application checks.

## Audited controls

From the repository, submit an idempotent request with a unique ID:

```sh
docker compose exec core trading-platform control pause --id maintenance-001 --url http://localhost:9010 --token-file /run/secrets/operator_token
```

Replace `pause` with `resume` or `flatten` as appropriate. A 202 response acknowledges a request, not broker execution. Inspect `controls` in the authenticated status API for COMPLETE, WAITING or REJECTED. Reuse the same ID only for the same action. Reader tokens cannot mutate state.

Pause immediately blocks new entries and leaves existing protection intact. Resume requires fresh coverage, current risk limits, no uncertainty or instance halt. Flatten cancels owned pending orders, closes owned positions on fresh executable quotes, and latches an account halt after confirmed zero exposure. Stale data/disconnection keeps flatten pending; no success is invented. An operational halt requires review/recovery and cannot be bypassed with resume. Alerts are local durable transition records; no email or chat messages are sent.

## Host and upgrade requirements

Use a dedicated always-on Linux host with encrypted disk, restricted operator access, accurate UTC time and off-host backups. Docker Desktop stops providing reliable availability during host sleep. Internal networks isolate workers from simulator/gateway; only the read-only gateway has egress. Never mount the Docker socket. Core is the sole SQLite writer; do not scale it, and never run old and new executors against the same account. Cross-host failover is unsupported.

Images have pinned bases and hashed package locks. Runtime images exclude test dependencies; gateway code/dependencies use a separate target. Generate an override with `python3 scripts/release_manifest.py --image REGISTRY/IMAGE@sha256:DIGEST --output release.json` after pushing and verifying an immutable image. Launch with `docker compose -f compose.yaml -f release.json up -d --no-build`. A mutable local tag is for development, not a released artifact.

Before upgrading: pause entries, drain/cancel pending exposure, reconcile, record image/config/package hashes, perform a consistent backup, stop the old core, and start one replacement. Retain old strategy code until its positions are drained. A future schema migration needs an explicit compatible rollback plan; refuse a database newer than the supported schema. Stop services gracefully; shutdown flushes core state and preserves broker-held paper protection, but does not imply flattening.

Runtime containers use UID10001, read-only root, dropped capabilities, tmpfs, resource/PID limits and bounded logs. Only the no-network volume initializer has limited filesystem privileges. Private token rotation requires its own writable path; credentials must not be baked into build context or image layers. The CI matrix builds/tests AMD64 and ARM64 on native runners; inspect actual results before claiming support. Local verification alone is not a clean remote Linux-host deployment qualification.
