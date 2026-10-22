# Connected read-only attended preview

The one-shot module `trading_platform.gateways.ctrader.preview_launcher` assembles VerifiedClient, ReadOnlySession, Feed, Stream and Binding. It has no execution transport or enable flag. Use the gateway Docker image, a read-only root filesystem, dropped capabilities and private mounts:

```sh
python -m trading_platform.gateways.ctrader.preview_launcher \
  --bundle /review/reviewed-bundle.json \
  --proposal /review/proposal.json \
  --approved-bundle-hash "$APPROVED_REVIEW_PIN" \
  --account-id 48232468 \
  --credentials /secrets/credentials.json \
  --tokens /state/tokens.json \
  --database /state/attended-preview.sqlite \
  --output /state/preview-unique.json
```

Mount `/review` and `/secrets` read-only. Mount `/state` writable, owned by the container UID10001, in a private0700 directory; retain the authoritative rotated token file. Do not copy stale seed tokens over it or run concurrent token writers. Credential/token files must satisfy TokenStore private-file checks. The output path must not exist and is created exclusively with0600 permissions. Reports contain private proposal and account-derived risk information; stdout contains only a fixed status. No credential values or exception text are reported.

Preflight validates the review pin and proposal before credential access. There is no supplied real-account approved bundle. A missing bundle produces REVIEW_REQUIRED and no connection. Use the existing authoritative first-test ledger; prior intents/exposure deliberately block Binding. Do not create a clean database to hide unresolved activity. The single-writer database lock prevents concurrent use of that same ledger.

The complete authentication, subscription, causal quote wait and preview collection is limited to30seconds. Shutdown has an additional5second limit. The proposal is never refreshed: its original60second expiry and10second collection-age gate remain enforced, so slow startup can block a run even before the outer timeout. A new proposal is a new explicitly prepared input, not an automatic retry. No historical bars are requested: this is a manual bounded transport preview, not strategy analysis.

The launcher authenticates only a demo account, repairs its quote subscription and uses the same-generation trusted binding for current economics and margin. Disconnect/reconnect, invalidation or missing fresh prices fail closed. No future-quote buffering is enabled by this launcher. It retires callbacks, revokes session readiness, stops the client and releases the database lock before writing the final report. A shutdown failure cannot be reported as success.

Exit0 and PREPARED_NOT_AUTHORIZED indicate a read-only preview only. Exit2 indicates blocked/failed preparation. Even a successful saved preview becomes stale quickly and cannot be used as a send permit. The adapter must repeat send-time checks under separately approved bounded authorization. Actual reviewed policy facts and real-broker launcher acceptance remain outstanding; offline tests do not supply them.
