# Autonomous trading platform — strategy-independent design

Date: 14 October 2026. Status: revised design, not deployed. Platform contract: Strategy API v1. First strategy adapter: TPR-1. First execution profile: proposed TPR-AUTO-1.

Build a Docker Compose-deployed Python trading platform with generic analysis workers that load versioned strategy packages, a shared deterministic risk controller, and exactly one broker execution writer per account. A worker is assigned a strategy instance and its declared instrument universe; it is not permanently assigned to TPR-1 or a particular symbol. Multi-instrument strategies receive a coherent snapshot of their entire universe. Once enabled in its configured mode, it discovers, qualifies, sizes, submits, monitors and exits trades without asking for approval on each trade. Autonomy operates inside a fixed, versioned mandate. It does not include changing its own strategy or increasing its own risk limits.

## Strategy boundary

The platform knows market events, instrument capabilities, decisions, risk, orders and positions. It does not know pullbacks, M1 rejection candles, 2R targets or any other particular signal rule. A strategy package owns its inputs, triggers, evaluation logic, candidate states, entry/exit proposals, parameters and tests. See [Strategy API v1](strategy-contract.md) for the interface, manifests, lifecycle and acceptance criteria.

Strategy packages can be deterministic, model-based or hybrid. All emit the same validated decision envelope. Model outputs have no broker authority; an independent deterministic risk boundary remains mandatory. A prose skill is a strategy specification, not an executable plugin: it must be adapted, versioned and evaluated before activation.

## First adapter: what exists and what must change

The existing skill supplies deterministic M5 trend/pullback rules, completed M1 rejection triggers, causal M15/H1 target screening, an execution validator and balance-based sizing. Wrap `skills/scalping-skill/scripts/tpr.py` in the first strategy plugin after packaging and regression testing. Its `execution_check` combines generic metadata checks with TPR-specific target, context, spread and R:R rules: split these responsibilities rather than placing the entire function in the shared core. Keep `risk_proposal.py` behind a sizing-policy interface; its linear stop-based sizing does not cover every strategy or instrument. Pin source hashes and parameters in every run.

The skill currently describes analysis and manual proposals. Implement the autonomous execution contract separately; keep the existing alert monitor's policy and state separate. Its 30-minute cadence cannot reliably capture entries that expire after three M1 bars. The new runtime is event-driven and continuously connected during supported sessions.

The saved `reporting/scalping/implementation-2026-10-14/replay-context/replay.md` contains 15 forming candidates, five completed triggers and three geometry passes, all passes on XAUUSD. This is a small pattern-detection sample with no verified fills or profitability evidence. It is not a basis for promising returns or promoting the strategy to live operation.

The current skill's data contract records missing source quote time, tick grid, candle basis and actual session state in the MCP workflow. This is an identified contract limitation, not a fresh audit of live responses. The new adapter must prove each required field; switching transport alone does not solve missing metadata.

## Components and authority

| Component | Autonomous responsibility | Authority boundary |
|---|---|---|
| Market-data service | Subscribe to quotes, validate history, finalize bars, track session and feed health | Cannot trade |
| Strategy registry and scheduler | Validate packages, bind instances, provision declared inputs and dispatch subscribed events | Cannot trade or modify active package versions |
| Generic analysis worker × N | Load one strategy instance; evaluate its event stream with isolated state | Emits typed decisions and proposed actions only |
| Risk controller | Validate decision evidence and account policy; compute size, margin and exposure; atomically reserve risk | Can veto; cannot manufacture a setup |
| Execution service | Submit, reconcile, cancel and close owned trades according to policy | Sole holder of trading credentials and sole order writer |
| Supervisor | Detect stale data, crashes, missing protection and state mismatches; inhibit entries | Requests recovery through execution service; no second writer |
| Optional language-model analyst | Explain decisions, summarize sessions, propose offline research | No credentials, no executable commands, no power to change runtime policy |

These are logical agents/services. Begin with a single-host Docker Compose deployment, isolated strategy worker containers, and one account executor. See [container deployment](container-deployment.md). Independent analysis means each strategy instance owns its evidence and state; all instances drawing on the same account share risk reservations. The scheduler can host several strategies on one instrument or a single strategy spanning several instruments.

For TPR-1, an LLM remains outside the decision path because that package requires deterministic gates. Other packages may use an LLM or learned model as their analysis engine, with pinned model/prompt versions, structured outputs, recorded inputs and responses, declared latency budgets, and independent evaluation. Timeouts, malformed output or unverifiable evidence yield no executable intent.

## TPR-1 example package — rules not imposed on other strategies

* EURUSD and XAUUSD only; trend pullback rejection only.
* Established M5 trend requires confirmed rising/falling highs and lows. A qualifying continuation impulse freezes the reclaimed level and invalidation.
* One active candidate per symbol; forming expiry is 30 minutes after impulse completion.
* A completed M1 rejection defines entry beyond the trigger extreme, stop beyond the whole pullback, and TP1 at the nearest eligible opposing structure.
* Preserve the exact symbol tolerances and research steps from TPR-1. They are not broker tick-size evidence.
* Require positive geometry and gross TP1 R:R of at least 2. Spread must be no more than 20% of stop distance and 20% of reward distance.
* Entry expires at the earlier of three subsequent M1 bars or the forming deadline. Never chase an entry already crossed before submission.
* Data gaps, incomplete context, unknown execution semantics and stale evidence block new entries. All reasons are retained.

Keep the skill's setup classifications inside its plugin and retain them as diagnostic detail. Map outcomes into the common decision contract. Add a separate broker-order lifecycle; a research `ENTRY_TOUCH_UNVERIFIED` or `MISSED` event must never overwrite a broker-confirmed fill.

## Data and broker integration

Preferred implementation: Python with cTrader Open API, durable local storage on an always-on host, automatic process restart and monitored connectivity. Official Python support and streaming/execution messages make this a reasonable fit for the existing Python strategy. This remains subject to an adapter feasibility test against the actual broker account.

cTrader documents nonhistorical and historical request limits of 50 and 5 requests per second per connection respectively. Use streaming plus a shared rate limiter and bounded history requests. Source: [Open API overview](https://help.ctrader.com/open-api/).

Subscribe to bid/ask events with source timestamps where supported; timestamps are optional in the protocol and missing values must block execution verification. A first subscription event can return a last quote even when the market is closed. Source: [Open API messages](https://help.ctrader.com/open-api/messages/).

Normalize the direct protocol in its own adapter: raw price fields and volume fields use documented scaling that differs from the existing MCP's already-decimal responses. Validate conversions with fixed fixtures and actual broker metadata. Source: [model messages](https://help.ctrader.com/open-api/model-messages/).

Adapter acceptance requires exact account/environment/symbol binding, contract valuation, volume limits and steps, executable price increments, bid/ask candle basis, holiday/session state, quote source timestamps, commissions, conversion rates, protection trigger sides and pending-order capabilities. Store original field evidence and observation times. Do not derive tick size from displayed digits or invent session status from a schedule. If Open API cannot substantiate a field, evaluate an instrumented broker-native cBot bridge; remain in shadow mode until the contract passes.

Data subscriptions, warm-up history and event cadence come from each package manifest; the data service shares compatible subscriptions across workers. For the TPR-1 package, warm up 200 M5, 300 M1, 100 M15 and 48 H1 bars and retain two-bar overlap for incremental fetches. Preserve gaps and revisions. An elapsed minute without ticks is not automatically a validated candle. Record finalized-bar arrival latency, source time and local receipt time separately. Reject out-of-order or incomplete evidence until repaired causally.

## Decision and execution sequence

1. Dispatch a subscribed bar-close, tick, timer or execution event with an immutable as-of snapshot. Data must satisfy the instance's declared coverage, freshness and causal availability requirements.
2. The strategy evaluates the event and emits a versioned decision plus next state: no action, watch, entry proposal, management proposal, or unavailable. Persist inputs, outputs and package identity atomically.
3. Validate the decision schema, provenance, ownership and deadline. The execution planner maps the proposed order semantics into broker capabilities without changing the strategy's intent. Unsupported behavior is rejected explicitly.
4. The shared risk controller applies the account mandate and allocated strategy budget, computes or verifies size through the configured risk model, and reserves exposure atomically. Strategy-specific constraints are checked through the package's versioned validator; they cannot override account limits.
5. The account arbiter resolves competing intents using a configured allocation policy. Default: fixed strategy priority, then decision time and stable intent ID. Do not rank different strategies by incomparable R:R or self-reported confidence.
6. Immediately before sending, the executor rechecks current prices, account state, deadline, kill switch and reservation. Persist the attempt before transmission; reconcile ambiguous results before any retry.
7. Apply broker events to authoritative order state and deliver owned execution events to the originating strategy instance. Confirm protection, recompute exposure and release reservations only on definitive evidence.
8. Manage positions using the bound exit-policy version and validated management proposals. Entry expiry and position exit are separate concepts. Record net outcome, costs, slippage and evidence per strategy instance.

Latency and quote-age budgets are manifest/profile settings bounded by the platform's maximum permitted staleness. TPR-AUTO-1 proposes a five-second close-to-decision objective, two-second order-send quote age, and the existing skill's 30-second outer source-age ceiling. Other strategies can subscribe to different events and use different approved budgets.

## Execution profiles

Order types, expiry, fill tolerance and exit behavior belong to named versioned profiles, selected by a strategy instance from capabilities supported by its broker and account mandate. The shared executor implements the mechanics; it has no hardcoded TP1, minimum R:R or three-bar expiry. Initial scope supports single-instrument directional orders with a verified protective stop. Multi-leg or stopless strategies require additional risk and execution capabilities and remain in research mode until those exist. Strategy independence does not mean silently pretending every strategy is supported.

## First execution profile example: TPR-AUTO-1

Prefer a broker-supported stop-limit entry with an explicit worst permitted fill, server-side expiry and attached protection. Compute maximum acceptable fill from the frozen structural stop, TP1, minimum 2R, cost limits and risk budget; size at that worst fill. If no legal price interval remains, reject. Configure and test exact broker stop/limit trigger behavior before use. Do not silently substitute a market order or ordinary stop order.

This execution choice changes fill probability relative to a simple OHLC entry-touch study and must be evaluated separately. A stop-limit can remain unfilled. Any triggered remainder must retain a server-enforced expiry or be confirmed cancelled; unsupported expiry semantics block this order policy.

Use full TP1 exits in the TPR-AUTO-1 profile. No discretionary trailing, breakeven, averaging down, martingale, pyramiding or widening of stops. These would be additional strategy variants.

If a fill is unprotected, immediately inhibit new entries, attempt the intended protection once through the executor, and close the owned exposure if protection cannot be confirmed. Retry/reconcile ambiguous responses without creating duplicate closes. During a complete disconnection the runtime cannot guarantee an emergency close; server-held protection and bounded pending expiry are therefore deployment requirements.

## Proposed risk mandate

These are proposed settings for the first account deployment, not hardcoded platform rules, changes to the existing monitor, or already approved live settings. Account policy dominates strategy allocation, which dominates a proposal. Each strategy has its own budget and allowed execution/risk profiles; adding a strategy cannot multiply the account budget. Strategies can request smaller allocations but cannot grant themselves larger ones.

| Control | Proposed value or behavior |
|---|---|
| Per-trade budget | Preserve 0.5% of freshly observed account balance, including estimated costs/slippage |
| Aggregate reserved and open risk | Maximum 1% of current balance; include pending orders and in-flight submissions |
| Symbol exposure | Initial account policy: at most one owned pending or open trade per symbol across all strategies |
| USD concentration | At most 0.5% for positions expressing the same USD direction; EURUSD and XAUUSD longs both consume this bucket |
| Daily loss circuit breaker | 2% of start-of-day equity, cash-flow adjusted, measured using realized and unrealized results plus costs |
| Daily behavior on trip | Cancel owned pending entries, close owned positions, halt entries until next Europe/London trading day and successful health checks |
| Loss streak | Three consecutive net losing trades pause new entries for 60 minutes; the daily breaker remains active |
| Margin | Broker estimate must pass; proposed free-margin reserve after submission is at least 50% of equity |
| Account | One explicitly bound dedicated account/environment; account mismatch halts trading |

The caps limit estimated exposure; gap losses and exceptional slippage can exceed them. Revalue exposure conservatively and include external positions in account-wide risk. If external exposure cannot be valued, block new entries. Never amend or close unrelated trades. Prefer a dedicated account to prevent netting with manual trades; require verified account position/netting behavior before activation.

Risk uses verified account-currency loss per unit plus round-trip commissions and a measured slippage allowance. Round volume down to the valid grid, reject below minimum, and verify margin separately. No USD-to-GBP conversion or fee may be silently assumed. Use this sizing model for the first stop-based profile. Other risk models require explicit capability support and an approved mandate version; the core does not require every strategy to size at 0.5%.

## Durable state and fault handling

Use SQLite WAL with transactional writes for a single host, append-only decision/order events, immutable snapshot files and encrypted backups. One durable writer per account; enforce a process lock and fencing so a restarted or standby executor cannot compete. No automatic active-active failover.

Persist: instruments/metadata evidence; completed bars and revisions; candidate events; intents; risk reservations; broker orders, deals and positions; policy versions; health events; equity checkpoints and daily circuit-breaker state. All records carry UTC timestamps, account/environment, strategy instance, package/config/model versions, execution/risk profile versions and evidence hashes. Render user times in Europe/London.

Order states: `CREATED → RISK_RESERVED → SUBMITTING → ACCEPTED → PART_FILLED/FILLED → CLOSED`, with branches for `REJECTED`, `CANCEL_PENDING`, `CANCELLED`, `EXPIRED`, and `UNKNOWN`. Unknown submission outcomes retain risk reservations and inhibit another submission for that candidate.

On startup/reconnect, first reconcile broker pending orders, positions and deals against local intents. Recover missed events and process fills that raced with cancellation. Never blindly resend a timed-out submission. If correlation is inconclusive, stay halted and alert. Partial fills retain protection and reserve risk for the remainder. Duplicate and out-of-order events are processed idempotently.

Feed stale or missing bars: inhibit entries and cancel owned pending orders when connectivity permits; retain protective exits on existing positions. Routine process restart: resume only after reconciliation and current data validation. Policy violation, unexplained position or repeated protection failure: latch a halt requiring investigation. Preserve daily/streak limits across restarts.

Use separate commands for `pause_entries`, `resume_after_checks`, and `flatten_owned_and_halt`. Inject credentials as service-scoped mounted secrets from the host secret store, never image layers, prompts or reports. Persist refreshed broker credentials in a separate restricted gateway volume when token rotation requires writes. Only the executor can access trade credentials. Notify on fills, meaningful state changes, protection failures and halts; routine no-setup evaluations stay quiet.

## Implementation and acceptance sequence

1. **Build the strategy contract and registry.** Implement typed inputs/decisions, manifests, isolated state, capability checks and conformance tests. Wrap TPR-1 without changing its baseline behavior. Add a deliberately different synthetic timer-driven strategy fixture to prove the platform has no dependency on M1, pullbacks, TP1 or 2R. The fixture tests architecture, not trading edge.
2. **Prove the adapter.** Capture real timestamped bid/ask data and verified contract metadata. Demonstrate price/volume units, currency valuation, bar basis, session handling, attached protection, expiry and reconciliation on demo.
3. **Build durable paper execution.** Same decision/risk pipeline with simulated fills from contemporaneous bid/ask data. Model costs, stop-limit nonfills, latency and conservative ambiguity; do not reconstruct historical spreads from current quotes.
4. **Fault-test demo execution.** Force disconnects before/after submission, timeout-after-acceptance, duplicated events, cancel/fill races, partial fills, crashes, token expiry, missing protection, account mismatch and simultaneous risk reservations. Require zero duplicate orders, zero unexplained exposure and successful restart reconciliation in the test suite.
5. **Evaluate each locked strategy and their combined portfolio.** Use an untouched chronological period, separate instruments and session buckets. Report net expectancy and uncertainty, drawdown, fill rate, slippage and tail losses. Pre-register sample sufficiency and acceptable drawdown before evaluating results. No live promotion from elapsed demo days or an arbitrary trade count alone.
6. **Deploy in a selected mode.** Explicitly bind demo/live account, risk mandate, execution policy and recovery behavior. Initial default is shadow. Promotion to live is a separate deployment decision; once activated, individual trades require no manual approval. Do not automatically tune or promote the strategy.

Proposed repository modules: `autotrader/contracts`, `registry`, `scheduler`, `workers`, `strategies/tpr1`, `market_data`, `broker`, `risk`, `execution`, `state`, `supervisor`, `reporting`, with separate `config/shadow`, `config/demo`, and `config/live` manifests. A status view should show current candidates, last completed bar/source quote, reasons for rejection, broker orders, protective levels, reserved risk, daily loss and operating mode.

The first implementation milestone is a generic continuously running shadow service that loads strategy packages by configuration, reproduces TPR-1 through an adapter, passes an unrelated strategy fixture without core changes, and proves the missing execution metadata. Autonomous demo trading follows when that contract passes. Live readiness remains contingent on execution reliability and credible performance evidence.
