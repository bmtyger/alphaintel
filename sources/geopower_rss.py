import datetime as dt
import re
import urllib.request
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}
_CUTOFF_DAYS = 30


class GeopowerRssSource(BaseSource):
    name = "geopower_rss"
    category = "geopower"
    feeds = [
        ("Reuters World", "https://www.reutersagency.com/feed/?best-topics=world&post_type=best"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-general"),
        ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
        ("NPR World", "https://feeds.npr.org/1001/rss.xml"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("France24", "https://www.france24.com/en/rss"),
        ("Middle East Eye", "https://www.middleeasteye.net/rss"),
        ("Egypt Independent", "https://egyptindependent.com/feed/"),
        ("South China Morning Post", "https://www.scmp.com/rss/4/feed"),
        ("Japan Times", "https://www.japantimes.co.jp/feed/"),
        ("India Times", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
        ("Foreign Affairs", "https://www.foreignaffairs.com/rss.xml"),
        ("CSIS", "https://www.csis.org/rss.xml"),
        ("Crisis Group", "https://www.crisisgroup.org/rss.xml"),
        ("Atlantic Council", "https://www.atlanticcouncil.org/feed/"),
        ("IISS", "https://www.iiss.org/rss/"),
        ("Eurasia Group", "https://www.eurasiagroup.com/feed/"),
        ("Stratfor", "https://worldview.stratfor.com/feed/"),
        ("The Diplomat", "https://thediplomat.com/feed/"),
        ("Fox News World", "https://feeds.foxnews.com/foxnews/world"),
        ("Russia Today", "https://www.rt.com/news/rss/"),
        ("Times of Israel", "https://www.timesofisrael.com/feed/"),
        ("Haaretz", "https://www.haaretz.com/rss"),
        ("Jerusalem Post", "https://www.jpost.com/rss"),
        ("Korea Herald", "http://www.koreaherald.com/rss/"),
        ("Straits Times", "https://www.straitstimes.com/news/global/rss.xml"),
        ("Nikkei Asia", "https://asia.nikkei.com/rss/feed"),
        ("Reuters Asia", "https://www.reutersagency.com/feed/?best-topics=asia&post_type=best"),
        ("UNCTAD", "https://unctad.org/rss"),
        ("Asharq", "https://eng-archive.aawsat.com/rss"),
        ("Arab News", "https://www.arabnews.com/rss"),
        ("Guardian World", "https://www.theguardian.com/world/rss"),
        ("DW News", "https://rss.dw.com/rss/rss-en-world"),
        ("CNBC World", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
        ("CNN World", "http://rss.cnn.com/rss/edition_world.rss"),
        ("ABC World", "https://abcnews.go.com/International/rss"),
        ("CBS News", "https://www.cbsnews.com/xml/rss/headlines"),
        ("NBC News", "https://feeds.nbcnews.com/nbcnews/news/world"),
        ("Politico", "https://www.politico.com/rss/politico.xml"),
        ("BBC Africa", "http://feeds.bbci.co.uk/news/world/africa/rss.xml"),
        ("BBC Asia", "http://feeds.bbci.co.uk/news/world/asia/rss.xml"),
        ("BBC Europe", "http://feeds.bbci.co.uk/news/world/europe/rss.xml"),
        ("BBC Latin America", "http://feeds.bbci.co.uk/news/world/latin_america/rss.xml"),
        ("BBC Middle East", "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
        ("BBC US Canada", "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
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
                    score = sum(
                        1 for k in _geopower_keywords if k in title.lower()
                    )
                    if score < 1 and org not in {
                        "Reuters World", "AP News", "UN News", "NPR World",
                        "Al Jazeera", "BBC World", "France24", "Middle East Eye",
                        "Egypt Independent", "South China Morning Post",
                        "Japan Times", "India Times", "Foreign Affairs", "CSIS",
                        "Crisis Group", "Atlantic Council", "IISS", "Eurasia Group",
                        "Stratfor", "The Diplomat", "Fox News World", "Russia Today",
                        "Times of Israel", "Haaretz", "Jerusalem Post", "Korea Herald",
                        "Straits Times", "Nikkei Asia", "Reuters Asia", "UNCTAD",
                        "Asharq", "Arab News", "Guardian World", "DW News",
                        "CNBC World", "CNN World", "ABC World", "CBS News",
                        "NBC News", "Politico",
                        "BBC Africa", "BBC Asia", "BBC Europe", "BBC Latin America",
                        "BBC Middle East", "BBC US Canada",
                    }:
                        continue
                    if score == 0:
                        score = 1  # ensure headline global-news items survive
                    items.append(
                        {
                            "category": self.category,
                            "timestamp": self._fmt(pub),
                            "headline": self._trunc(title, 170),
                            "bullet_points": [
                                self._trunc(f"Geopower: {org} — world, conflict, policy", 120)
                            ],
                            "source": org,
                            "confidence": min(96, 78 + score * 4),
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


_geopower_keywords = [
    "sanctions", "treaty", "war", "conflict", "oil", "energy", "trade war",
    "summit", "nuclear", "tariff", "diplomat", "agreement", "un security council",
    "military", "defense", "border", "election", "coup", "alliance", "nato",
    "opec", "gas", "lithium", "copper", "supply chain", "strait", "missile",
    "iran", "ukraine", "russia", "china", "taiwan", "israel", "lebanon",
    "hormuz", "pentagon", "white house", "congress", "brexit", "europe",
    "asia", "africa", "latin america", "middle east", "biden", "trump",
    "president", "prime minister", "putin", "xi", "modi", "south china sea",
    "tibet", "xinjiang", "genocide", "sanctioned", "blacklist",
]
