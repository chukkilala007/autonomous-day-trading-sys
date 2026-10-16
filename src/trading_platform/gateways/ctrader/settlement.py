"""Complete hedged-position deal settlement with explicit audited fee semantics."""
from decimal import Decimal
from typing import Literal
from trading_platform.contracts.values import Record,Name,Time,canonical,digest
from .valuation import Hash,Settlement
from .execution import money
from .normalization import integer,timestamp_ms


class CostPolicy(Record):
    account_id: Name
    evidence_hash: Hash
    verified_at: Time
    valid_until: Time
    commission_sign: Literal['signed_cash','positive_charge']
    conversion_fee_sign: Literal['signed_cash','positive_charge']
    closing_commission_source: Literal['deal','close_detail']
    closing_commission_excludes_opening: Literal[True]
    all_costs_covered: Literal[True]


def charge(value,convention):
    if value is None: raise ValueError('missing scaled cost')
    if convention=='positive_charge':
        if value<0: raise ValueError('negative unsigned charge')
        return -value
    return value


def settle(account,command,position_id,entry_order_id,expected_quantity,deals,history_from,history_to,now,policy):
    policy=CostPolicy.model_validate_json(policy.model_dump_json())
    if policy.account_id!=str(account) or not policy.verified_at<=now<policy.valid_until:
        raise ValueError('account-bound current cost policy required')
    if not deals: raise ValueError('complete lifecycle deals required')
    ids=set();opened=Decimal(0);closed=Decimal(0);movements=[];opens=[];closes=[];symbol=None;side=None
    def movement(deal,suffix,amount):
        if amount is None: raise ValueError('scaled cash movement missing')
        movements.append(dict(id=str(deal['dealId'])+':'+suffix,position_id=str(position_id),amount=str(amount),
                              currency=command['currency'],evidence_hash=digest(deal)))
    for deal in sorted(deals,key=lambda d:(integer(d['executionTimestamp']),str(d['dealId']))):
        identity=str(deal['dealId'])
        if identity in ids or str(deal['positionId'])!=str(position_id): raise ValueError('duplicate/foreign position deal')
        ids.add(identity)
        if deal['dealStatus'] not in ('FILLED','PARTIALLY_FILLED'): raise ValueError('nonexecuted deal in settlement')
        if symbol is None: symbol=str(deal['symbolId'])
        if str(deal['symbolId'])!=symbol: raise ValueError('position symbol changed')
        quantity=Decimal(integer(deal['filledVolume']))/100
        if quantity<=0: raise ValueError('positive executed quantity required')
        at=timestamp_ms(deal['executionTimestamp'])
        detail=deal.get('closePositionDetail')
        if detail is None:
            if str(deal['orderId'])!=str(entry_order_id): raise ValueError('scale-in/multiple entry orders unsupported')
            if side is None: side=deal['tradeSide']
            if side not in ('BUY','SELL') or deal['tradeSide']!=side: raise ValueError('entry side changed')
            opened+=quantity;opens.append(at)
            movement(deal,'commission',charge(money(deal,'commission'),policy.commission_sign))
        else:
            if side is None or deal['tradeSide']==side or deal['tradeSide'] not in ('BUY','SELL'): raise ValueError('invalid closing side')
            if Decimal(integer(detail['closedVolume']))/100!=quantity: raise ValueError('closing quantity mismatch')
            closed+=quantity;closes.append(at)
            if closed>opened: raise ValueError('history closes more than known entry')
            movement(deal,'gross',money(detail,'grossProfit'))
            movement(deal,'swap',money(detail,'swap'))
            source=deal if policy.closing_commission_source=='deal' else detail
            movement(deal,'commission',charge(money(source,'commission'),policy.commission_sign))
            movement(deal,'conversion',charge(money(detail,'pnlConversionFee'),policy.conversion_fee_sign))
    if not opens or not closes or opened!=expected_quantity or opened!=closed:
        raise ValueError('complete entry/exit quantities required')
    return Settlement.model_validate_json(canonical(dict(command_id=command['id'],position_id=str(position_id),
        opened=opened,closed=closed,complete=True,costs_complete=True,history_from=history_from,
        opened_at=min(opens),closed_at=max(closes),history_to=history_to,movements=movements,
        evidence_hash=digest(dict(policy=policy,deals=deals)))))
