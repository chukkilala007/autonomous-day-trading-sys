"""Interpret account symbol schedules; scheduled open is not execution readiness.

The supported broker profile uses UTC schedules. Unknown time zones, holiday
boundaries or trading modes fail closed instead of using public marketing hours.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .normalization import integer


def scheduled_state(symbol, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone required')
    now = now.astimezone(timezone.utc)
    mode = symbol.get('tradingMode')
    if mode in ('DISABLED_WITHOUT_PENDINGS_EXECUTION', 'DISABLED_WITH_PENDINGS_EXECUTION', 'CLOSE_ONLY_MODE'):
        return 'ENTRY_DISABLED'
    if mode != 'ENABLED' or symbol.get('scheduleTimeZone') != 'UTC':
        return 'UNKNOWN'
    schedule = symbol.get('schedule')
    if not isinstance(schedule, list) or not schedule:
        return 'UNKNOWN'
    intervals = []
    for row in schedule:
        start, end = integer(row['startSecond']), integer(row['endSecond'])
        if not 0 <= start < end <= 604800:
            raise ValueError('invalid weekly interval')
        intervals.append((start, end))
    intervals.sort()
    if any(left[1] > right[0] for left, right in zip(intervals, intervals[1:])):
        raise ValueError('overlapping weekly intervals')
    seconds = ((now.weekday() + 1) % 7) * 86400 + now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6
    if not any(start <= seconds < end for start, end in intervals):
        return 'SCHEDULED_CLOSED'
    for holiday in symbol.get('holiday', []):
        if type(holiday.get('isRecurring')) is not bool:
            return 'UNKNOWN'
        try:
            holiday_now = now.astimezone(ZoneInfo(holiday['scheduleTimeZone']))
        except (KeyError, ValueError, ZoneInfoNotFoundError):
            return 'UNKNOWN'
        day = (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=integer(holiday['holidayDate']))).date()
        applies = (day.month, day.day) == (holiday_now.month, holiday_now.day) if holiday['isRecurring'] else day == holiday_now.date()
        if not applies:
            continue
        if 'startSecond' not in holiday or 'endSecond' not in holiday:
            return 'UNKNOWN'
        start, end = integer(holiday['startSecond']), integer(holiday['endSecond'])
        if not 0 <= start < end <= 86400:
            raise ValueError('invalid holiday interval')
        local_seconds = holiday_now.hour * 3600 + holiday_now.minute * 60 + holiday_now.second + holiday_now.microsecond / 1e6
        if start <= local_seconds < end:
            return 'HOLIDAY_CLOSED'
    return 'SCHEDULED_OPEN'
