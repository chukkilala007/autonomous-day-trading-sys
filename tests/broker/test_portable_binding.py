from datetime import timedelta
import pytest
from twisted.internet.defer import FirstError
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.attended_binding import Binding, ReviewedBundle
from trading_platform.gateways.ctrader.broker_profile import AccountIdentity, BrokerProfile, SymbolMapping
from test_attended_binding import rig, result, T


def configure(x, broker='Example Broker'):
    p=x.bundle.policy
    identity=AccountIdentity(broker=broker,account_id=p.account_id,environment='demo',currency='USD',account_type='HEDGED')
    mapping=SymbolMapping(instrument=p.instrument,native_symbol='EUR/USD.c',**{k:getattr(p,k) for k in
        ('symbol_id','quote_currency','tick','minimum','maximum','step','contract_value_per_unit')})
    profile=BrokerProfile(identity=identity,symbols=(mapping,),observed_at=T-timedelta(seconds=1),valid_until=T+timedelta(minutes=5))
    bundle=ReviewedBundle(**dict(x.bundle.model_dump(),broker_profile=profile,broker_profile_hash=digest(profile)))
    x.raw['ProtoOATraderReq']['trader']['brokerName']=broker
    x.raw['ProtoOASymbolsListReq']['symbol'][0].update(symbolName='EUR/USD.c',quoteAssetId='1')
    binding=Binding(x.session,x.stream,x.db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=x.epoch,now=lambda:x.clock[0])
    return bundle,binding


@pytest.mark.parametrize('broker',['FxPro','Example Broker'])
def test_broker_profile_routes_native_alias_without_changing_strategy(rig,broker):
    bundle,b=configure(rig,broker)
    assert result(b.preview(rig.entry))['status']=='PREPARED_NOT_AUTHORIZED'
    assert b.symbol=='EURUSD'
    assert bundle.broker_profile.identity.broker==broker


@pytest.mark.parametrize('fault',['broker','currency','account_type','quote_asset','live','generation','expired'])
def test_profile_identity_and_session_mismatches_block(rig,fault):
    bundle,b=configure(rig)
    if fault=='broker':rig.raw['ProtoOATraderReq']['trader']['brokerName']='Other'
    if fault=='currency':rig.raw['ProtoOAAssetListReq']['asset'][0]['name']='GBP'
    if fault=='account_type':rig.raw['ProtoOATraderReq']['trader']['accountType']='NETTED'
    if fault=='quote_asset':rig.raw['ProtoOASymbolsListReq']['symbol'][0]['quoteAssetId']='2'
    if fault=='live':rig.session.demo_binding['is_live']=True
    if fault=='generation':rig.session.generation+=1
    if fault=='expired':
        bp=bundle.broker_profile.model_copy(update={'valid_until':T})
        bundle=ReviewedBundle(**dict(bundle.model_dump(),broker_profile=bp,broker_profile_hash=digest(bp)))
        b=Binding(rig.session,rig.stream,rig.db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=rig.epoch,now=lambda:T)
    with pytest.raises((ValueError,FirstError)):result(b.preview(rig.entry))
    assert b._preview_lease is None


def test_profile_pin_geometry_and_legacy_guard(rig):
    rig.raw['ProtoOATraderReq']['trader']['brokerName']='Other'
    with pytest.raises(ValueError):result(rig.binding.preview(rig.entry))
    bundle,_=configure(rig)
    for change in ({'broker_profile_hash':'b'*64},{'broker_profile_hash':None},
                   {'policy':bundle.policy.model_copy(update={'symbol_id':2})}):
        with pytest.raises(ValueError):ReviewedBundle(**dict(bundle.model_dump(),**change))


def test_profile_expiry_caps_preview_lease(rig):
    from trading_platform.contracts.values import utc
    bundle,b=configure(rig)
    bp=bundle.broker_profile.model_copy(update={'valid_until':T+timedelta(seconds=1)})
    bundle=ReviewedBundle(**dict(bundle.model_dump(),broker_profile=bp,broker_profile_hash=digest(bp)))
    b=Binding(rig.session,rig.stream,rig.db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=rig.epoch,now=lambda:T)
    assert utc(result(b.preview(rig.entry))['valid_until'])<=bp.valid_until


def test_reconnect_during_profile_collection_rejects(rig):
    bundle,b=configure(rig);read=rig.session.read
    def changed(name,**kw):
        value=read(name,**kw)
        if name=='ProtoOAExpectedMarginReq':rig.session.generation+=1
        return value
    rig.session.read=changed
    with pytest.raises(ValueError):result(b.preview(rig.entry))
    assert b._preview_lease is None
