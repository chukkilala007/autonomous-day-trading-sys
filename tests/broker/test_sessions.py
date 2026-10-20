from datetime import datetime, timezone
import pytest
from trading_platform.gateways.ctrader.sessions import scheduled_state


def symbol():
    return dict(tradingMode='ENABLED', scheduleTimeZone='UTC',
                schedule=[dict(startSecond=162045, endSecond=248385)])


@pytest.mark.parametrize('stamp,expected', [
    ('2026-10-19T21:00:44+00:00', 'SCHEDULED_CLOSED'),
    ('2026-10-19T21:00:45+00:00', 'SCHEDULED_OPEN'),
    ('2026-10-20T20:59:44.999999+00:00', 'SCHEDULED_OPEN'),
    ('2026-10-20T20:59:45+00:00', 'SCHEDULED_CLOSED'),
    ('2026-10-19T22:00:45+01:00', 'SCHEDULED_OPEN'),
])
def test_account_schedule_uses_sunday_origin_and_exclusive_end(stamp, expected):
    assert scheduled_state(symbol(), datetime.fromisoformat(stamp)) == expected


def test_holidays_and_unsupported_metadata_fail_closed():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    raw = symbol()
    raw['holiday'] = [dict(scheduleTimeZone='UTC', isRecurring=True,
                           holidayDate=(datetime(2025, 10, 20, tzinfo=timezone.utc)-datetime(1970, 1, 1, tzinfo=timezone.utc)).days,
                           startSecond=0, endSecond=3600)]
    assert scheduled_state(raw, now) == 'HOLIDAY_CLOSED'
    del raw['holiday'][0]['endSecond']
    assert scheduled_state(raw, now) == 'UNKNOWN'
    raw = symbol(); raw['scheduleTimeZone'] = 'Europe/London'
    assert scheduled_state(raw, now) == 'UNKNOWN'
    raw = symbol(); raw['tradingMode'] = 'CLOSE_ONLY_MODE'
    assert scheduled_state(raw, now) == 'ENTRY_DISABLED'
    raw = symbol(); raw['schedule'].append(raw['schedule'][0])
    with pytest.raises(ValueError, match='overlapping'): scheduled_state(raw, now)


def test_nonrecurring_holiday_does_not_recur_and_missing_mode_is_unknown():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    raw = symbol()
    raw['holiday'] = [dict(scheduleTimeZone='UTC', isRecurring=False, holidayDate=0)]
    assert scheduled_state(raw, now) == 'SCHEDULED_OPEN'
    del raw['tradingMode']
    assert scheduled_state(raw, now) == 'UNKNOWN'
