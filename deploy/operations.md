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

## Backup and isolated restore

Pause entries and stop core and simulator before a paired paper backup. The archive tool acquires both writer locks; it refuses an active writer. Mount the existing core/simulator volumes into a one-shot runtime container with networking disabled, plus a private backup directory, and invoke:

```sh
python -m trading_platform.persistence.archive backup --database /state/core.db --broker /broker-state/paper.json --destination /backup/NEW_ARCHIVE
python -m trading_platform.persistence.archive verify --archive /backup/NEW_ARCHIVE
python -m trading_platform.persistence.archive restore --archive /backup/NEW_ARCHIVE --destination /restore/NEW_DIRECTORY
```

Archives contain SQLite (including transactional evidence), simulator state and checksums, with restrictive file permissions. Existing archive/restore destinations are never overwritten. Incomplete artifacts are explicitly marked. Restore verifies checksums, database integrity and schema compatibility, and adds an entry halt plus pause. Restore first to a unique isolated paper project with no broker egress. Reconcile the copied broker events and ownership; preserve all prior risk halts. Do not clear a halt through direct SQL or treat restored state as authorization to trade.

This paired archive is for paper mode. Real-account restore must reconcile against current broker state, not restore an old simulated broker file. Application/refresh-token recovery is a separate encrypted secret backup managed by the operator; tokens are deliberately excluded from the paper archive. Copy archives and protected secrets to an approved encrypted off-host destination and perform a restore there before release. No off-host destination or token backup was configured during local implementation.

Schema 1 is the current supported version. A future schema is rejected. Roll back only to an image compatible with the saved schema; otherwise restore the pre-upgrade archive into isolation and reconcile. Never overwrite a newer operational DB with an older copy while an executor is connected.

## Declared local drill limits

`config/soak-acceptance.json` fixes the limits before measurement: 60 seconds, 5 synthetic events/second, at least 250 processed events, p95 processing below 500ms, maximum process RSS 256MiB, exactly two original entry commands and zero residual positions/reservations. This is a modest paper tick workload, not a production trading-load claim. `scripts/soak.py` reports the actual metrics and fails if any limit is missed.

`scripts/recovery_drill.py` starts with two owned commands and open risk, backs up quiesced state, restores to a new isolated directory and reconciles through protected exits. Acceptance: zero lost committed events, identical order IDs, no duplicate submissions, retained restore halt and recovery below 10 seconds. Run these scripts in the test/gateway-check image. Production soak duration, operational RPO/RTO and actual host outage tests must be agreed and measured on the intended host before release.

## Encrypted secret recovery tooling

The gateway/tools image includes `python -m trading_platform.persistence.secret_archive`.
Use `keygen --output /private/archive.key` once, store this 32-byte key separately in an approved offline key store, and keep it out of archives and Git. Back up explicitly named private files with `backup --key /private/archive.key --source credentials.json=/private/credentials.json --source tokens.json=/state/tokens.json --output /backup/NEW.sealed`. Stop token rotation while capturing the pair; per-file change detection is not a cross-file transaction. Files must be private regular files, not symlinks.

The format uses AES-256-GCM with a random nonce and authenticated version header. Verify recovery using `restore --key /recovery/archive.key --archive /backup/NEW.sealed --destination /restore/NEW_DIRECTORY` in a no-network container. Authentication completes before any plaintext destination is created. The destination must be new; files are 0600 in a 0700 directory. An incomplete restore retains an `INCOMPLETE` marker. Neither command activates credentials or contacts a broker. Test restored credentials only during a separately authorized provider qualification.

Only synthetic secrets were exercised locally. Copying ciphertext to an off-host destination, separately recovering the key, and qualifying an actual credential restore remain operator/deployment acceptance tasks; no remote destination is configured or assumed.

## Reproducible offline paper release bundle

After committing a clean checkout, run `python3 scripts/release_bundle.py build --image REGISTRY/IMAGE@sha256:DIGEST --destination /private/path/NEW_BUNDLE`. This packages an allowlisted set of committed Git blobs, the exact source commit, file checksums and immutable Compose override. Ignored/untracked local credentials are excluded. It intentionally includes **public synthetic paper fixture tokens**, so it is only a paper handoff, never a credential-bearing demo deployment. The image digest is an input; the bundle explicitly reports `registry_verified: false` and does not claim the image exists or is published.

Run `python3 scripts/release_bundle.py verify /private/path/NEW_BUNDLE` after transfer and before use. It rejects missing/modified/extra files, path traversal, symlinks, incomplete packaging and mode/override mismatches. Checksums detect corruption, not hostile replacement of the entire bundle; preserve the source commit and bundle manifest through a trusted channel. The source and commands are included for inspection; source files are materialized without executable bits, so invoke scripts through Python or `sh`. Actual registry verification and intended-host deployment remain separate acceptance checks.

## Sandbox credentials and read-only probe

Keep `Sandbox.rtf` private and untracked; it is excluded from both Git and the Docker build context. The supplied document currently contains access/refresh tokens only. A separate private JSON application file must contain `client_id` and `client_secret`. Do not use credentials from an unrelated MCP connection. Import with `python3 scripts/import_sandbox.py --document Sandbox.rtf --application /private/application.json --output /private/NEW_credentials.json`. RTF import uses macOS `textutil`; plaintext token documents can also be imported. The output is exclusive/0600 and forces refresh because copied relative expiry has no trustworthy issuance time.

In the gateway Docker image, invoke `python -m trading_platform.gateways.ctrader.probe --credentials /private/credentials.json --tokens /state/tokens.json --output /state/NEW_probe.json`. Bind private credential and writable state directories only to that one-shot gateway container. It uses verified demo TLS, authenticates the application, rotates tokens, discovers explicit `isLive: false` accounts and selects automatically only when exactly one demo account exists. With multiple demo accounts it writes their IDs privately and requires a subsequent `--account ID`. Optional `--symbols EURUSD XAUUSD` must match exact broker symbol names.

The private evidence report includes symbol metadata, a bounded 24-hour M1 history range and bracketed account economics. It explicitly does not mark full provider qualification complete. No mutating broker module or order request is used. A failure emits only a generic reason; raw authentication payloads are never placed in logs/reports. Preserve rotated tokens; never repeatedly import the older token document over rotated state.

## Bounded read-only demo qualification

Run `trading_platform.gateways.ctrader.probe` with `--audit` in the gateway image to collect exact-symbol metadata, fresh account economics and three completed M1 bid/ask tick comparisons. Use an exclusive private `--output` path and preserve the rotated `--tokens` file. The audit records unresolved capabilities; a collected report does not authorize execution. MAX margin aggregation is supported, but the actual empty-account result does not qualify nonempty margin or fee policies.

The read-only gateway service accepts `--run-seconds 90 --reconnect-after 35 --report /state/shadow-run-NNN.json`. These optional drill arguments force a TCP break on the gateway's own connection, allow SDK reauthentication/history repair and stop the process after the bounded interval. Use `restart: "no"` for this drill. Reports contain request-type counts and coverage/reconciliation evidence, never authentication payloads. Use a new report filename for each run; reports are exclusive private files.

Use `scripts/prepare_shadow.py --probe /path/to/private-collected-probe.json --account ACCOUNT --symbol SYMBOL --destination var/shadow-analysis` to create isolated analysis configuration and RPC tokens. Set `CTRADER_DEMO_ACCOUNT`, `SHADOW_SECRET_DIR`, `SHADOW_STATE_DIR`, `SHADOW_ANALYSIS_DIR` and `SHADOW_CORE_STATE_DIR`, then resolve `compose.shadow.yaml --profile analysis` with a unique project name. Keep the existing rotated token store mounted to only one gateway process. The generated `feed.json` derives warm-up requirements from the reviewed registry and binds exact account/symbol/basis evidence. Gateway rejects missing, expired or inconsistent configuration at startup and each poll. Regenerate older hand-written feed files; Compose now mounts `/analysis/feed.json`. For the current TPR shadow acceptance, requests include M1=400, M5=80, M15=24 and H1=16 bars; these are deployment requirements, not shared-core strategy defaults. Missing intervals and old quotes continue to block decisions.

Default container UID is 10001; private host-owned files on macOS may require an explicit host UID:GID override on the isolated test services. Do not loosen file modes or copy credentials into images. Keep worker/broker networks internal and only the gateway on the egress network. Inspect container logs, report counts, authenticated worker health and zero core command/reservation rows before stopping the uniquely named stack. A weekend run with subscription snapshots but no fresh prices proves blocking behavior, not live streaming or successful strategy evaluation.

For a bounded shared-runtime check with less history, `prepare_shadow.py --instances timer_fixture` activates only that reviewed fixture in the generated feed/core configuration. The default remains both instances. Compose may start an unused TPR worker; it receives no evaluations. A fixture ENTRY tests decision recording only and is never an order or strategy-performance claim. TPR qualification retains its own full history requirements. Partial spot messages preserve each side's own source time; the combined quote uses the oldest side, and both sides must be freshly observed after reconnect.

`probe --margin-audit` collects expected BUY/SELL margins at the symbol minimum and up to two further volume steps. The resulting report applies only to those quantities and its observation time. It neither qualifies an entire tier schedule nor supplies tick/multiplier/fee policy. Stale account economics or margin responses reject; host overload must be fixed rather than widening freshness limits.

## Selected local demo host

The operator selected this Mac with Docker Desktop as the demo host on 2026-10-19. A separate Linux host and registry are not prerequisites for this local demo. Container Linux and native CPU architecture still apply. Production/off-host recovery acceptance remains separate.

Build the current committed source using `docker build --target runtime -t autonomous-trading-paper:local .` and `docker build --target gateway -t autonomous-trading-gateway:local .`. Run `python3 scripts/local_demo_host.py --runtime-image autonomous-trading-paper:local --gateway-image autonomous-trading-gateway:local --destination var/NEW_host_check`. It checks Linux/native non-root images and minimum Docker resources, saves a sanitized report and pins all four shadow services to local content-addressed image IDs. It does not verify source provenance or broker readiness. Record the source commit and installed-image test results with the report. A failed check emits no image override.

Append the generated `images.json` after the shadow Compose file and any drill override, then launch with `--no-build --pull never`. This prevents Compose from substituting rebuilt or pulled tags. Keep the images locally; Docker image pruning can remove them. The override is host-local and is not a transferable registry release.

This Mac currently has idle sleep enabled on AC and battery. For an attended bounded drill on AC power, run its foreground command under `caffeinate -i COMMAND...`; the assertion ends when that command exits. Do not wrap a detached `up -d` command and assume the assertion lasts for the session. Use a separate foreground `caffeinate -i` for the entire attended session if running detached services; stop it after stopping the session. Closing the lid, explicit sleep, power loss and Docker Desktop shutdown still interrupt service. No global power settings are changed by the project. Reconnection must repair history and reconcile before decisions resume.

Demo order testing starts only after the pre-order gates in the implementation plan are satisfied and the operator explicitly authorizes bounded actual demo orders. This host check never changes the existing disabled-order mandate. Paper recovery evidence does not establish recovery of actual broker positions.

A bounded shadow report includes `latest_coverage`: one row per required history timeframe and one per quote symbol. `contiguous_available` stops at the first missing required interval; it is not the total number of cached bars. `first_missing_end` identifies that interval. `repaired` is independent of history count, and quote rows report source age against the existing two-second bound. These are the last completed poll's diagnostics, not a promise that data remains fresh after the run ends.

Clock readiness is a separate requirement. `sntp -t 3 time.apple.com` measures the Mac's offset without changing it. If the host lags broker timestamps, synchronize macOS Date & Time (or have an administrator run `sudo sntp -s time.apple.com` locally), then recheck both host and Docker guest time and run fresh shadow acceptance. Never provide administrator passwords to this agent. The quote validator rejects future timestamps; the new `spot_rejections` report records fixed reason codes without raw messages. Clock correction is not a reason to re-label past failed evidence or widen source-age limits.

Quote validity is durable and separate from historical repair. Rejection blocks the cached quote and clears both side observations; a newly valid two-sided quote restores only quote readiness. Real disconnect invalidates both gates. The last accepted quote remains stored to reject timestamp regression, and the normal two-second age check still applies.

## FxPro public specification reconciliation

Run `python -m trading_platform.gateways.ctrader.specifications --probe PRIVATE_PROBE --account ACCOUNT --output NEW_PRIVATE_REPORT` in the gateway image. This offline review binds the reviewed public EURUSD/GOLD facts to fresh selected-account metadata, preserves discrepancies, and interprets UTC session/holiday schedules. Output is not an executable capability policy. Gold's public increment currently conflicts with account metadata. SCHEDULED_OPEN does not certify current execution availability; no rounded website schedule overrides broker intervals. New public facts require an explicit reviewed source update and tests.
