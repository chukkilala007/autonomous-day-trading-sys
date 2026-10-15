# cTrader provider evidence

Implementation references checked 2026-10-15:

- [Authentication and refresh](https://help.ctrader.com/open-api/account-authentication/): application authentication precedes account enumeration and account authentication; token refresh may use protobuf. Use an explicitly selected demo account.
- [Connections](https://help.ctrader.com/open-api/connection/) and [endpoints](https://help.ctrader.com/open-api/proxies-endpoints/): pinned SDK uses TCP; this adapter explicitly configures Twisted hostname-verifying TLS for the demo endpoint, bounded reconnect backoff and SDK heartbeats.
- [Protocol model](https://help.ctrader.com/open-api/model-messages/) and [symbol data](https://help.ctrader.com/open-api/symbol-data/): relative prices divide by 100000; volume uses hundredths of a unit; trendbar timestamps identify opening minutes. Normalization fixtures test these conventions independently of symbol digits.

No actual Open API authentication, account-specific metadata or demo order has yet been observed by this project. Application credentials, refresh-token state and a selected demo account are required. Existing desktop/MCP access is not a credential for a headless Docker gateway.

Actual provider flow is a separate acceptance gate. Never promote a synthetic fixture or SDK schema inspection to account-specific capability evidence. Mandatory fields absent from the protocol require a broker-specific verified extension; unsupported capabilities remain disabled.

## Read-only collector launch

`compose.shadow.yaml` is a separate project, never an override on a paper database. It starts the SDK read-only collector, not an enabled order gateway. Provision a UID10001-readable private credential JSON (mode 0600) with `client_id`, `client_secret`, `access_token`, `refresh_token`, and numeric Unix `expires_at`. Rotated credentials are written atomically to the private state directory. Do not paste tokens into terminal commands or commit them.

Provide `feed.json` with `symbols` mapping exact verified names to broker IDs, `requirements` rows `[symbol, verified_candle_basis, fixed_minutes, count]`, and `history_hours`. No symbol IDs or candle basis are inferred. Set local paths `SHADOW_SECRET_DIR`, `SHADOW_STATE_DIR` and the selected `CTRADER_DEMO_ACCOUNT`, then run `docker compose -p trading-shadow -f compose.shadow.yaml up --build -d`. The state directory must be owned by runtime UID10001. Only the gateway mounts credentials and has egress; nothing is published to the host.

The current collector records a bounded account history window; `hasMore` blocks complete-history acceptance. Deep pagination and real-time shadow worker orchestration remain explicit F5 integration work. `ShadowRuntime` provides the separately tested no-executor decision path; the collector does not silently treat paper decisions as actual broker events.
