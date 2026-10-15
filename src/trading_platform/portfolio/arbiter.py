"""Stable priority; confidence/R:R are not comparable across strategies."""
from decimal import Decimal


def arbitrate(decisions,priorities):
    return sorted(decisions,key=lambda d:(priorities.get(d.instance,100),d.at,d.id))


def external_risk(exposures):
    total=Decimal(0)
    for exposure in exposures:
        if exposure.get('verified') is not True or exposure.get('risk') is None:
            raise ValueError('EXTERNAL_EXPOSURE_UNVALUED')
        risk=Decimal(exposure['risk'])
        if not risk.is_finite() or risk<0: raise ValueError('invalid external risk')
        total+=risk
    return total
