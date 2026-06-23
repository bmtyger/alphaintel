import datetime as dt
import logging
import re
from .rss_helpers import _fmt, _parse_dt, _text, _trunc
from .base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

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
        fetch_errors: list[str] = []
        for org, url in self.feeds:
            try:
                xml = self._request("GET", url, headers=UA)[0].decode(
                    "utf-8", errors="replace"
                )
                for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:6]:
                    title = _text(
                        raw,
                        r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>",
                    )
                    pub = _text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                    link = _text(raw, r"<link[^>]*>(.*?)</link>")
                    if not title:
                        continue
                    key = title.strip().lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    when = _parse_dt(pub)
                    if when and when < cutoff:
                        continue
                    items.append(
                        {
                            "category": self.category,
                            "timestamp": _fmt(pub),
                            "headline": _trunc(title, 170),
                            "bullet_points": [
                                _trunc(f"Tech: {org} — AI, gadgets, software", 120)
                            ],
                            "source": org,
                            "url": link,
                        }
                    )
            except Exception as exc:
                msg = f"tech feed failed [{org}] {url}: {exc}"
                fetch_errors.append(msg)
                logger.warning(msg)
        conf_errors: list[str] = []
        confidence_map: dict[str, int] = {}
        for item in items:
            try:
                confidence_map[item["url"]] = _tech_conf(item["headline"])
            except Exception as exc:
                conf_errors.append(f"confidence failed [{self.name}] {item['url']}: {exc}")
        for item in items:
            if item["url"] in confidence_map:
                item["confidence"] = confidence_map[item["url"]]
        combined = fetch_errors + conf_errors
        error = "; ".join(combined) if combined else None
        success = not combined and (not fetch_errors or bool(items))
        return SourceResult(items=items, source_name=self.name, category=self.category, success=success, error=error)


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
