"""Deployment-pinned autonomous demo pilot boundary.

Strategies still decide whether and when to trade. This gate only constrains the
single pre-authorized pilot envelope and durably consumes it before transport.
"""
import json
from typing import Literal
from pydantic import Field, model_validator
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import Record, Name, Positive, Time, canonical, decimal, digest, utc
from .valuation import Hash


class PilotMandate(Record):
    classification: Literal['autonomous_strategy_demo_pilot'] = 'autonomous_strategy_demo_pilot'
    environment: Literal['demo'] = 'demo'
    authorized: Literal[True] = True
    account_id: Name
    account_alias: Name
    test_id: Name
    instance: Name
    package: Name
    config_hash: Hash
    instrument: Name
    quantity: Positive
    maximum_loss: Positive
    maximum_stop_distance: Positive
    minimum_reward_risk: Positive
    allowed_order_types: tuple[Literal['limit'], ...] = ('limit',)
    allowed_sides: tuple[Literal['buy','sell'], ...] = ('buy','sell')
    maximum_entries: Literal[1] = 1
    maximum_decision_age_seconds: int = Field(gt=0, le=5)
    maximum_proposal_lifetime_seconds: int = Field(gt=0, le=120)
    valid_from: Time
    submit_before: Time
    reviewed_bundle_hash: Hash
    source_hash: Hash
    image_digest: Hash

    @model_validator(mode='after')
    def bounded(self):
        if (self.valid_from>=self.submit_before or self.maximum_loss>5
                or len(set(self.allowed_order_types))!=len(self.allowed_order_types)
                or len(set(self.allowed_sides))!=len(self.allowed_sides)):
            raise ValueError('invalid autonomous pilot bounds')
        return self


class PilotGate:
    def __init__(self,db,mandate,*,approved_hash):
        self.db=db
        self.mandate=PilotMandate.model_validate_json(mandate.model_dump_json())
        if digest(self.mandate)!=approved_hash:
            raise ValueError('autonomous pilot mandate pin mismatch')
        self.approved_hash=approved_hash
        self.key='autonomous-pilot-entry:'+self.mandate.account_id

    def validate(self,command,now):
        m=self.mandate;now=utc(now)
        if not m.valid_from<=now<m.submit_before:
            raise ValueError('autonomous pilot window closed')
        if command.get('instance')!=m.instance or command.get('instrument')!=m.instrument:
            raise ValueError('foreign autonomous pilot command')
        body=command.get('body',{})
        if body.get('type')!='entry':
            raise ValueError('autonomous pilot entry required')
        decision=Decision.model_validate_json(json.dumps(body.get('decision')))
        if (decision.id!=command.get('id') or decision.outcome!='ENTRY'
                or decision.environment!='demo' or decision.account!=m.account_alias
                or decision.instance!=m.instance or decision.package!=m.package
                or decision.config_hash!=m.config_hash):
            raise ValueError('unapproved autonomous strategy decision')
        if not 0<=(now-decision.at).total_seconds()<=m.maximum_decision_age_seconds:
            raise ValueError('stale autonomous strategy decision')
        proposal=decision.proposal
        if not isinstance(proposal,Entry) or (proposal.instrument!=m.instrument
                or proposal.order_type not in m.allowed_order_types
                or proposal.side not in m.allowed_sides or proposal.profile!='protected'
                or proposal.target is None or proposal.exit_at is not None):
            raise ValueError('unsupported autonomous pilot proposal')
        lifetime=(proposal.expires_at-decision.at).total_seconds()
        if not now<proposal.expires_at or not 0<lifetime<=m.maximum_proposal_lifetime_seconds:
            raise ValueError('autonomous pilot proposal lifetime')
        risk=abs(proposal.worst_fill-proposal.stop)
        reward=abs(proposal.target-proposal.worst_fill)
        if risk<=0 or risk>m.maximum_stop_distance or reward/risk<m.minimum_reward_risk:
            raise ValueError('autonomous pilot geometry outside mandate')
        size=body.get('size',{})
        if decimal(size.get('quantity'))!=m.quantity or decimal(size.get('risk'))>m.maximum_loss:
            raise ValueError('autonomous pilot size outside mandate')
        if self.db.connection.execute('SELECT 1 FROM checkpoints WHERE id=?',(self.key,)).fetchone():
            raise ValueError('autonomous pilot entry already consumed')
        return decision

    def consume(self,command,now):
        decision=self.validate(command,now)
        record=dict(test_id=self.mandate.test_id,command_id=command['id'],decision_hash=digest(decision),
                    mandate_hash=self.approved_hash,consumed_at=utc(now))
        with self.db.transaction() as c:
            if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(self.key,)).fetchone():
                raise ValueError('autonomous pilot entry already consumed')
            c.execute('INSERT INTO checkpoints VALUES (?,?)',(self.key,canonical(record)))
        return record
