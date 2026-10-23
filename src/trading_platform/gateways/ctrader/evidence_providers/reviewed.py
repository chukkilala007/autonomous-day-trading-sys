"""Broker-neutral, pinned document observations compared with account metadata.

No web scraping, capability promotion, fees inference or broker-specific defaults.
"""
from datetime import timedelta
from typing import Literal
from pydantic import model_validator
from trading_platform.contracts.values import Record, Positive, Time, digest, utc
from ..broker_profile import CaptureScope, Hash, Label, demo_identity
from ..normalization import integer, units


class DocumentGrid(Record):
    minimum: Positive | None = None
    maximum: Positive | None = None
    step: Positive | None = None
    lot: Positive | None = None

    @model_validator(mode='after')
    def nonempty(self):
        if all(v is None for v in self.model_dump().values()):
            raise ValueError('at least one documented grid observation required')
        return self


class ReviewedDocument(Record):
    version: Literal[1] = 1
    scope: CaptureScope
    source: Label
    source_hash: Hash
    reviewed_at: Time
    valid_until: Time
    grid: DocumentGrid

    @model_validator(mode='after')
    def interval(self):
        if self.valid_until <= self.reviewed_at:
            raise ValueError('invalid document review interval')
        return self


def reconcile(probe, document, *, approved_document_hash, now):
    """Document pin must come from independent review, not probe producer.

    Input probe is a retained local observation, not cryptographically signed.
    Output is a comparison artifact and cannot be used as execution capability.
    """
    document=ReviewedDocument.model_validate_json(document.model_dump_json())
    if digest(document)!=approved_document_hash:
        raise ValueError('document review pin mismatch')
    now=utc(now);scope=document.scope;account=scope.identity.account_id
    if not document.reviewed_at <= now < document.valid_until:
        raise ValueError('document review outside validity')
    if (probe.get('status')!='COLLECTED' or probe.get('mode')!='demo-readonly'
            or probe.get('orders_enabled') is not False or probe.get('account_id')!=account):
        raise ValueError('bound read-only probe required')
    at=utc(probe['collected_at'])
    if not 0 <= (now-at).total_seconds() < 86400:
        raise ValueError('stale specification metadata')
    identity=demo_identity(probe['economics'],account=account,binding=probe.get('demo_binding'),
                           generation=probe['generation'])
    scope.verify(identity,digest(scope),now)  # Scope is covered by the independent document pin.
    if str(probe['metadata'].get('ctidTraderAccountId'))!=account:
        raise ValueError('foreign symbol metadata')
    symbols=probe['symbols']
    if (scope.native_symbol not in symbols or integer(symbols[scope.native_symbol])!=scope.symbol_id
            or sum(integer(v)==scope.symbol_id for v in symbols.values())!=1):
        raise ValueError('ambiguous or foreign symbol mapping')
    rows=probe['metadata']['symbol'];ids=[integer(r['symbolId']) for r in rows]
    if len(ids)!=len(set(ids)) or ids.count(scope.symbol_id)!=1:
        raise ValueError('ambiguous or missing symbol metadata')
    raw=rows[ids.index(scope.symbol_id)]
    actual={k:units(raw[v]) for k,v in [('minimum','minVolume'),('maximum','maxVolume'),
                                      ('step','stepVolume'),('lot','lotSize')]}
    if any(v<=0 for v in actual.values()) or actual['maximum']<actual['minimum']:
        raise ValueError('invalid account grid')
    comparisons={k:dict(document=str(v),account=str(actual[k]),matches=v==actual[k])
                 for k,v in document.grid.model_dump().items() if v is not None}
    body=dict(format=1,provider='reviewed_document_v1',identity=identity.model_dump(),
              instrument=scope.instrument,native_symbol=scope.native_symbol,symbol_id=scope.symbol_id,
              source=document.source,source_hash=document.source_hash,document_hash=digest(document),
              input_hash=digest(probe),observed_at=at.isoformat(),reviewed_at=now.isoformat(),
              valid_until=min(at+timedelta(days=1),document.valid_until,scope.valid_until).isoformat(),
              comparisons=comparisons,conflicts=sorted(k for k,v in comparisons.items() if not v['matches']),
              classification='document_comparison_only',orders_enabled=False,qualification_complete=False,
              unresolved=['account_tick_value_provenance','costs_and_settlement','operation_capabilities'])
    body['evidence_hash']=digest(body)
    return body
