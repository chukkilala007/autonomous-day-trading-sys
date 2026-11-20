"""Complete hedged-position deal settlement with explicit audited fee semantics."""
from decimal import Decimal
from typing import Literal
from trading_platform.contracts.values import Record,Name,Time,Number,Positive,canonical,digest
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


class DeferredCostPolicy(Record):
    account_id: Name
    classification: Literal['settlement_review_pending']
    review_hash: Hash
    verified_at: Time
    valid_until: Time
    all_costs_covered: Literal[False] = False


class ObservedZeroCostPolicy(Record):
    """Exact completed demo lifecycle only; no general fee-sign claim."""
    classification: Literal['demo_observed_zero_cost_lifecycle']
    account_id: Name
    command_id: Name
    position_id: Name
    entry_order_id: Name
    currency: Name
    quantity: Positive
    deals_hash: Hash
    balance_before: Number
    balance_after: Number
    baseline_evidence_hash: Hash
    review_hash: Hash
    history_from: Time
    verified_at: Time
    valid_until: Time


def verify_observed_cash(policy, deals, cashflows, economics):
    p=ObservedZeroCostPolicy.model_validate_json(policy.model_dump_json())
    if (economics['account_id']!=p.account_id or economics['account']['currency']!=p.currency
            or Decimal(economics['account']['balance'])!=p.balance_after
            or economics['reconciliation'].get('order') or economics['reconciliation'].get('position')
            or cashflows or digest(sorted(deals,key=lambda d:str(d['dealId'])))!=p.deals_hash):
        raise ValueError('observed lifecycle cash evidence changed')
    if any(str(d['positionId'])!=p.position_id for d in deals):
        raise ValueError('other lifecycle in observed cash window')
    gross=Decimal(0)
    for d in deals:
        if money(d,'commission')!=0: raise ValueError('nonzero or missing observed commission')
        detail=d.get('closePositionDetail')
        if detail is not None:
            if any(money(detail,k)!=0 for k in ('commission','swap','pnlConversionFee')):
                raise ValueError('nonzero or missing observed closing costs')
            amount=money(detail,'grossProfit')
            if amount is None: raise ValueError('missing observed gross profit')
            gross+=amount
    closing=[d for d in deals if 'closePositionDetail' in d]
    if not closing or money(max(closing,key=lambda d:integer(d['executionTimestamp']))['closePositionDetail'],'balance')!=p.balance_after:
        raise ValueError('closing balance mismatch')
    if p.balance_after-p.balance_before!=gross:
        raise ValueError('observed balance change unexplained')


class SettlementReviewRequired(ValueError):
    pass


def charge(value,convention):
    if value is None: raise ValueError('missing scaled cost')
    if convention=='positive_charge':
        if value<0: raise ValueError('negative unsigned charge')
        return -value
    return value


def settle(account,command,position_id,entry_order_id,expected_quantity,deals,history_from,history_to,now,policy):
    if isinstance(policy, DeferredCostPolicy):
        value=DeferredCostPolicy.model_validate_json(policy.model_dump_json())
        if value.account_id != str(account): raise ValueError('foreign deferred settlement policy')
        raise SettlementReviewRequired('observed settlement requires review; no completion inferred')
    if isinstance(policy, ObservedZeroCostPolicy):
        p=ObservedZeroCostPolicy.model_validate_json(policy.model_dump_json())
        if (str(account)!=p.account_id or command['id']!=p.command_id or command['currency']!=p.currency
                or str(position_id)!=p.position_id or str(entry_order_id)!=p.entry_order_id
                or expected_quantity!=p.quantity or history_from>p.history_from
                or not p.history_from<p.verified_at<=now<p.valid_until
                or digest(sorted(deals,key=lambda d:str(d['dealId'])))!=p.deals_hash):
            raise ValueError('observed settlement scope mismatch')
        # Zero costs make sign and duplicate-incidence conventions irrelevant for
        # this exact reviewed lifecycle. The provider separately checks cash evidence.
        verify_observed_cash(p,deals,[],dict(account_id=p.account_id,
            account=dict(currency=p.currency,balance=str(p.balance_after)),reconciliation={}))
        scoped=CostPolicy(account_id=p.account_id,evidence_hash=digest(p),verified_at=p.verified_at,
            valid_until=p.valid_until,commission_sign='signed_cash',conversion_fee_sign='signed_cash',
            closing_commission_source='close_detail',closing_commission_excludes_opening=True,all_costs_covered=True)
        return settle(account,command,position_id,entry_order_id,expected_quantity,deals,history_from,history_to,now,scoped)
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
