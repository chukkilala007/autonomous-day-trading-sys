# Attended demo launcher — J08

`python -m trading_platform.gateways.ctrader.attended_launcher` composes the existing first-test transport, binding, execution ledger, adapter, provider and monitor. It is a one-shot command for this Mac's Docker deployment. It does not run strategies, issue approvals, choose risk values or authorize an account. J06/J07/J09 still gate actual use.

Default execution is disabled: it writes a private report without reading review files, credentials or database. All arguments are paths/pins, not secret values. Required arguments:

```
--bundle PATH --proposal PATH --review PATH --approval PATH --cost-policy PATH
--account-id ID
--approved-bundle-hash HASH --approved-review-hash HASH
--approved-approval-hash HASH --approved-cost-policy-hash HASH
--credentials PATH --tokens PATH --database PATH --output NEW_PATH
```

Only a separately authorized run adds `--execute`. Review files must be exact ReviewedBundle, Entry, first_test.Review, attended_adapter.Approval and settlement.CostPolicy objects. Independent pins must be supplied through reviewed deployment configuration, not calculated from arbitrary input at launch. The portable broker profile is mandatory. Modeled risk requires matching semantics and acknowledgement across policy/review/approval. Settlement policy is independently pinned: it describes observed cash accounting, not a guaranteed loss bound, and cannot be inferred from modeled allowances. J04 still blocks supplying a real settlement policy.

## Docker deployment

Build the `gateway` target from the reviewed source, then pin the resulting image ID/digest in deployment. The offline suite uses `gateway-check`; that test image is not the production release. Existing Dockerfile installs the launcher module in both targets. `python -m trading_platform.gateways.ctrader.attended_launcher --help` is a harmless installation check.

Run with no published ports, non-root UID10001, read-only root filesystem, `/tmp` tmpfs, `--cap-drop ALL` and `--security-opt no-new-privileges`. Mount reviewed inputs and application credentials read-only; mount a separate private state directory writable for token rotation, database and reports. Ensure UID10001 can write it. Broker egress is needed only for a separately approved active/recovery run. Do not include credentials in the image, command line or logs. Run offline acceptance with `--network none`.

Preserve the same account database across all invocations. Do not delete or replace it to obtain a new attempt. Use one process and one authoritative state directory per account; the database writer lock and fence cannot detect a second independent copy of the database. Keep other account-trading processes stopped for the bounded test.

## Behavior and recovery

Before reading credentials, an active run validates all four independent pins, scope, proposal, risk semantics, protocol mapping and validity. The original proposal expiry is retained. Authentication, subscription repair and a causal fresh quote precede submission; the adapter repeats trusted preview and send-time checks. At most one durable account attempt is allowed.

After an uncertain send, the launcher monitors the consumed attempt instead of resending. The existing monitor requests owned pending cancellation after20seconds/partial fill, immediate close for unprotected owned exposure and close after120seconds. These are request deadlines, not guaranteed closure. Complete settlement and reconciliation are required for COMPLETE. An unfilled terminal order remains cost-unqualified.

An attended invocation is bounded to180seconds including startup. Timeout, interruption, client-stop failure or unresolved reconciliation never reports flatness. Shutdown disables write paths, retires callbacks and preserves the durable journal. The180second timeout does not flatten exposure and can expire during an outage. Operator takeover/recovery remains required when unresolved; a process kill or Mac sleep can prevent cleanup. Keep the Mac awake and the broker UI available during authorized testing.

For an existing consumed attempt, use the exact original reviewed files/pins and state with `--execute --recover`. This mode never submits an entry, never renews its approval, and refuses a missing attempt. Expired entry/proposal reviews do not prevent owned recovery, but current demo identity, ownership and fencing still apply. Expired settlement evidence prevents claiming completed settlement. Recovery data is checked against the original broker/account profile on every economics collection.

The report is created exclusively at0600 and fsynced, rejects existing output paths and contains fixed diagnostics rather than exceptions. CLI output contains only status. `orders_enabled=false` describes the stopped final state; `activation_requested` records whether execution was requested. Check status and `exposure_resolved`, never infer no prior order from the final disabled flag.

## Qualification boundary

Offline fixtures validate wiring; they do not establish actual broker acceptance or cleanup. J07 still lacks J06's executable bundle. J09 cannot finalize prices/approval until that bundle and fresh preview exist. J10 remains blocked and no active invocation was made during implementation.

## Opt-in causal quote buffering

Both attended launchers now accept `--quote-buffer-ms 100`; default0 retains strict immediate processing. No other bound is accepted. This holds only source timestamps up to100ms ahead, with250ms residence and64pending limits, then runs the unchanged strict stream validator. Timestamps are never rewritten. The trusted binding routes only spot messages through the buffer; execution events continue through the existing ledger path. A pending queue inhibits previews and send-time quote checks, even if an older quote was valid. Disconnect resets queues and invalidates coverage; shutdown resets timers before database close.

The output includes buffer metrics when enabled. Select/review this flag with the final deployment configuration and regenerate source/image review pins after this code change. This is not order authorization, a clock correction or relaxed acceptance of future prices. Real broker ten-minute observations do not establish order acceptance.
