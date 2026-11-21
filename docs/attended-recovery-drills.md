# Attended container and archive recovery

These drills are offline and use synthetic broker responses. They do not authorize broker orders, qualify arbitrary schema migrations, or establish host power-loss recovery.

## Container restart and compatible image replacement

Run from the repository root, with two distinct gateway-check images already built:

```sh
python3 scripts/attended_container_drill.py --baseline BASELINE_IMAGE --candidate CANDIDATE_IMAGE
```

The script creates isolated temporary storage, runs with no network and no credentials, kills the worker with SIGKILL, and restarts the same stopped container. Pending, uncertain cancel and uncertain close scenarios preserve the original attempt. The unresolved close then passes candidate replacement and rollback to baseline without resending. Containers are removed after each scenario. Docker --init ensures the worker is not PID1 and the injected signal is delivered normally.

The tested baseline is commit ac32b24 (schema1), before filled-cancel reconciliation. This proves compatibility for these specific ledger scenarios, not arbitrary downgrade safety or Docker's automatic restart policy.

## Attended-ledger backup and restore

Stop the attended writer before backup. The tool acquires the database writer lock and uses SQLite's backup API; copying a live database file is not supported. Run these commands inside the gateway image with only the intended state/archive paths mounted:

```sh
python -m trading_platform.persistence.attended_archive backup --database /state/ledger.sqlite --destination /archives/new-backup --account ACCOUNT_ID
python -m trading_platform.persistence.attended_archive verify --archive /archives/new-backup --account ACCOUNT_ID --approved-manifest-hash REVIEWED_HASH
python -m trading_platform.persistence.attended_archive restore --archive /archives/new-backup --destination /restores/new-restore --account ACCOUNT_ID --approved-manifest-hash REVIEWED_HASH
```

Backup returns a manifest and its hash. Retain/review the hash separately: a checksum stored only beside the archive does not establish trusted provenance. Account mismatch, checksum mismatch, extra files, symlinks, unsupported schema and incomplete artifacts reject. Destination must be new. Archives and restored databases are local private files; this tool does not provide encryption or off-host storage. Credentials and rotated tokens are excluded and must use the separate secret-recovery process.

Restore preserves the ledger, archived test history, consumed approvals and unresolved actions. It adds a durable restore marker and halt and advances the fence so stale controllers cannot write. The final ledger is published only after the inhibition is durable. Interrupted output retains INCOMPLETE and must not be activated.

The attended adapter and both entry transports reject new entries while either restore marker or halt exists. Freshly authenticated, ownership-checked recovery may reconcile/manage existing exposure; completion does not automatically clear the entry inhibition. No automatic re-arm command is supplied. Resume new entries only through a separately reviewed release/reconciliation procedure; never delete markers merely to make a test pass.

Do not run a restored ledger on older runtime images that predate the restore guard. The upgrade/rollback drill uses a non-restored ledger and does not qualify that downgrade. Schema migration, multi-day stability, real broker reconnect/settlement and encrypted off-host recovery remain separate acceptance gates.
