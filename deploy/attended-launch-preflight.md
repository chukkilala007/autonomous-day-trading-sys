# Offline attended launch preflight

Run the input check inside the gateway image using:

```sh
python -m trading_platform.gateways.ctrader.launch_preflight \
  --bundle /private/reviewed-bundle.json \
  --proposal /private/proposal.json \
  --account-id 48232468 \
  --approved-bundle-hash "$APPROVED_REVIEW_PIN"
```

Mount inputs read-only and use `--network none`. The pin must come from separately reviewed deployment configuration. There is no real-account reviewed bundle in the repository; never substitute test fixtures. The bundle and proposal use ReviewedBundle and Entry schemas respectively. Proposal expiry is its original creation time plus60seconds; this check accepts only its first10seconds and never refreshes it.

Exit2 reports fixed blocker codes without echoing input files. Missing review reports REVIEW_REQUIRED. Exit0 means only INPUTS_VALIDATED_NOT_BROKER_READY: matching identity, review pin, policy dates, proposal geometry and reviewed grids. It proves neither broker connectivity nor current quotes, margin, exposure, fee accuracy, acceptance or authorization. No credentials are read, no ledger is changed and no broker connection is opened.

The bounded read-only session/stream/Binding composition root is now implemented; see `connected-readonly-preview.md` for timeout and private output handling. Actual attended submission additionally requires reviewed policy facts, fresh broker preview, concrete bounded human approval and enabled lifecycle wiring. This command cannot submit or enable orders.
