import datetime as dt
import re
import urllib.request
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}
_CUTOFF_DAYS = 60


class GeoExtraSource(BaseSource):
    name = "geopower_extra"
    category = "geopower"
    feeds = [
        ("Eurasia Group", "https://www.eurasiagroup.com/feed/"),
        ("Stratfor", "https://worldview.stratfor.com/feed/"),
        ("IISS", "https://www.iiss.org/rss/"),
        ("Crisis Group", "https://www.crisisgroup.org/rss.xml"),
        ("Atlantic Council", "https://www.atlanticcouncil.org/feed/"),
    ]

    def fetch(self) -> SourceResult:
        items: list[dict] = []
        seen = set()
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=_CUTOFF_DAYS)
        for org, url in self.feeds:
            try:
                xml = self._request("GET", url, headers=UA)[0].decode(
                    "utf-8", errors="replace"
                )
                for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:8]:
                    title = self._text(
                        raw,
                        r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>",
                    )
                    pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                    link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                    if not title:
                        continue
                    key = title.strip().lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    when = self._parse_dt(pub)
                    if when and when < cutoff:
                        continue
                    items.append(
                        {
                            "category": self.category,
                            "timestamp": self._fmt(pub),
                            "headline": self._trunc(
                                f"{org}: {title}", 170
                            ),
                            "bullet_points": [
                                self._trunc(f"Source: {org}", 120)
                            ],
                            "source": org,
                            "confidence": 88,
                            "url": link,
                        }
                    )
            except Exception:
                continue
        return SourceResult(items=items, source_name=self.name, category=self.category)

    @staticmethod
    def _text(text, pattern):
        m = re.search(pattern, text, re.S)
        if not m:
            return ""
        return next(g for g in m.groups() if g is not None).strip()

    @staticmethod
    def _parse_dt(raw):
        raw = raw.strip()
        if not raw:
            return None
        try:
            import email.utils

            return email.utils.parsedate_to_datetime(raw)
        except Exception:
            return None

    @staticmethod
    def _fmt(raw):
        raw = raw.strip()
        if not raw:
            return (
                __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .strftime("%Y-%m-%d %H:%M UTC")
            )
        try:
            import email.utils

            t = email.utils.parsedate_to_datetime(raw)
            return t.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return raw

    @staticmethod
    def _trunc(text, n=180):
        t = text.strip()
        return t if len(t) <= n else t[: n - 1].rstrip() + "…"
