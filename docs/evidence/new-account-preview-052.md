# New-account configured preview — 2026-11-20

J06 configuration assembled and separately checked for read-only preparation; J07 proposal-bound preview passed. This is not order authorization or broker acceptance. Public manifest: [preview052](new-account-preview-052.json).

## Configuration and validation

Demo login10655835/API49644649, USD/HEDGED, NAS100/native#USNDAQ100/1107. Probe050 supplies fresh identity and volume geometry. Quantity0.01; minimum/step0.01, maximum500. Tick0.01 and USD1 per-unit point value are explicitly configured assumptions informed by historical capture005; no old account evidence is promoted to new-account verification. Trial operations remain unknown, with DEMO_TRIAL_NOT_AUTHORIZED preparation status.

Fixed round-trip fee estimate USD0.25, adverse-exit allowance50points and other-cost allowance USD0.50 remain provisional modeled inputs. Deferred settlement does not claim complete cost accounting. Configuration expires at the timestamp in the manifest (no later than24hours after probe050). A separate review checked identity, numeric settings, assumption text, empty capability-evidence list, profile hash and local/installed source-tree equality before writing read-only pins. These pins are not J09 approval.

Rebuilt trading-gateway:new-account; pinned image and source hashes in manifest. Seventeen targeted configured-demo/discovery tests passed in Docker in2.03s, one SDK deprecation warning; source mounted read-only, no network. Configuration was parsed with the installed rebuilt runtime. Initial assembly rejected Python lists where strict tuples were required; corrected private assembler and schema validation passed before any connection. No runtime source changed. Prior full600tests+4subtests remains historical baseline.

## Connected observation

Private one-shot runner uses installed ReadOnlySession/Binding and optional100ms buffer, with45second collection bound and5second shutdown bound. It creates one synthetic lifecycle-test proposal after a fresh causal quote, persists it before preview, and never changes its expiry. No execution transport or approval issuer is present. New account has its own retained ledger var/sandbox-state/attended-49644649.sqlite; no existing ledger was deleted or bypassed. Runtime checks verified no prior commands and broker-flat reconciliation.

At19:25:11UTC preview returned PREPARED_NOT_AUTHORIZED with no blockers: BUY LIMIT0.01, entry25349.50, stop25249.50, target25449.50, original expiry19:26:09.197984UTC. Modeled stop loss USD1, fees USD0.25, modeled additional allowances USD1: total USD2.25 within USD5 budget. Required margin USD12.68; reserve check passed. Read-only request allowlist and zero rejected writes checked. Buffer had no pending quotes; holding was not exercised by this run. No new-account ten-minute reconnect acceptance claimed.

The saved preview expired at19:25:11.686808UTC and is historical evidence only. Never use it as a current send permit or roll the original proposal expiry forward. Exact fresh proposal, approval and send-time checks remain required. J09 explicit approval and J10 actual lifecycle are outstanding. User-facing review should disclose unverified broker settings, unbounded realized loss and deferred settlement; do not label USD2.25 a guaranteed loss cap.
