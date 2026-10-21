# One-shot demo EURUSD contract capture

This cBot only reads metadata, prints one `CONTRACT_SPEC_JSON:` record, and stops. It has no trading calls, file writes or network clients. `AccessRights.None` alone is not a prohibition on trading; review the source. It refuses live accounts, backtests, a different broker/login/currency/symbol, and an invalid nonce. No account balances or credentials are exported.

Algo Account.Number is the broker login, not Open API ctidTraderAccountId. The importer binds it through the selected account's fresh traderLogin. Do not enter48232468 as the expected login unless the fresh probe actually reports that login.

## Build

SDK image used: `mcr.microsoft.com/dotnet/sdk:6.0@sha256:c8fdd06e430de9f4ddd066b475ea350d771f341b77dd5ff4c2fafa748e3f2ef2`. Package cTrader.Automate1.0.21 is locked in packages.lock.json. From this directory:

```
docker run --rm -v "$PWD:/work" -w /work mcr.microsoft.com/dotnet/sdk:6.0@sha256:c8fdd06e430de9f4ddd066b475ea350d771f341b77dd5ff4c2fafa748e3f2ef2 dotnet build -c Release -p:RestoreLockedMode=true -p:AlgoPublish=false
```

The SDK on Linux generated `bin/Release/net6.0/.algo`; copy that artifact to an explicitly named `ContractSpecExporter.algo` before importing. Build success confirms SDK compatibility, not actual account execution. The .NET6 target matches this cTrader SDK; it is used for compiling this utility, not the Docker trading service runtime.

## Capture and review

1. Collect a new read-only probe for the selected demo account; preserve rotated tokens. Do not overwrite existing private outputs.
2. Run `python -m trading_platform.gateways.ctrader.algo_capture challenge --probe PRIVATE_PROBE --account 48232468 --output NEW_PRIVATE_CHALLENGE` in the gateway environment. The challenge lasts one hour and binds the exact probe hash.
3. Import the reviewed .algo locally into FxPro cTrader. Add a local EURUSD instance on the selected demo account. Use the challenge's broker_login and nonce as parameters. Do not enable cloud synchronization or any other bot.
4. Run once. Save only the JSON after `CONTRACT_SPEC_JSON:` to a private capture file. Never substitute values from a backtest or manually invent TickSize.
5. Within five minutes run `python -m trading_platform.gateways.ctrader.algo_capture review --probe PRIVATE_PROBE --account 48232468 --challenge PRIVATE_CHALLENGE --capture PRIVATE_CAPTURE --output NEW_PRIVATE_REVIEW`.

The importer checks identity, time, nonce, pip geometry and independently observed volume/lot values. It does not authenticate a local JSON file as broker-signed evidence and never promotes an executable capability. Keep actual capture provenance for review; price-grid applicability to entries/protections remains a separate question.

References: [TickSize](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickSize/), [account properties](https://help.ctrader.com/ctrader-algo/references/Account/IAccount/), [build tooling](https://help.ctrader.com/ctrader-algo/compiling/).
