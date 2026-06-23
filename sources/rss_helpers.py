import datetime as dt
import email.utils
import re


def _text(text, pattern):
    """Extract first matching group from a regex search in `text`."""
    m = re.search(pattern, text, re.S)
    if not m:
        return ""
    return next(g for g in m.groups() if g is not None).strip()


def _parse_dt(raw):
    """Parse an RFC-2822-ish date string into a datetime, or None."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return email.utils.parsedate_to_datetime(raw)
    except Exception:
        return None


def _fmt(raw):
    """Format a date string as UTC datetime, falling back to raw text."""
    raw = raw.strip()
    if not raw:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        t = email.utils.parsedate_to_datetime(raw)
        return t.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return raw


def _trunc(text, n=180):
    """Trim text to length `n`, appending an ellipsis if truncated."""
    t = text.strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"
