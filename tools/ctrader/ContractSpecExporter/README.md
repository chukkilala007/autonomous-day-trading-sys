# One-shot demo EURUSD/NAS100 contract capture

This cBot only reads metadata, prints one `CONTRACT_SPEC_JSON:` record, and stops. It has no trading calls, file writes or network clients. `AccessRights.None` alone is not a prohibition on trading; review the source. It refuses live accounts, backtests, a different broker/login/currency/expected symbol, and an invalid nonce. No account balances or credentials are exported.

Algo Account.Number is the broker login, not Open API ctidTraderAccountId. The importer binds it through the selected account's fresh traderLogin. Do not enter48232468 as the expected login unless the fresh probe actually reports that login.

## Build

SDK image used: `mcr.microsoft.com/dotnet/sdk:6.0@sha256:c8fdd06e430de9f4ddd066b475ea350d771f341b77dd5ff4c2fafa748e3f2ef2`. Package cTrader.Automate1.0.21 is locked in packages.lock.json. From this directory:

```
docker run --rm -v "$PWD:/work" -w /work mcr.microsoft.com/dotnet/sdk:6.0@sha256:c8fdd06e430de9f4ddd066b475ea350d771f341b77dd5ff4c2fafa748e3f2ef2 dotnet build -c Release -p:RestoreLockedMode=true -p:AlgoPublish=false
```

The SDK on Linux generated `bin/Release/net6.0/.algo`; copy that artifact to an explicitly named `ContractSpecExporter.algo` before importing. Build success confirms SDK compatibility, not actual account execution. The .NET6 target matches this cTrader SDK; it is used for compiling this utility, not the Docker trading service runtime.

## Capture and review

1. Collect a new read-only probe for the selected demo account; preserve rotated tokens. Do not overwrite existing private outputs.
2. Run `python -m trading_platform.gateways.ctrader.algo_capture challenge --probe PRIVATE_PROBE --account 48232468 --output NEW_PRIVATE_CHALLENGE` in the gateway environment. Use `--symbol '#USNDAQ100'` for NAS100 (default EURUSD). The challenge lasts one hour and binds the exact probe hash and selected symbol.
3. Import the reviewed .algo locally into FxPro cTrader. Add a local instance for the exact challenge symbol on the selected demo account. Use the challenge's broker_login, nonce and symbol as the Expected broker login, Capture nonce and Expected symbol parameters. Do not enable cloud synchronization or any other bot.
4. Run once. Save only the JSON after `CONTRACT_SPEC_JSON:` to a private capture file. Never substitute values from a backtest or manually invent TickSize.
5. Within five minutes run `python -m trading_platform.gateways.ctrader.algo_capture review --probe PRIVATE_PROBE --account 48232468 --challenge PRIVATE_CHALLENGE --capture PRIVATE_CAPTURE --output NEW_PRIVATE_REVIEW`.

The importer checks identity, time, nonce, pip geometry and independently observed volume/lot values. It does not authenticate a local JSON file as broker-signed evidence and never promotes an executable capability. Keep actual capture provenance for review; price-grid applicability to entries/protections remains a separate question.

References: [TickSize](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickSize/), [account properties](https://help.ctrader.com/ctrader-algo/references/Account/IAccount/), [build tooling](https://help.ctrader.com/ctrader-algo/compiling/).

## Version2 monetary observations

Version2 emits quote currency, TickValue and PipValue in addition to TickSize and volume geometry. Only EURUSD and #USNDAQ100 on the selected FxPro USD demo account are allowed, and expected symbol defaults empty (fail closed). There are no trading calls. Retain the original v1 artifact/capture; build v2 to a new named artifact and review its digest before import.

The importer still accepts historical v1 EURUSD records. Version2 requires a symbol-bound challenge, USD quote currency and positive finite monetary values. Output includes TickValue/TickSize as `candidate_value_per_unit_per_price`, classified `startup_snapshot_pending_review`. It is not a verified contract multiplier. TickValue/PipValue are startup snapshots according to the [official TickValue documentation](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickValue/); capture provenance, units and applicability require review before policy use. No rounding tolerance or automatic monetary-value promotion is introduced.
