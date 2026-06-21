import datetime as dt
import re
import urllib.request
from .base import BaseSource, SourceResult

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
        ("InfoSecurity", "https://www.infosecurity-magazine.com/rss"),
        ("Cyware", "https://cyware.com/rss"),
        ("Security Affairs", "https://securityaffairs.co/feed"),
        ("The Register", "https://www.theregister.com/security/headlines.atom"),
        ("Mandiant", "https://www.mandiant.com/resources/blog/rss.xml"),
        ("Rapid7", "https://blog.rapid7.com/rss/"),
        ("Qualys", "https://blog.qualys.com/rss"),
        ("Sumo Logic", "https://www.sumologic.com/blog/feed/"),
        ("Splunk", "https://www.splunk.com/en_us/blog/rss.xml"),
        ("Elastic Security", "https://www.elastic.co/blog/rss.xml"),
        ("Netwitness", "https://www.netwitness.com/blog/feed/"),
        ("Microsoft Security", "https://www.microsoft.com/security/blog/feed/"),
        ("Google Blog", "https://blog.google/rss/"),
        ("NCC Group", "https://www.nccgroup.com/us/blog/feed/"),
        ("Tenable", "https://www.tenable.com/blog/rss"),
        ("Flashpoint", "https://flashpoint.io/blog/feed/"),
        ("Silent Breach", "https://silentbreach.com/blog/feed/"),
        ("Recorded Future", "https://www.recordedfuture.com/blog/feed/"),
        ("CSO Online", "https://www.csoonline.com/feed/"),
        ("CSO Australia", "https://www.csoonline.com.au/feed/"),
        ("CSO UK", "https://www.csoonline.com/uk/feed/"),
        ("Tripwire", "https://www.tripwire.com/state-of-security/feed/"),
        ("Apple Security", "https://support.apple.com/rss"),
        ("FireEye Threat", "https://www.mandiant.com/resources/blog/rss.xml"),
        ("Snyk Blog", "https://snyk.io/blog/feed/"),
        ("ZDNet Tech", "https://www.zdnet.com/news/rss.xml"),
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
                                self._trunc(f"Security: {org} — threat intel, breaches, vulns", 120)
                            ],
                            "source": org,
                            "confidence": _security_conf(title),
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
