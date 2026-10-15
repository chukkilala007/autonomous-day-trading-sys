from collections import defaultdict
from trading_platform.contracts.values import canonical


def validate_history(snapshot):
    grouped=defaultdict(dict)
    for b in snapshot.bars:
        key=(b.instrument,(b.end-b.start).total_seconds())
        old=grouped[key].get(b.start)
        if old is not None and old!=b: raise ValueError('conflicting OHLC revision')
        grouped[key][b.start]=b
    for (_,period),series in grouped.items():
        bars=sorted(series.values(),key=lambda b:b.start)
        if any((b.start-a.start).total_seconds()!=period for a,b in zip(bars,bars[1:])):
            raise ValueError('DATA_GAP: recorded contiguous session history required')
    return tuple(b for key in sorted(grouped) for b in sorted(grouped[key].values(),key=lambda b:b.start))
