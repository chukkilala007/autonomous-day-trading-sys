# Broker evidence providers

F5.2t isolates historical FxPro public comparisons in `gateways.ctrader.evidence_providers.fxpro`. The existing `python -m trading_platform.gateways.ctrader.specifications` command and imports delegate to that provider, preserving its output/hash behavior, reviewed date, symbol restrictions and unresolved conflicts. Its public constants are historical observations, not current scraped policy or defaults for other brokers.

`evidence_providers.reviewed` accepts broker-neutral `ReviewedDocument` objects through `reconcile(probe, document, approved_document_hash=..., now=...)`. This offline Python boundary performs no network access. The document contains:

- A CaptureScope identifying broker/account/environment/currency/type and canonical/native symbol/ID, with an explicit validity window.
- Source reference, content SHA256, review time and expiry.
- Explicit positive normalized minimum, maximum, step and/or lot observations. At least one is required; omitted values remain absent.

Review the document independently and supply its canonical digest from the deployment/reviewer trust boundary. The source hash records provenance but does not prove that a document is authentic, current or correctly interpreted. A profile pin computed by the same untrusted producer is not independent review. Public documentation scoped to a broker still needs an explicit account applicability assessment; the schema does not invent it.

The provider checks the document pin and freshness, correlated demo probe identity/generation, exact native mapping and unique metadata. It compares only supplied observations with normalized account values, returns all conflicts and caps validity at the earliest probe/document/scope expiry. It rejects cross-broker/account reuse. Broker data is never replaced by a public value. Neither agreement nor an empty conflict list qualifies execution.

The result is `document_comparison_only`, with orders disabled and qualification incomplete. It is not a CapabilityReport, ReviewedBundle or approval. Tick/value observations remain in the portable Algo capture path; fees/rounding, conversion and operation semantics need their own reviewed evidence. The existing probe, normalization, capture and attended binding do not import the FxPro provider. No automatic provider selection, fallback broker, live scrape or broker-specific commission default is introduced.

Tests use synthetic FxPro and another broker, including alias/ID collisions, wrong identity/environment, expired review, changed pin, duplicate metadata and contradictory documents. No second-broker credentials or acceptance are claimed. Next is F6.4j operation capability planning; actual broker qualification remains separate.
