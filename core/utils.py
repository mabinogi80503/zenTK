def make_datetime(timestr):
    from time import mktime, strptime
    from datetime import datetime
    return datetime.fromtimestamp(mktime(strptime(timestr, "%Y-%m-%d %H:%M:%S")))


def get_datime_diff_from_now(timestr):
    from time import mktime, strptime
    from datetime import timedelta, datetime
    target_at = datetime.fromtimestamp(mktime(strptime(timestr, '%Y-%m-%d %H:%M:%S')))
    target_at = target_at - timedelta(hours=1)  # JP 轉 TW
    now_at = datetime.now()
    return now_at - target_at
