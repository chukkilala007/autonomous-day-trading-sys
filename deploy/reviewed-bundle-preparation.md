# J06 reviewed-bundle preparation

Status: preparation packet available; executable bundle BLOCKED. [Packet](../docs/evidence/nas100-bundle-review-packet.json) is deliberately not a ReviewedBundle. It records historical candidate geometry and hashes the local review documents. Those SHA256 values detect document changes; they are neither independent approval pins nor hashes of downloaded broker pages. Unknown fields are null, not zero, empty approvals or invented hashes. Do not pass this packet to a broker launcher or rename it into a bundle.

## Assembly once evidence is available

1. Resolve [J03/J04](../docs/evidence/nas100-contract-cost-review.md) and [J05](../docs/evidence/nas100-operation-review.md). Read selected-account identity from private scope/correlated authenticated economics; do not derive identity from a public alias. Revalidate symbol mapping and geometry. Keep broker applicability in BrokerProfile, not shared execution code.
2. Record account/symbol-scoped CapabilityEvidence for all three required operations with source hashes, reviewed classification and finite validity intervals. Only account-applicable reviewed documentation or observed acceptance may support a claim. Actual acceptance need not precede the first test; general protocol support alone is insufficient.
3. Review USD-linear contract value, grid and fees. Supply round-trip fee incidences explicitly; zero public commission alone does not resolve fixed/minimum charges or delayed cleanup. Set a positive adverse-exit price allowance and a nonnegative other-cost allowance with a dated assumptions review explaining financing, adjustments and delayed close. These are modeled amounts, not guaranteed bounds. No amounts are chosen in the packet.
4. Construct DemoRiskPolicy with reviewed facts/assumptions and finite validity, then BrokerProfile with matching identity/geometry. Set explicit minimum quantity0.01 and profile USD_linear_absolute_protected_buy_limit_gtd. Independently review the canonical profile digest, then populate all ReviewedBundle review hashes. Never populate missing reviews with a hash of an empty document.
5. Build/test the exact final runtime and record its source and image identities. The existing modeled-risk image contains an earlier installed source revision; mounted-source test success does not qualify that image for deployment. Rebuild before pinning the final deployment. Recompute/independently review canonical bundle digest after every edit; a locally calculated digest alone is not approval.
6. Use the offline launch preflight, then J07's connected read-only launcher during a fresh open session. Create prices and the original60-second proposal near collection time; do not store placeholder market prices or roll expiry forward automatically. Check J08's final deployment inputs before the final preview.
7. J09 supplies a separate concrete order authorization, including modeled semantics and acknowledgement that realized loss is not bounded. FirstTest Review and Approval have separate pins. J06 never supplies authorization or enables the transport. J10 only follows fresh send-time validation.

## Remaining inputs and ownership

| Input | Owner / source | Used by |
|---|---|---|
| Account grid, protection and expiry applicability | Account-applicable broker documentation/response, operator supplied if necessary | J03/J05 review and profile evidence |
| Rounding, charge/event rules | Broker/account evidence | J04 fee and assumption review |
| Adverse-exit and other-cost model | Explicit risk review; operator acceptance at J09 | DemoRiskPolicy |
| Rebuilt tested runtime | Repository/Docker implementation work | Bundle source/image identities |
| Independent profile/bundle review | Deployment review separate from proposal producer | Trusted binding pins |

The prepared packet has no validity interval, approved bundle hash, order prices, credentials or authorization. Missing account evidence blocks publication of an executable bundle, but does not block J08's offline wiring. Settlement observations remain outputs of later authorized tests.
