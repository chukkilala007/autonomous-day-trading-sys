# Broker/account profile foundation

F5.2r adds `gateways.ctrader.broker_profile` as an offline boundary. It is not yet consumed by the attended runtime or exporter; those migrations are F5.2s. Existing FxPro checks stay active.

`BrokerProfile` version1 contains an immutable `AccountIdentity`, explicit normalized `SymbolMapping` tuples, validity interval and operation-scoped `CapabilityEvidence`. Broker names may contain spaces and are compared exactly. Canonical instrument names are not proof that two contracts are interchangeable. Geometry is configured data, not automatically verified economics.

`verify(authenticated_identity=..., approved_hash=..., now=...)` checks a separately supplied canonical SHA256 pin, all identity components and profile validity. It reparses the model to reject unchecked constructed/copied state. Callers must obtain identity from an authenticated session and obtain the pin independently; passing the profile's own identity/hash does not authenticate or approve it. Session generation, freshness, account access rights and permissions remain responsibilities of the runtime integration.

`capability(instrument, operation, ...)` performs those checks before returning supported, unsupported or unknown. Only current broker_verified/demo_observed evidence can establish supported/unsupported. Missing, expired, future, protocol-only and synthetic evidence return unknown. Foreign identities/mappings, duplicate mappings/evidence and unknown instruments reject. There is no fallback to another broker or symbol. Classification records a review assertion; this module does not cryptographically authenticate its source. Never accept untrusted evidence without the independent review pin.

Tests contain explicit synthetic FxPro and Example Broker profiles with identical aliases/IDs but different contracts. No real broker profile or deployment approval is supplied. Demo/live is an identity discriminator, not permission to run live. No transport, credential loading or execution switch is added.

Next: F5.2s must derive identity from correlated authenticated broker data and replace existing guards with profile verification, preserving legacy capture provenance and explicit currency/order limitations. F5.2t isolates public evidence providers; F6.4j integrates capability resolution with exact requested operations. This foundation does not complete either stage.
