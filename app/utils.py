from datetime import datetime
from dateutil.relativedelta import relativedelta

def is_older_than_one_month(date_string: str) -> bool:
    try:
        date = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        now = datetime.now(date.tzinfo)
        return date < now - relativedelta(months=1)
    except:
        return True
