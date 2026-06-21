import datetime as dt
import re
import urllib.request
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}

_CUTOFF_DAYS = 60


class GeopowerSource(BaseSource):
    name = "geopower"
    category = "geopower"
    feeds = [
        ("Reuters World", "https://www.reutersagency.com/feed/?best-topics=world&post_type=best"),
        ("AP Top News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
        ("IEA News", "https://www.iea.org/rss"),
        ("CSIS", "https://www.csis.org/rss.xml"),
        ("Foreign Affairs", "https://www.foreignaffairs.com/rss.xml"),
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("France24", "https://www.france24.com/en/rss"),
        ("The Diplomat", "https://thediplomat.com/feed/"),
        ("Fox News World", "https://feeds.foxnews.com/foxnews/world"),
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
                    low = (title + " " + self._desc(raw)).lower()
                    score = sum(
                        1 for k in geopolitical_keywords if k in low
                    )
                    if score < 1 and org not in {
                        "Reuters World",
                        "UN News",
                        "CSIS",
                        "AP Top News",
                        "BBC World",
                        "Al Jazeera",
                        "France24",
                        "The Diplomat",
                        "Fox News World",
                    }:
                        continue
                    items.append(
                        {
                            "category": self.category,
                            "timestamp": self._fmt(pub),
                            "headline": self._trunc(title, 170),
                            "bullet_points": [
                                self._trunc(f"Source: {org}", 120)
                            ],
                            "source": org,
                            "confidence": min(93, 78 + score * 3),
                            "url": link,
                        }
                    )
            except Exception:
                continue
        return SourceResult(items=items, source_name=self.name, category=self.category)

    @staticmethod
    def _desc(raw):
        m = re.search(
            r"<description[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</description>",
            raw,
            re.S,
        )
        if not m:
            return ""
        return next(g for g in m.groups() if g is not None)

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


geopolitical_keywords = [
    "sanctions", "treaty", "war", "conflict", "oil", "energy", "trade war",
    "summit", "nuclear", "tariff", "diplomat", "agreement", "un security council",
    "military", "defense", "border", "election", "coup", "alliance", "nato",
    "opec", "gas", "lithium", "copper", "supply chain", "strait", "missile",
    "iran", "ukraine", "russia", "china", "taiwan", "israel", "lebanon",
    "hormuz", "pentagon", "white house", "congress", "brexit", "europe",
    "asia", "africa", "latin america", "middle east",
]
