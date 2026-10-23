"""Explicit attended operation requirements; no alternative order or authorization."""
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import digest, utc

# Compound entry capability prevents independent flags implying atomic attachment.
REQUIRED = ('BUY_LIMIT_ABSOLUTE_SLTP_GTD_60S', 'CANCEL_PENDING', 'CLOSE_POSITION')


def plan(profile, entry, *, authenticated_identity, approved_hash, now):
    now=utc(now)
    profile=profile.verify(authenticated_identity=authenticated_identity,approved_hash=approved_hash,now=now)
    entry=Entry.model_validate_json(entry.model_dump_json())
    mappings=[s for s in profile.symbols if s.instrument==entry.instrument]
    if len(mappings)!=1: raise ValueError('unmapped operation instrument')
    mapping=mappings[0]
    blockers=[]
    if (profile.identity.environment!='demo' or profile.identity.account_type!='HEDGED'
            or profile.identity.currency!='USD' or mapping.quote_currency!='USD'):
        blockers.append('UNSUPPORTED_ACCOUNT_CONTRACT')
    if (entry.side!='buy' or entry.order_type!='limit' or entry.profile!='protected'
            or entry.basis!='executable' or entry.target is None or entry.exit_at is not None
            or entry.entry!=entry.worst_fill):
        blockers.append('UNSUPPORTED_OPERATION_PROFILE')
    # The caller must preserve original expiry; this function never renews it.
    from datetime import timedelta
    created=entry.expires_at-timedelta(seconds=60)
    if not created<=now<=created+timedelta(seconds=10):
        blockers.append('PROPOSAL_NOT_CURRENT')
    requirements=[];valid_until=min(profile.valid_until,entry.expires_at)
    for operation in REQUIRED:
        evidence=next((e for e in profile.evidence if e.instrument==entry.instrument and e.operation==operation),None)
        state=profile.capability(entry.instrument,operation,authenticated_identity=authenticated_identity,
                                 approved_hash=approved_hash,now=now)
        if evidence is None: reason='MISSING_EVIDENCE'
        elif evidence.classification not in ('broker_verified','demo_observed'): reason='UNQUALIFIED_EVIDENCE'
        elif not evidence.observed_at<=now<evidence.valid_until: reason='EVIDENCE_NOT_CURRENT'
        elif state=='unknown': reason='EXPLICIT_UNKNOWN'
        elif state=='unsupported': reason='BROKER_UNSUPPORTED'
        else: reason='REVIEWED_SUPPORTED'
        requirements.append(dict(operation=operation,state=state,reason=reason,
                                 evidence_hash=digest(evidence) if evidence else None))
        if state!='supported': blockers.append(('UNSUPPORTED:' if state=='unsupported' else 'UNKNOWN:')+operation)
        else: valid_until=min(valid_until,evidence.valid_until)
    return dict(status='BLOCKED' if blockers else 'SUPPORTED_NOT_AUTHORIZED',blockers=blockers,
                requirements=requirements,profile_hash=digest(profile),proposal_hash=digest(entry),
                valid_until=valid_until.isoformat(),orders_enabled=False,alternatives=[])
