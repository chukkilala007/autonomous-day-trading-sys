"""Read-only account view. Ownership comes from persisted broker-ID bindings."""
from trading_platform.contracts.values import canonical


def account_view(account_id,trader,reconcile,deals,owned_ids,*,history_complete):
    for response in (trader,reconcile,deals):
        if str(response.get('ctidTraderAccountId'))!=str(account_id): raise ValueError('foreign account response')
    if str(trader.get('trader',{}).get('ctidTraderAccountId'))!=str(account_id): raise ValueError('foreign trader')
    positions=[];orders=[]
    for field,destination,id_field in (('position',positions,'positionId'),('order',orders,'orderId')):
        seen=set()
        for row in reconcile.get(field,[]):
            identity=str(row[id_field])
            if identity in seen: raise ValueError('duplicate broker entity')
            seen.add(identity)
            destination.append(dict(broker_id=identity,owner=owned_ids.get((field,identity)),record=row))
    complete=bool(history_complete) and not deals.get('hasMore',False)
    return dict(mode='shadow',account_id=str(account_id),trader=trader['trader'],positions=positions,orders=orders,
        deals=deals.get('deal',[]),history_complete=complete,entry_blockers=[] if complete else ['INCOMPLETE_ACCOUNT_HISTORY'],submission_enabled=False)


def persist_view(db,view,at):
    with db.transaction() as c:
        c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('shadow:account',canonical(dict(view,observed_at=at))))
