# Attended offline Docker soak

This drill uses installed runtime components and synthetic broker fixtures. It opens no broker connection and mounts no credentials. It alternates unfilled cancellation/review and partial-fill/nonzero-cost settlement, using one retained SQLite database and the guarded completed-cycle transition. Every cycle retains its archive and consumed approval/test IDs.

Build and run from the repository root:

```sh
docker build --target gateway-check -t trading-gateway-check:attended-soak .
docker run --rm --network none --read-only --tmpfs /tmp trading-gateway-check:attended-soak python scripts/attended_soak.py
```

The predeclared limits are in `config/attended-soak-acceptance.json`: five minutes, one target cycle per second, at least 250 cycles, p95 cycle time at most one second, sampled process RSS at most 256 MiB and post-warmup RSS range at most 32 MiB. The first 20 cycles are warmup for the memory-range check. Any lifecycle, write-count, archival or database-integrity assertion aborts the run. Exit zero additionally requires all measured limits to pass.

The final JSON reports duration, cycles, synthetic writes, retained archives, checkpoint count, database size, cycle latency and sampled memory. Database growth is expected because audit archives and consumption tombstones are retained; it is reported rather than treated as a leak. The temporary test database is deleted when the drill exits. Never point this harness at the development demo ledger.

The synthetic clock is reset per independent approved lifecycle; the real wall clock governs the soak duration. Authentication, network latency, market-data freshness, actual fee conventions, container restart policy and host power loss are outside this drill. A five-minute pass does not establish multi-day stability or production capacity. This is a repeatable development regression harness using test fixtures, not a deployable trading launcher.

The gateway runtime itself can be rebuilt separately:

```sh
docker build --target gateway -t trading-gateway:attended-soak .
```

A new image fingerprint does not renew broker evidence or authorize orders. Review and bind fresh account/configuration/proposal/source/image inputs before the next market-open broker test.

## Two-hour profile

Use the longer predeclared profile and a new synthetic evidence directory:

```sh
docker run --name attended-long-soak --network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges -v "$PWD/var/offline-long-soak:/evidence" trading-gateway-check:long-soak-bounded python scripts/attended_soak.py --limits config/attended-long-soak-acceptance.json --state-dir /evidence/state
```

Prepare a writable, synthetic-only evidence mount for container UID10001 first. The state directory itself must not already exist. Never mount the broker demo ledger or credentials. Unlike the default temporary run, this option retains the synthetic database for investigation. It starts a new workload; it does not resume or add together partial runs to satisfy duration.

The long profile requires7200seconds and at least6000cycles. Other latency and memory limits are unchanged. Progress includes elapsed seconds, most recent cycle latency and database size. Only the final JSON plus successful container exit establishes completion. Interrupted runs remain diagnostic evidence.
