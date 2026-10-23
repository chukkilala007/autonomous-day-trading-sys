# Broker/account profile foundation

F5.2r adds `gateways.ctrader.broker_profile` as an offline boundary. F5.2s adds opt-in profile verification to the attended binding and v3 capture scope verification to the exporter/importer. Legacy paths retain their FxPro restrictions.

`BrokerProfile` version1 contains an immutable `AccountIdentity`, explicit normalized `SymbolMapping` tuples, validity interval and operation-scoped `CapabilityEvidence`. Broker names may contain spaces and are compared exactly. Canonical instrument names are not proof that two contracts are interchangeable. Geometry is configured data, not automatically verified economics.

`verify(authenticated_identity=..., approved_hash=..., now=...)` checks a separately supplied canonical SHA256 pin, all identity components and profile validity. It reparses the model to reject unchecked constructed/copied state. Callers must obtain identity from an authenticated session and obtain the pin independently; passing the profile's own identity/hash does not authenticate or approve it. Session generation, freshness, account access rights and permissions remain responsibilities of the runtime integration.

`capability(instrument, operation, ...)` performs those checks before returning supported, unsupported or unknown. Only current broker_verified/demo_observed evidence can establish supported/unsupported. Missing, expired, future, protocol-only and synthetic evidence return unknown. Foreign identities/mappings, duplicate mappings/evidence and unknown instruments reject. There is no fallback to another broker or symbol. Classification records a review assertion; this module does not cryptographically authenticate its source. Never accept untrusted evidence without the independent review pin.

Tests contain explicit synthetic FxPro and Example Broker profiles with identical aliases/IDs but different contracts. No real broker profile or deployment approval is supplied. Demo/live is an identity discriminator, not permission to run live. No transport, credential loading or execution switch is added.

Next: F5.2t isolates public evidence providers; F6.4j integrates operation capability resolution. F5.2s integration below preserves legacy provenance and explicit currency/order limitations.

## F5.2s integration

ReviewedBundle accepts broker_profile plus broker_profile_hash together. The outer independently pinned bundle binds both. Profile account/currency, symbol ID, quote currency and contract geometry must match Policy; demo HEDGED is required. New fields alter canonical bundle digests even for default-null legacy values: independently review/re-pin bundles and dependent approvals, never auto-migrate an old pin.

During preview, the trusted binding resolves native_symbol in the correlated broker catalog, obtains bracketed economics and verifies broker/account/type/currency against the current authenticated demo generation. Quote currency is checked via catalog quoteAssetId and correlated assets. Current access, limited-risk, USD-linear, zero-distance, flatness, fresh quote/margin and fencing guards remain. A profile is not an order capability approval. Profile expiry caps the preview lease; offline preflight also rejects stale profiles.

V3 capture uses a separately pinned CaptureScope without pre-known economics; see the exporter README for workflow. New probes carry demo binding/generation; legacy probes and captures remain historical and are not rewritten. BrokerProfile geometry still needs independently reviewed evidence before executable use. No source provider, fallback order semantics or production risk gate was changed. Real v3 capture and second-broker acceptance remain unperformed.
