"""Create a read-only TPR-2 shadow qualification report."""
import argparse
from datetime import datetime,timezone
from trading_platform.qualification.tpr2 import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',default='config/evaluation/tpr2-shadow-v2.json')
    parser.add_argument('--run',action='append',required=True,metavar='SYMBOL=STOPPED_DB_COPY')
    parser.add_argument('--gateway-report',action='append',required=True,metavar='SYMBOL=GATEWAY_REPORT')
    parser.add_argument('--output',required=True)
    args=parser.parse_args();pairs=[]
    for value in args.run:
        symbol,separator,path=value.partition('=')
        if not separator or not symbol or not path: parser.error('--run requires SYMBOL=STOPPED_DB_COPY')
        pairs.append((symbol,path))
    gateways=[]
    for value in args.gateway_report:
        symbol,separator,path=value.partition('=')
        if not separator or not symbol or not path: parser.error('--gateway-report requires SYMBOL=GATEWAY_REPORT')
        gateways.append((symbol,path))
    from collections import Counter
    if Counter(symbol for symbol,_ in gateways)!=Counter(symbol for symbol,_ in pairs):
        parser.error('each run requires one matching gateway report')
    result=run(args.plan,pairs,args.output,datetime.now(timezone.utc),gateways);print(result['status'])


if __name__=='__main__': main()
