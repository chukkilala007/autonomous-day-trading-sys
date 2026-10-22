import copy
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest
from twisted.internet.defer import succeed, Deferred
from trading_platform.contracts.values import digest
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.events import Quote
from trading_platform.gateways.ctrader.attended_binding import Binding, ReviewedBundle
from trading_platform.gateways.ctrader.contract_builder import Policy
from trading_platform.gateways.ctrader.read_only_session import ReadOnlySession
from trading_platform.gateways.ctrader.stream import Stream
from trading_platform.gateways.ctrader.orders import Fence
from trading_platform.market_data.service import Feed
from trading_platform.persistence.database import Database

T=datetime(2026,10,22,tzinfo=timezone.utc);H='a'*64


def result(d):
    out=[];errors=[];d.addCallbacks(out.append,errors.append)
    if errors:errors[0].raiseException()
    assert out
    return out[0]


@pytest.fixture
def rig(tmp_path):
    db=Database(tmp_path/'state');clock=[T];calls=[]
    client=SimpleNamespace(setConnectedCallback=lambda c:None,setDisconnectedCallback=lambda c:None)
    client.setMessageReceivedCallback=lambda c:setattr(client,'received',c)
    session=ReadOnlySession(client,None,12);session.ready=True;session.generation=1
    session.demo_binding=dict(account_id='12',generation=1,is_live=False)
    raw={
      'ProtoOASymbolsListReq':dict(ctidTraderAccountId='12',symbol=[dict(symbolId='1',symbolName='EURUSD')]),
      'ProtoOASymbolByIdReq':dict(ctidTraderAccountId='12',symbol=[dict(symbolId='1',tradingMode='ENABLED',distanceSetIn='SYMBOL_DISTANCE_IN_POINTS',slDistance=0,tpDistance=0,minVolume='100000',maxVolume='5000000000',stepVolume='100000')]),
      'ProtoOAAssetListReq':dict(ctidTraderAccountId='12',asset=[dict(assetId='1',name='USD')]),
      'ProtoOATraderReq':dict(ctidTraderAccountId='12',trader=dict(ctidTraderAccountId='12',balance='1000000',moneyDigits=2,depositAssetId='1',accountType='HEDGED',totalMarginCalculationType='MAX',balanceVersion='3',brokerName='FxPro',accessRights='FULL_ACCESS',isLimitedRisk=False)),
      'ProtoOAReconcileReq':dict(ctidTraderAccountId='12',order=[],position=[]),
      'ProtoOAGetPositionUnrealizedPnLReq':dict(ctidTraderAccountId='12',moneyDigits=2,positionUnrealizedPnL=[]),
      'ProtoOAExpectedMarginReq':dict(ctidTraderAccountId='12',moneyDigits=2,margin=[dict(volume='100000',buyMargin='4000',sellMargin='4000')])}
    def read(name,**kw):
        calls.append((name,kw));return succeed(copy.deepcopy(raw[name]))
    session.read=read
    feed=Feed(db);stream=Stream(session,feed,{'EURUSD':1},[],lambda:clock[0]);stream.subscribed_generation=1
    feed.repaired('EURUSD',T);feed.ingest_quote(Quote(instrument='EURUSD',bid='1.1001',ask='1.1002',source_time=T,received_at=T))
    policy=Policy(account_id='12',instrument='EURUSD',symbol_id=1,currency='USD',quote_currency='USD',tick='0.00001',minimum='1000',maximum='50000000',step='1000',contract_value_per_unit='1',roundtrip_cost_per_unit='0.0002',minimum_total_cost='0',fixed_cost='0',cost_coverage='complete_roundtrip_upper_bound',classification='broker_verified',evidence_hash=H,observed_at=T-timedelta(days=1),valid_until=T+timedelta(days=1))
    bundle=ReviewedBundle(policy=policy,source_hash=H,image_digest=H,price_grid_review=H,protection_review=H,costs_review=H,entry_expiry_review=H,profile='EURUSD_USD_absolute_protected_buy_limit_gtd')
    epoch=Fence(db,12).acquire('core')
    binding=Binding(session,stream,db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=epoch,now=lambda:clock[0])
    entry=Entry(instrument='EURUSD',side='buy',order_type='limit',entry='1.1',worst_fill='1.1',stop='1.099',target='1.102',expires_at=T+timedelta(seconds=60))
    yield SimpleNamespace(**locals())
    db.close()


def test_reads_real_components_no_valuation_or_readiness_arguments(rig):
    r=result(rig.binding.preview(rig.entry))
    assert r['status']=='PREPARED_NOT_AUTHORIZED' and not r['orders_enabled']
    assert r['quantity']==1000 and r['margin']==40
    assert r['planned_loss']==__import__('decimal').Decimal('1.2')
    assert {n for n,_ in rig.calls}==set(rig.raw)
    assert rig.calls[-1]==('ProtoOAExpectedMarginReq',dict(symbolId=1,volume=[100000]))
    assert rig.db.connection.execute('SELECT count(*) FROM commands').fetchone()[0]==0


@pytest.mark.parametrize('fault',['live','generation','disconnected','fence','quote_invalid','buffer','stale','mapping','volume','profile','foreign_margin','exposure','policy','event','ledger'])
def test_fail_closed(rig,fault):
    x=rig
    if fault=='live':x.session.demo_binding['is_live']=True
    if fault=='generation':x.session.generation+=1
    if fault=='disconnected':x.session.ready=False
    if fault=='fence':Fence(x.db,12).acquire('other')
    if fault=='quote_invalid':x.feed.invalidate_quote('EURUSD')
    if fault=='buffer':x.feed.put('quote-buffer-pending:EURUSD',{'pending':True})
    if fault=='stale':x.clock[0]+=timedelta(seconds=3)
    if fault=='mapping':x.raw['ProtoOASymbolsListReq']['symbol'][0]['symbolName']='OTHER'
    if fault=='volume':x.raw['ProtoOASymbolByIdReq']['symbol'][0]['minVolume']='200000'
    if fault=='profile':x.raw['ProtoOATraderReq']['trader']['isLimitedRisk']=True
    if fault=='foreign_margin':x.raw['ProtoOAExpectedMarginReq']['ctidTraderAccountId']='13'
    if fault=='exposure':x.raw['ProtoOAReconcileReq']['order']=[dict(orderId='7')]
    if fault=='policy':x.clock[0]+=timedelta(days=2)
    if fault=='event':x.binding.failed_event=True
    if fault=='ledger':x.feed.put('gateway-send:old',{})
    with pytest.raises(ValueError):result(x.binding.preview(x.entry))
    assert not x.binding.busy


@pytest.mark.parametrize('race',['generation','fence','ledger','event','latency'])
def test_inflight_change_discards_result(rig,race):
    x=rig;pending=Deferred();old=x.session.read
    x.session.read=lambda name,**kw:pending if name=='ProtoOAExpectedMarginReq' else old(name,**kw)
    d=x.binding.preview(x.entry)
    if race=='generation':x.session.generation+=1
    if race=='fence':Fence(x.db,12).acquire('other')
    if race=='ledger':x.feed.put('gateway-send:late',{})
    if race=='event':x.binding.revision+=1
    if race=='latency':x.clock[0]+=timedelta(seconds=3)
    pending.callback(x.raw['ProtoOAExpectedMarginReq'])
    with pytest.raises(ValueError):result(d)


def test_latency_does_not_roll_expiry(rig):
    rig.clock[0]+=timedelta(milliseconds=500)
    r=result(rig.binding.preview(rig.entry))
    assert r['entry'].expires_at==rig.entry.expires_at
    assert r['proposal_created_at']==T


def test_unpinned_policy_refused(rig):
    with pytest.raises(ValueError,match='pin'):
        Binding(rig.session,rig.stream,rig.db,rig.bundle,approved_bundle_hash='b'*64,core_id='core',epoch=1,now=lambda:T)


def test_competing_preview_rejected(rig):
    rig.binding.busy=True
    with pytest.raises(ValueError,match='already running'):result(rig.binding.preview(rig.entry))
    assert not rig.calls


def test_mutating_original_review_does_not_change_pin(rig):
    object.__setattr__(rig.bundle.policy,'tick',__import__('decimal').Decimal('1'))
    assert result(rig.binding.preview(rig.entry))['status']=='PREPARED_NOT_AUTHORIZED'


def test_execution_callback_invalidates_inflight(rig):
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAExecutionEvent
    from ctrader_open_api import Protobuf
    message=ProtoOAExecutionEvent(ctidTraderAccountId=12,executionType=2)
    from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage
    rig.client.received(None,ProtoMessage(payloadType=message.payloadType,payload=message.SerializeToString()))
    assert rig.binding.failed_event and rig.binding.revision==1
    with pytest.raises(ValueError):result(rig.binding.preview(rig.entry))


def test_malformed_event_invalidates(rig):
    rig.client.received(None,object())
    assert rig.binding.failed_event


def test_disconnect_revokes_demo_binding(rig):
    rig.session.disconnected()
    assert rig.session.demo_binding is None and not rig.session.ready
    with pytest.raises(ValueError):result(rig.binding.preview(rig.entry))


def test_changed_balance_during_collection_rejected(rig):
    old=rig.session.read;count=[0]
    def read(name,**kw):
        if name=='ProtoOATraderReq':
            count[0]+=1
            if count[0]==2:rig.raw[name]['trader']['balanceVersion']='4'
        return old(name,**kw)
    rig.session.read=read
    with pytest.raises(Exception):result(rig.binding.preview(rig.entry))


def test_review_and_symbol_grid_are_independently_bound(rig):
    rig.raw['ProtoOASymbolByIdReq']['ctidTraderAccountId']='13'
    with pytest.raises(ValueError,match='metadata'):result(rig.binding.preview(rig.entry))
