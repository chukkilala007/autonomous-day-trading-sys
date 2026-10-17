from trading_platform.risk.sizing import size


def check_entry(entry,quote,now):
    if now>=entry.expires_at: raise ValueError('ENTRY_EXPIRED')
    if quote.instrument!=entry.instrument or not 0<=(now-quote.source_time).total_seconds()<=2:
        raise ValueError('STALE_OR_WRONG_QUOTE')
    if entry.basis!='executable': raise ValueError('RESEARCH_GEOMETRY')
    price=quote.ask if entry.side=='buy' else quote.bid
    if entry.order_type=='market':
        if (entry.side=='buy' and price>entry.worst_fill) or (entry.side=='sell' and price<entry.worst_fill): raise ValueError('FILL_BOUND')
    if entry.order_type in ('stop','stop_limit'):
        if (entry.side=='buy' and price>=entry.entry) or (entry.side=='sell' and price<=entry.entry): raise ValueError('ENTRY_ALREADY_CROSSED')
    if entry.order_type=='stop_limit':
        if entry.side=='buy' and not entry.entry<=entry.limit<=entry.worst_fill: raise ValueError('stop-limit bounds')
        if entry.side=='sell' and not entry.entry>=entry.limit>=entry.worst_fill: raise ValueError('stop-limit bounds')
    if entry.side=='buy' and price<=entry.stop or entry.side=='sell' and price>=entry.stop: raise ValueError('STOP_INVALIDATED')


def plan(decision,instance,quote,contract,now,balance,equity,free_margin):
    if instance.mode not in ('paper','demo'): raise ValueError('execution mode disabled')
    if (decision.instance,decision.account,decision.environment,decision.config_hash)!=(instance.instance_id,instance.account.alias,instance.account.environment,instance.hash): raise ValueError('decision binding mismatch')
    if decision.outcome!='ENTRY': raise ValueError('entry decision required')
    if decision.at>now: raise ValueError('future decision')
    check_entry(decision.proposal,quote,now)
    if contract.account_currency!=instance.account.currency: raise ValueError('account currency mismatch')
    if contract.exact_costs and contract.exact_costs.account_id!=instance.account.broker_account: raise ValueError('quantity economics account mismatch')
    return size(decision.proposal,contract,balance*min(instance.account.per_trade,instance.allocation),now=now,free_margin=free_margin,equity=equity,reserve_fraction=instance.account.free_margin_fraction)
