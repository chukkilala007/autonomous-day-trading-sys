# NAS100 open-session retry — 2026-10-25

Probe039 authenticated and collected at23:01:10UTC. Returned schedule evaluates SCHEDULED_OPEN;61M1 bars observed. This supersedes the earlier closed-session observation for this later interval only.

Unbuffered stream039 observed153updates over60seconds;139 were rejected as future-dated, with source lead1.642–45.162ms. No callback errors or writes. Final causal quote validity was false. This measures source lead at receipt, not a verified NTP offset.

A separate60second read-only run040 used the existing SpotBuffer, unchanged limits100ms lead/250ms residence/64pending. Observed161updates,146buffered and146released, peak pending1, final pending0, zero rejections/callback errors. Final quote was0.012398seconds old and causal-valid. Timestamps were not rewritten; strict stream validation ran after causal release. Request audit confirms authentication, subscription and margin only. No order transport or authorization used.

Evidence: [unbuffered039](nas100-open-session-039.json), [buffered040](nas100-buffered-040.json). Private source hashes retained; no credentials/account payload published. Probe040 does not exist:040 identifies the second stream observation. Next fresh probe/stream041 avoids collisions.

## Remaining gates

The closed-session obstacle is cleared for the observed interval. J05 account operation applicability, J06 executable bundle/assumptions/pins and J09 authorization are unchanged. J07 still needs the selected-symbol ten-minute/reconnect qualification and a proposal-bound connected preview with the final approved bundle. A60second collector observation is not that acceptance.

The attended preview/launcher currently instantiate strict Stream directly; this buffered collector result does not imply the attended path has buffering enabled. Any proposal to integrate the opt-in buffer there must preserve pending-queue inhibition, shutdown/disconnect reset and send-time freshness, and be implemented/tested before claiming the same behavior. J08 remains DONE for its tested strict-stream implementation; buffered attended integration is not delivered. No automatic relaxation or real order was made.
