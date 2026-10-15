# cTrader provider evidence

Implementation references checked 2026-10-15:

- [Authentication and refresh](https://help.ctrader.com/open-api/account-authentication/): application authentication precedes account enumeration and account authentication; token refresh may use protobuf. Use an explicitly selected demo account.
- [Connections](https://help.ctrader.com/open-api/connection/) and [endpoints](https://help.ctrader.com/open-api/proxies-endpoints/): pinned SDK uses TCP; this adapter explicitly configures Twisted hostname-verifying TLS for the demo endpoint, bounded reconnect backoff and SDK heartbeats.
- [Protocol model](https://help.ctrader.com/open-api/model-messages/) and [symbol data](https://help.ctrader.com/open-api/symbol-data/): relative prices divide by 100000; volume uses hundredths of a unit; trendbar timestamps identify opening minutes. Normalization fixtures test these conventions independently of symbol digits.

No actual Open API authentication, account-specific metadata or demo order has yet been observed by this project. Application credentials, refresh-token state and a selected demo account are required. Existing desktop/MCP access is not a credential for a headless Docker gateway.

Actual provider flow is a separate acceptance gate. Never promote a synthetic fixture or SDK schema inspection to account-specific capability evidence. Mandatory fields absent from the protocol require a broker-specific verified extension; unsupported capabilities remain disabled.
