"""Separate first-test qualification, never a production CapabilityReport.

Only the attended adapter's consumed approval and a fresh internally collected
preview can reach the inherited durable transport. No launcher enables this.
"""
import json
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from trading_platform.contracts.values import Record, Name, Time, digest, utc
from trading_platform.contracts.orders import Entry
from trading_platform.execution.planner import check_entry
from .valuation import Hash
from .orders import DemoTransport, limit_fields
from .execution_review import protocol_profile
from .sessions import scheduled_state


class Review(Record):
    mode: Literal['attended_first_test'] = 'attended_first_test'
    account_id: Name
    symbol: Name = 'EURUSD'
    review_bundle_hash: Hash
    protocol_hash: Hash
    observed_at: Time
    valid_until: Time
    # These are outputs to collect, not facts promoted by this review.
    acceptance_observed: Literal[False] = False
    risk_semantics: Literal['verified_bound','demo_modeled_risk'] = 'verified_bound'


class FirstTestTransport(DemoTransport):
    def __init__(self,binding,review,*,approved_review_hash,approved_approval_hash,authorized=False):
        super().__init__(binding.db,binding.session,authorized=authorized)
        review=Review.model_validate_json(review.model_dump_json())
        if digest(review)!=approved_review_hash or review.review_bundle_hash!=binding.pin or review.account_id!=str(self.session.account_id):
            raise ValueError('first-test review binding mismatch')
        from .attended_binding import ReviewedBundle
        if review.symbol!=ReviewedBundle.model_validate_json(binding._bundle_json).policy.instrument:
            raise ValueError('review symbol differs from bound contract')
        if not review.observed_at<review.valid_until:raise ValueError('invalid review window')
        self.binding=binding;self.review_hash=approved_review_hash;self.approval_hash=approved_approval_hash

    def prepare(self,command,core_id,epoch,report,quote,now,account_observed_at):
        if not isinstance(report,Review) or digest(report)!=self.review_hash:
            raise ValueError('explicit first-test review required')
        if not self.authorized:raise ValueError('first-test transport disabled')
        if (core_id,epoch)!=(self.binding.core_id,self.binding.epoch):raise ValueError('foreign first-test fence')
        self.fence.check(core_id,epoch)
        state=self.binding._state()
        if not report.observed_at<=now<report.valid_until:raise ValueError('first-test review expired')
        protocol=protocol_profile()
        if not protocol['sdk_mapping_matches_transport'] or digest(protocol)!=report.protocol_hash:
            raise ValueError('protocol profile changed')
        if self.binding._preview_lease is None:raise ValueError('no internally collected preview')
        lease=json.loads(self.binding._preview_lease);preview=lease['preview']
        if (lease['state']!=list(state) or lease['bundle_hash']!=report.review_bundle_hash
                or not utc(preview['created_at'])<=now<utc(preview['valid_until'])
                or preview['status']!='PREPARED_NOT_AUTHORIZED' or preview['blockers']):
            raise ValueError('stale or blocked bound preview')
        from .attended_binding import ReviewedBundle
        bundle=ReviewedBundle.model_validate_json(self.binding._bundle_json)
        if digest(bundle)!=self.binding.pin: raise ValueError('reviewed bundle changed')
        from .modeled_risk import DemoRiskPolicy
        modeled=isinstance(bundle.policy,DemoRiskPolicy)
        expected='demo_modeled_risk' if modeled else 'verified_bound'
        if report.risk_semantics!=expected or preview.get('risk_semantics','verified_bound')!=expected:
            raise ValueError('risk semantics mismatch')
        if modeled and (preview.get('realized_loss_bounded') is not False or preview.get('risk_policy_hash')!=digest(bundle.policy)
                or preview.get('assumptions_review_hash')!=bundle.policy.assumptions_review_hash):
            raise ValueError('modeled assumptions mismatch')
        quantity=bundle.quantity
        entry=Entry.model_validate_json(json.dumps(command['body']['decision']['proposal']))
        if (entry.instrument!=report.symbol or command['body']['decision']['environment']!='demo' or digest(entry)!=lease['proposal_hash']
                or Decimal(command['body']['size']['quantity'])!=quantity
                or Decimal(preview['quantity'])!=quantity or Decimal(preview['planned_loss'])>5):
            raise ValueError('first-test proposal/size mismatch')
        if utc(preview['account_observed_at'])!=account_observed_at or not 0<=(now-account_observed_at).total_seconds()<=2:
            raise ValueError('first-test account timestamp mismatch')
        # Metadata schedules are pre-trade support only, not actual acceptance.
        if any(scheduled_state(lease['metadata'],now+timedelta(seconds=i))!='SCHEDULED_OPEN' for i in range(121)):
            raise ValueError('unknown or closed test/cleanup session window')
        current=self.binding._quote(now)
        if quote.bid!=current.bid or quote.ask!=current.ask or quote.source_time!=current.observed_at:
            raise ValueError('first-test quote changed')
        check_entry(entry,quote,now)
        policy=bundle.policy
        for price in (entry.entry,entry.stop,entry.target):
            if price is None or price%policy.tick:raise ValueError('first-test price grid')
        if not policy.minimum<=quantity<=policy.maximum or (quantity-policy.minimum)%policy.step:
            raise ValueError('first-test volume grid')
        fields=limit_fields(self.session.account_id,policy.symbol_id,entry,quantity)
        fields['clientOrderId']=command['id'][:50]
        return fields

    def send(self,command,core_id,epoch,report,quote,now,account_observed_at):
        row=self.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('attended-attempt:'+str(self.session.account_id),)).fetchone()
        if not row:raise ValueError('consumed bounded approval required')
        attempt=json.loads(row['body'])
        if (attempt['approval_hash']!=self.approval_hash or attempt['command_id']!=command['id']
                or attempt['owner']!=command['instance']):
            raise ValueError('foreign consumed approval')
        return super().send(command,core_id,epoch,report,quote,now,account_observed_at)
