# One-shot broker-profiled demo contract capture

This cBot only reads metadata, prints one `CONTRACT_SPEC_JSON:` record, and stops. It has no trading calls, file writes or network clients. `AccessRights.None` alone is not a prohibition on trading; review the source. It refuses live accounts, backtests, a different broker/login/currency/expected symbol, and an invalid nonce. No account balances or credentials are exported.

Algo Account.Number is the broker login, not Open API ctidTraderAccountId. The importer binds it through the selected account's fresh traderLogin. Do not enter48232468 as the expected login unless the fresh probe actually reports that login.

## Build

SDK image used: `mcr.microsoft.com/dotnet/sdk:6.0@sha256:c8fdd06e430de9f4ddd066b475ea350d771f341b77dd5ff4c2fafa748e3f2ef2`. Package cTrader.Automate1.0.21 is locked in packages.lock.json. From this directory:

```
docker run --rm -v "$PWD:/work" -w /work mcr.microsoft.com/dotnet/sdk:6.0@sha256:c8fdd06e430de9f4ddd066b475ea350d771f341b77dd5ff4c2fafa748e3f2ef2 dotnet build -c Release -p:RestoreLockedMode=true -p:AlgoPublish=false
```

The SDK on Linux generated `bin/Release/net6.0/.algo`; copy that artifact to an explicitly named `ContractSpecExporter.algo` before importing. Build success confirms SDK compatibility, not actual account execution. The .NET6 target matches this cTrader SDK; it is used for compiling this utility, not the Docker trading service runtime.

## Legacy v1/v2 capture and review

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

## Version3 portable capture

Current source builds v3. Preserve v1/v2 artifacts and historical captures; the legacy steps above apply only to those artifacts. V3 has no hard-coded broker or symbol allowlist. Empty expected broker/symbol/account currency/quote currency refuse; demo, RealTime, exact login and nonce guards remain. The new scope hash must be64lowercase hex characters. No trading calls were added.

Create an independently reviewed `CaptureScope` JSON (see gateway broker_profile.py): version1, identity (broker, Open API account_id, environment=demo, currency, account_type), canonical instrument, native_symbol, symbol_id, quote_currency, observed_at and valid_until. It deliberately omits unknown tick/value geometry so discovery does not require the facts it is collecting. Pin its canonical digest independently of the proposal/capture producer.

Use a new probe from the current collector; it includes authenticated demo binding/generation. Old probes cannot be promoted into v3 by attaching a profile. Both challenge and review commands require `--scope PRIVATE_SCOPE --approved-scope-hash REVIEWED_PIN`; challenge also requires `--symbol EXACT_NATIVE_SYMBOL`. The challenge binds that scope, probe, broker login, symbol, broker and currencies. Review still requires a capture within5minutes and an unexpired challenge/scope.

Set the v3 UI parameters from the challenge: Expected broker login, Capture nonce, Expected symbol, Expected broker, Expected account currency, Expected quote currency and Capture scope hash. Run only the reviewed artifact on the selected demo account. Build success is not account execution evidence; installation/run of this new artifact has not occurred. V3 artifact SHA256: e9453c210d4a3c4af4f7bbdbb72c03807583fb5149b27dc75811b799026ae767.

V3 output review labels monetary_value_currency explicitly as the captured account currency. TickValue/TickSize remains a startup observation candidate, not a quote-to-account conversion or executable multiplier. Positive values, consistent tick/pip geometry and matching Open API volume/lot rules remain mandatory. Historical v1/v2 parsing retains original FxPro restrictions and cannot acquire v3 scope provenance.
