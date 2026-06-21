import datetime as dt
import re
import urllib.request
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}
_CUTOFF_DAYS = 30


class TechRssSource(BaseSource):
    name = "tech_rss"
    category = "trends"
    feeds = [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("Wired", "https://www.wired.com/feed/rss"),
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
        ("VentureBeat", "https://venturebeat.com/feed/"),
        ("Hacker News", "https://hnrss.org/newest"),
        ("TechRadar", "https://www.techradar.com/rss"),
        ("ZDNet", "https://www.zdnet.com/news/rss.xml"),
        ("Tom Hardware", "https://www.tomshardware.com/feeds/all"),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("Gizmodo", "https://gizmodo.com/rss"),
        ("Engadget", "https://www.engadget.com/rss.xml"),
        ("Kotaku", "https://kotaku.com/rss"),
        ("Hacker News Frontpage", "https://hnrss.org/frontpage"),
        ("MakeUseOf", "https://www.makeuseof.com/feed/"),
        ("HowToGeek", "https://www.howtogeek.com/feed/"),
        ("The Information", "https://www.theinformation.com/feed"),
        ("Techmeme", "https://www.techmeme.com/feed.xml"),
        ("9to5Mac", "https://9to5mac.com/feed/"),
        ("MacRumors", "https://www.macrumors.com/rss/"),
        ("Android Authority", "https://www.androidauthority.com/feed/"),
        ("XDA Developers", "https://www.xda-developers.com/feed/"),
        ("AnandTech", "https://www.anandtech.com/rss/"),
        ("Snyk Blog", "https://snyk.io/blog/feed/"),
        ("Product Hunt", "https://www.producthunt.com/feed"),
        ("Stratechery", "https://stratechery.com/feed/"),
        ("Azeem Azhar", "https://azeem.substack.com/feed"),
        ("Benedict Evans", "https://www.ben-evans.com/feed"),
        ("Decrypt Tech", "https://decrypt.co/rss"),
        ("TechMonk", "https://www.techmonk.net/feed/"),
        ("Beebom", "https://beebom.com/feed/"),
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
                for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:6]:
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
                            "headline": self._trunc(title, 170),
                            "bullet_points": [
                                self._trunc(f"Tech: {org} — AI, gadgets, software", 120)
                            ],
                            "source": org,
                            "confidence": _tech_conf(title),
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


def _tech_conf(text: str) -> int:
    low = text.lower()
    score = 75
    if any(w in low for w in
           ("ai", "artificial intelligence", "machine learning", "deep learning",
            "gpt", "llm", "openai", "anthropic", "google ai", "chatbot",
            "chip", "semiconductor", "cpu", "gpu", "qualcomm", "nvidia",
            "mac", "iphone", "android", "windows", "apple", "google",
            "microsoft", "meta", "amazon", "aws", "cloud", "startup",
            "tech", "software", "app", "launch", "release", "update",
            "blockchain", "crypto", "bitcoin", "ethereum", "web3")):
        score += 10
    if any(w in low for w in
           ("exclusive", "leak", "rumor", "review", "hands-on", "first look")):
        score += 8
    return min(96, score)
