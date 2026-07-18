import re
import urllib.request
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}


class RssMarketSource(BaseSource):
    name = "yahoo_finance"
    category = "finance"
    url = "https://finance.yahoo.com/news/rssindex"

    def fetch(self) -> SourceResult:
        return self._parse_rss()

    def _parse_rss(self) -> SourceResult:
        xml = self._request("GET", self.url, headers=UA)[0].decode("utf-8", errors="replace")
        items = []
        for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:8]:
            title = self._text(raw, r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>")
            pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
            link = self._text(raw, r"<link[^>]*>(.*?)</link>")
            items.append({
                "category": self.category,
                "timestamp": self._fmt(pub),
                "headline": self._trunc(title, 170),
                "bullet_points": [self._trunc(f"Source: {link}", 120)] if link else [],
                "source": "Yahoo Finance",
                "confidence": 85,
                "url": link,
            })
        return SourceResult(items=items, source_name=self.name, category=self.category)

    @staticmethod
    def _text(text, pattern):
        m = re.search(pattern, text, re.S)
        if not m:
            return ""
        return next(g for g in m.groups() if g is not None).strip()

    @staticmethod
    def _fmt(raw):
        raw = raw.strip()
        if not raw:
            return __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        # Convert RFC 2822 to our format roughly
        try:
            import email.utils
            t = email.utils.parsedate_to_datetime(raw)
            return t.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return raw

    @staticmethod
    def _trunc(text, n=180):
        t = text.strip()
        return t if len(t) <= n else t[: n-1].rstrip() + "…"


class FedEcxBisSource(BaseSource):
    name = "central_banks"
    category = "finance"

    def fetch(self) -> SourceResult:
        feeds = [
            ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
            ("ECB", "https://www.ecb.europa.eu/rss/press/rss_ecb_content.html"),
            ("BIS", "https://www.bis.org/rss/rss_news.xml"),
        ]
        items: list[dict] = []
        for org, url in feeds:
            try:
                xml = self._request("GET", url, headers=UA)[0].decode("utf-8", errors="replace")
                for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:4]:
                    title = self._text(raw, r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>")
                    pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                    link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                    if not title:
                        continue
                    items.append({
                        "category": self.category,
                        "timestamp": self._fmt(pub),
                        "headline": self._trunc(f"{org}: {title}"),
                        "bullet_points": [self._trunc(f"Source: {org} press release", 120)],
                        "source": org,
                        "confidence": 94,
                        "url": link,
                    })
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
    def _fmt(raw):
        raw = raw.strip()
        if not raw:
            return __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        try:
            import email.utils
            t = email.utils.parsedate_to_datetime(raw)
            return t.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return raw

    @staticmethod
    def _trunc(text, n=180):
        t = text.strip()
        return t if len(t) <= n else t[: n-1].rstrip() + "…"
