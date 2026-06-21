import re
import urllib.request
import urllib.error
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}


class DarkPoolSource(BaseSource):
    name = "dark_pool"
    category = "finance"
    url = "https://www.cnbc.com/id/100003114/device/rss/rss.html"

    def fetch(self) -> SourceResult:
        items = []
        try:
            xml = self._request("GET", self.url, headers=UA)[0].decode(
                "utf-8", errors="replace"
            )
            for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:8]:
                title = self._text(
                    raw,
                    r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>",
                )
                link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                if not title:
                    continue
                tickers = self._extract_tickers(title)
                items.append(
                    {
                        "category": self.category,
                        "timestamp": self._fmt(pub),
                        "headline": self._trunc(
                            f"Market Flow: {title}", 170
                        ),
                        "bullet_points": [
                            self._trunc("Options / dark-pool flow signal from CNBC", 120)
                        ],
                        "source": "CNBC",
                        "confidence": 82,
                        "url": link,
                        "tickers": tickers,
                    }
                )
        except Exception:
            pass
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

    @staticmethod
    def _extract_tickers(text):
        text = text.upper()
        tickers = set()
        for m in re.finditer(r"\b([A-Z]{1,5})\b", text):
            t = m.group(1)
            if t in {
                "THE",
                "AND",
                "FOR",
                "WITH",
                "FROM",
                "THIS",
                "THAT",
                "WILL",
                "NOT",
                "HAVE",
                "WERE",
                "COMPANY",
                "INC",
                "CORP",
                "LLC",
                "SEC",
                "USD",
            }:
                continue
            tickers.add(t)
        return sorted(tickers)[:6]


class FinraShortInterestSource(BaseSource):
    name = "finra_short_interest"
    category = "finance"
    url = "https://www.investing.com/rss/news_25.rss"

    def fetch(self) -> SourceResult:
        items = []
        try:
            xml = self._request("GET", self.url, headers=UA)[0].decode(
                "utf-8", errors="replace"
            )
            for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:8]:
                title = self._text(
                    raw,
                    r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>",
                )
                link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                if not title:
                    continue
                tickers = self._extract_tickers(title)
                items.append(
                    {
                        "category": self.category,
                        "timestamp": self._fmt(pub),
                        "headline": self._trunc(f"Short Interest: {title}", 170),
                        "bullet_points": [
                            self._trunc(
                                "Short interest / bearish flow signal from Investing.com",
                                120,
                            )
                        ],
                        "source": "Investing.com",
                        "confidence": 83,
                        "url": link,
                        "tickers": tickers,
                    }
                )
        except Exception:
            pass
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

    @staticmethod
    def _extract_tickers(text):
        text = text.upper()
        tickers = set()
        for m in re.finditer(r"\b([A-Z]{1,5})\b", text):
            t = m.group(1)
            if t in {
                "THE",
                "AND",
                "FOR",
                "WITH",
                "FROM",
                "THIS",
                "THAT",
                "WILL",
                "NOT",
                "HAVE",
                "WERE",
                "COMPANY",
                "INC",
                "CORP",
                "LLC",
                "SEC",
                "USD",
            }:
                continue
            tickers.add(t)
        return sorted(tickers)[:6]


class CryptoOnchainSource(BaseSource):
    name = "crypto_onchain"
    category = "finance"
    feeds = [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Cointelegraph", "https://cointelegraph.com/rss"),
    ]

    def fetch(self) -> SourceResult:
        items = []
        seen = set()
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
                    link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                    pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                    if not title:
                        continue
                    key = title.strip().lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(
                        {
                            "category": self.category,
                            "timestamp": self._fmt(pub),
                            "headline": self._trunc(
                                f"On-chain: {title}", 170
                            ),
                            "bullet_points": [
                                self._trunc(
                                    "Crypto on-chain / whale flow signal",
                                    120,
                                )
                            ],
                            "source": org,
                            "confidence": 84,
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
