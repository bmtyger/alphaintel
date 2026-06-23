import datetime as dt
import logging
import re
from .rss_helpers import _fmt, _parse_dt, _text, _trunc
from .base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}
_CUTOFF_DAYS = 30


class SecurityRssSource(BaseSource):
    name = "security_rss"
    category = "security"
    feeds = [
        ("Dark Reading", "https://www.darkreading.com/rss.xml"),
        ("Help Net Security", "https://helpnetsecurity.com/feed/"),
        ("SecurityWeek", "https://www.securityweek.com/feed/"),
        ("ZDNet Security", "https://www.zdnet.com/topic/security/rss.xml"),
        ("CrowdStrike", "https://www.crowdstrike.com/blog/feed/"),
        ("Palo Alto Unit 42", "https://unit42.paloaltonetworks.com/feed/"),
        ("Graham Cluley", "https://www.grahamcluley.com/feed/"),
        ("Threatpost", "https://threatpost.com/feed/"),
        ("SC Magazine", "https://www.scmagazine.com/rss"),

        ("Security Affairs", "https://securityaffairs.co/feed"),

        ("Mandiant", "https://www.mandiant.com/resources/blog/rss.xml"),
        ("Rapid7", "https://blog.rapid7.com/rss/"),
        ("Sumo Logic", "https://www.sumologic.com/blog/feed/"),

        ("Netwitness", "https://www.netwitness.com/blog/feed/"),
        ("Microsoft Security", "https://www.microsoft.com/security/blog/feed/"),
        ("Google Blog", "https://blog.google/rss/"),

        ("Flashpoint", "https://flashpoint.io/blog/feed/"),

        ("CSO Online", "https://www.csoonline.com/feed/"),

        ("Snyk Blog", "https://snyk.io/blog/feed/"),
        ("ZDNet Tech", "https://www.zdnet.com/news/rss.xml"),
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
                                _trunc(f"Security: {org} — threat intel, breaches, vulns", 120)
                            ],
                            "source": org,
                            "url": link,
                        }
                    )
            except Exception as exc:
                msg = f"security feed failed [{org}] {url}: {exc}"
                fetch_errors.append(msg)
                logger.warning(msg)
        conf_errors: list[str] = []
        confidence_map: dict[str, int] = {}
        for item in items:
            try:
                confidence_map[item["url"]] = _security_conf(item["headline"])
            except Exception as exc:
                conf_errors.append(f"confidence failed [{self.name}] {item['url']}: {exc}")
        for item in items:
            if item["url"] in confidence_map:
                item["confidence"] = confidence_map[item["url"]]
        combined = fetch_errors + conf_errors
        error = "; ".join(combined) if combined else None
        success = not combined and (not fetch_errors or bool(items))
        return SourceResult(items=items, source_name=self.name, category=self.category, success=success, error=error)


def _security_conf(text: str) -> int:
    low = text.lower()
    score = 75
    if any(w in low for w in
           ("vulnerability", "exploit", "cve", "hack", "breach", "malware",
            "ransomware", "phishing", "apt", "zero-day", "patch", "security",
            "threat", "attack", "leak", "data", "privacy", "encryption",
            "firewall", "siem", "soc", "dfir", "forensic")):
        score += 12
    if any(w in low for w in
           ("critical", "severe", "urgent", "alert", "advisory",
            "botnet", "cisa", "kev")):
        score += 8
    return min(96, score)
