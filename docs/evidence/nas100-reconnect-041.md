# NAS100 read-only reconnect qualification041

Observed25October2026,23:15:16–23:25:16UTC/London; reviewed26October. Historical acceptance evidence, not a current quote or order authorization.

The600.229second run authenticated the selected demo account and checked native NAS100 mapping and an open broker schedule. It received1,558spot updates. The unchanged100ms causal buffer held and released1,324updates, peak queue1, final pending0. No quote rejections, callback errors or read failures. Final quote source age0.357797seconds, causal-valid. The sampler accepted522fresh samples and blocked37samples under the combined readiness/pending/freshness conditions; blocked samples were not silently accepted.

One deliberate TCP abort occurred halfway through. Authentication/subscription and read-history repair completed in generations1and3;263fresh samples followed reconnect. Recorded disconnect count2 includes lifecycle shutdown notification and must not be represented as two forced reconnect drills. Two paginated M1 reads returned75and80rows over their two-hour windows. Account reconciliation/deal-history collection ran57times and reported complete history. These observations do not certify candle basis, gap-free strategy lookbacks or strategy performance.

[Sanitized metrics](nas100-reconnect-041.json) preserve original report/runner hashes. Request allowlist contains authentication, catalog/metadata, subscription, M1 history and account/deal reads only. Zero order writes or rejected write attempts. The read-only runner imports no order transport. Private reports and credentials remain outside Git.

## Disposition

PASS for this bounded read-only availability/reconnect slice. J07's proposal-bound connected preview remains blocked by J06's independently reviewed executable bundle. J03–J05 broker facts, modeled assumptions/settlement policy and J09 authorization are unchanged. No stale quote from this report may be reused for submission. New timed work requires fresh inputs.

J08a separately integrated opt-in100ms buffering into the actual attended launchers and passed587tests+4subtests plus deployment smoke. The ten-minute runner exercises the shared stream/buffer/session stack; it does not claim a real attended preview, submission, cleanup or settlement test. Consolidated broker questions are prepared in deploy/broker-execution-evidence-request.md and remain unsent. Next private evidence number042.
