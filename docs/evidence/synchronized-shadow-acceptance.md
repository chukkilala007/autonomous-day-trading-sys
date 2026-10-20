# Post-correction sustained read-only acceptance

Date: 2026-10-20. Runtime baseline: implementation merge `74b6ed1`; subsequent commits changed documentation/evidence only. Execution remains disabled.

## Preconditions and scope

After the operator ran `sudo sntp -sS time.apple.com`, independent read-only measurements returned:

- Apple: +0.003500 ±0.008990 seconds.
- Cloudflare: +0.002256 ±0.016057 seconds.

These measurements show substantial improvement from approximately 132ms lag; their uncertainty does not establish exact broker-clock alignment.

Fresh probe-021 collected account, symbol and sampled margin evidence. EURUSD passed the three-sample bid-basis audit. XAUUSD did not: one reconstructed bid close differed from the broker bar close. Gold receives no fresh candle-basis qualification from this audit. See `synchronized-capability-audit-021.json`; no prior successful sample overrides this mismatch.

The initial attempt to expand the isolated configuration to both symbols failed strict model validation. A single-symbol run-016 had started and was promptly stopped; its private partial report is retained and is not acceptance evidence. Corrected JSON model validation then rejected a combined configuration because XAUUSD lacked current candle-basis evidence. No combined configuration was activated.

Run-017 therefore uses EURUSD only, both strategy workers, the unchanged 400/80/24/16 history requirements and two-second quote-age limit. Duration is 600 seconds, with a forced TCP disconnect at 240 seconds. The previously specified acceptance criteria remain: complete required histories, reconnect and post-repair fresh quotes, zero future-quote rejections, and no broker writes. Normal missing/stale data must suppress decisions.

A separate read-only SQLite sampler records quote validity/age and core counts every five seconds after its start. Its samples are not an every-tick record and do not replace the gateway's rejection counters. Ten minutes is bounded functional acceptance, not long-term operational soak.

## Results

Run-017 completed in approximately 602 seconds: 58 reconciliations, complete 400/80/24/16 history, forced reconnect PASS, 11 complete gateway polling snapshots, 83 core events and 166 decisions. Zero commands, reservations, positions or broker writes. One collection failure was recorded.

**Sustained acceptance FAIL:** 466 of 596 quote updates were future-dated. The gateway's generic PASS denotes bounded functional activity and reconnect, not sustained availability; the exported report explicitly records `sustained_acceptance: FAIL`. Final quote age was 6.677 seconds and its validity flag was false.

Host offset increased to +0.017764 +/-0.010011s during the run and +0.021748 +/-0.007747s afterward. Read-only administrator queries for automatic time settings failed because a password was required; no settings changed. All test containers/networks were removed.

Evidence: `synchronized-eurusd-shadow-017.json`, `synchronized-observations-017.json`. No runtime source changed in this acceptance round. Next diagnostic: measure rejected timestamps' lead over the container clock without changing validation.
