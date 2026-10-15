# Demo qualification — NOT QUALIFIED

No actual demo order was placed for this implementation. Open API credentials, a selected demo account and explicit demo-test authorization have not been provided. S5 and S6 acceptance gates remain open. Offline code can be merged after its tests pass; it cannot be deployed as a qualified demo executor.

The deterministic suite covers stale fences, unknown sends/no retry, duplicated/old events, partial fills, pending cancellation races in the paper broker, process death, isolated worker failure, protection halts and disconnected recovery policy. These scenarios are simulated, not broker observations.

Run `python -m trading_platform.gateways.ctrader.qualification --account ACCOUNT --evidence PRIVATE_JSON --output NEW_REPORT_JSON` in the gateway image to classify captured qualification evidence. It exits 2 if qualification is incomplete, and creates the report exclusively so prior reports cannot silently change. Each scenario must record its account, timestamp, artifact hash, source, result, unexplained-exposure and duplicate-submission checks. Actual broker artifacts must be retained privately; this repository contains no user account data.

Before actual qualification: authenticate read-only, verify every mandatory field against the selected account, record the deployment mandate and narrow approved test envelope, and obtain explicit authorization for demo orders. Test only owned orders/positions. Record actual amounts, protective prices, deadlines, fees and broker events. The current demo mapper deliberately supports only verified limit orders with absolute stop/target and server expiry; unsupported strategies/order profiles fail instead of being substituted. Actual complete lifecycle and recovery qualification remains required even when unit tests pass.

S7 controls and recovery tooling can be developed and exercised against the paper stack while broker qualification is unavailable. Production/demo release remains gated; S8 live authorization is separate.
