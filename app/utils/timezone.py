from datetime import datetime, timezone, timedelta, date

# Indian Standard Time (IST) is UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_time(*args, **kwargs) -> datetime:
    """Returns the current local datetime in IST as a timezone-unaware object."""
    return datetime.now(IST).replace(tzinfo=None)

def get_ist_date(*args, **kwargs) -> date:
    """Returns the current local date in IST."""
    return datetime.now(IST).date()
