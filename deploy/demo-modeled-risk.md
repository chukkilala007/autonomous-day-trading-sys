# Demo modeled-risk policy

J01/F6.4k adds a separate DemoRiskPolicy; production Policy, Contract/ExactCosts and their complete-bound semantics are unchanged. Modeled preparation does not create a production Contract or label assumed slippage broker_verified.

Only the profile-bound demo USD/HEDGED protected BUY LIMIT first-test path is supported. Quantity is exactly the reviewed minimum. Explicit fee inputs, source hashes, a strictly positive adverse-exit price allowance, other cost allowance and assumptions-review hash are mandatory. There are no default real-account assumptions. Values require independent review before use.

Modeled loss = quantity × (entry − stop) × contract value + max(quantity × fee per unit, minimum fee) + fixed fee + quantity × adverse-exit price allowance × contract value + other cost allowance. Fee inputs cover reviewed round-trip incidences. Account and quote currencies must both be USD. Geometry already uses executable entry/exit prices; do not double-count spread in the fee allowance. Financing/adjustments and delayed cleanup must be addressed in the reviewed assumptions; an allowance is not a guaranteed ceiling.

The preview separates planned stop loss, reviewed fees, modeled allowance and modeled loss; realized_loss_bounded is false. It keeps the minimum of USD5 and0.1%equity as a modeled budget and10%equity margin reserve, exact broker margin, fresh quote/account evidence, capability/expiry and fencing requirements. The planned_loss compatibility field means modeled loss on this explicitly labelled path, never guaranteed realized loss.

Approval must explicitly select demo_modeled_risk and acknowledge accepts_unbounded_realized_loss. The independently pinned first-test Review must select the same semantics; send preparation rechecks the bound assumptions/policy hashes. Adapter rejects production DemoTransport for this policy. Existing one-attempt journaling, disabled defaults, owned cleanup and settlement confirmation remain. New Approval/Review fields change canonical hashes and require fresh independent pins.

Implementation/testing is not acceptance of any real allowance and not order authorization. J06 supplies reviewed account-specific values; J08 wires the attended launcher; J09 obtains concrete bounded authorization. All current tests are synthetic and use a fake transport.
