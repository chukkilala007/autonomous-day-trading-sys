# TPR-2 end-to-end qualification runbook

This runbook qualifies analysis and proposal generation only. The shadow gateway exposes no order operation, TPR-2 rejects live mode, and the forward report never authorizes orders.

## Frozen evaluation

The immutable evaluation contract is `config/evaluation/tpr2-shadow-v1.json`. It was registered before the observation window and binds `tpr2@1`, its source digest, EURUSD and XAUUSD, minimum samples, maximum unavailable fraction, reconnect generation, zero-write requirement and the no-performance-claim boundary. Do not edit it after observations begin. A strategy or parameter change requires a new package, plan and untouched window.

Run EURUSD and XAUUSD as separate single-symbol shadow deployments and state databases. This preserves per-symbol candidate state and makes sample/recovery evidence attributable. Insufficient observations extend the same locked evaluation through the declared maximum date; they do not justify parameter changes.

## Fresh read-only preparation

1. Build and test the exact gateway/runtime images. Record their immutable image IDs with `scripts/local_demo_host.py`.
2. Collect a new read-only probe for the selected demo account and exact symbol. The probe must verify its mapping and bid candle basis. Never reuse expired capability evidence.
3. Generate a new private analysis directory with `scripts/prepare_shadow.py --probe PRIVATE_PROBE --account ACCOUNT --symbol EURUSD --instances tpr2 --destination PRIVATE_EURUSD_ANALYSIS`. Repeat for XAUUSD. The generator creates a distinct TPR-2 token, feed contract, instance and deployment.
4. Create distinct UID 10001 writable gateway and core state directories for each symbol. Keep credentials mounted only on the gateway. Do not copy tokens into commands or reports.

Before startup, resolve `compose.shadow.yaml` with the analysis profile and exact local image override. Confirm:

- only the gateway has egress and credentials;
- the TPR-2 worker has only the internal worker network and one token;
- the core has broker/worker networks but no credentials or order transport;
- TPR-2 history is exactly 400 M1, 80 M5, 24 M15 and 16 H1 bid bars;
- the core database is new and contains no command, reservation or position rows.

## Bounded acceptance run

Start one symbol at a time with a unique Compose project name. Require fresh full coverage before decisions. Force one gateway reconnect after warm-up and require authenticated/subscribed generation 3. Keep the run long enough to cross the plan's minimum decision sample; stop and preserve evidence if any order-write counter becomes nonzero, package/config changes, data gaps enter a candidate lifecycle, the account changes, or quote/session evidence becomes stale.

The gateway may export execution evidence only when reviewed tick grid, bid/ask basis and an actual `OPEN` session observation are all current. Missing, stale, closed or malformed facts are omitted. In that case TPR-2 may produce structural `WATCH` decisions but must not produce an execution-qualified `ENTRY`.

After a clean shutdown, copy each stopped core database before inspection. Generate the combined report:

```text
python3 scripts/tpr2_qualification.py \
  --plan config/evaluation/tpr2-shadow-v1.json \
  --run EURUSD=PRIVATE_EURUSD_DB_COPY \
  --run XAUUSD=PRIVATE_XAUUSD_DB_COPY \
  --gateway-report EURUSD=PRIVATE_EURUSD_GATEWAY_REPORT \
  --gateway-report XAUUSD=PRIVATE_XAUUSD_GATEWAY_REPORT \
  --output NEW_PRIVATE_REPORT.json
```

The output is `IN_PROGRESS` until the preregistered end date. Afterwards it can be `OPERATIONAL_SHADOW_PASS`, `INCONCLUSIVE_EXTEND`, `INCONCLUSIVE`, or `FAIL`. It never reports P&L, edge, live readiness or order authorization.

## Demo-order transition

Only an operational shadow pass plus a naturally produced still-fresh limit proposal permits preparation of a new disabled pilot preflight. Renew the account, broker bundle, image, source, configuration, quote, session, margin and clock evidence. Bind a single exact quantity and maximum USD 5 modeled loss. Review the generated mandate separately before enabling one demo submission. No mandate may be prepared from a synthetic trigger or an expired shadow decision.
