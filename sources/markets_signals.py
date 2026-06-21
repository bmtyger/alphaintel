import re
import urllib.request
import urllib.error
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}


class DarkPoolSource(BaseSource):
    name = "dark_pool"
    category = "finance"

    def fetch(self) -> SourceResult:
        items = []
        try:
            xml = self._request("GET", "https://www.wallstreetonwater.com/rss", headers=UA)[0].decode("utf-8", errors="replace")
            for raw in re.findall(r"<item>(.*?)</item>", xml, re.S)[:6]:
                title = self._text(raw, r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>")
                link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                if not title:
                    continue
                tickers = self._extract_tickers(title)
                items.append({
                    "category": self.category,
                    "timestamp": self._fmt(pub),
                    "headline": self._trunc(f"Dark Pool: {title}", 170),
                    "bullet_points": [self._trunc(f"Source: WallStOnWater", 120)],
                    "source": "WallStOnWater",
                    "confidence": 87,
                    "url": link,
                    "tickers": tickers,
                })
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

    @staticmethod
    def _extract_tickers(text):
        text = text.upper()
        tickers = set()
        for m in re.finditer(r"\b([A-Z]{1,5})\b", text):
            t = m.group(1)
            if t in {"THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "WILL", "NOT",
                     "HAVE", "WERE", "COMPANY", "INC", "CORP", "LLC", "SEC", "USD"}:
                continue
            tickers.add(t)
        return sorted(tickers)[:6]


class FinraShortInterestSource(BaseSource):
    name = "finra_short_interest"
    category = "finance"

    def fetch(self) -> SourceResult:
        items = []
        try:
            data = self._request("GET", "https://www.finra.org/rss-gateway/topics/shortinterest.rss", headers=UA)[0].decode("utf-8", errors="replace")
            for raw in re.findall(r"<item>(.*?)</item>", data, re.S)[:6]:
                title = self._text(raw, r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>")
                link = self._text(raw, r"<link[^>]*>(.*?)</link>")
                pub = self._text(raw, r"<pubDate[^>]*>(.*?)</pubDate>")
                if not title:
                    continue
                tickers = self._extract_tickers(title)
                items.append({
                    "category": self.category,
                    "timestamp": self._fmt(pub),
                    "headline": self._trunc(f"Short Interest: {title}", 170),
                    "bullet_points": [self._trunc("FINRA aggregated short interest report", 120)],
                    "source": "FINRA",
                    "confidence": 91,
                    "url": link,
                    "tickers": tickers,
                })
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

    @staticmethod
    def _extract_tickers(text):
        text = text.upper()
        tickers = set()
        for m in re.finditer(r"\b([A-Z]{1,5})\b", text):
            t = m.group(1)
            if t in {"THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "WILL", "NOT",
                     "HAVE", "WERE", "COMPANY", "INC", "CORP", "LLC", "SEC", "USD"}:
                continue
            tickers.add(t)
        return sorted(tickers)[:6]


class CryptoOnchainSource(BaseSource):
    name = "crypto_onchain"
    category = "finance"

    def fetch(self) -> SourceResult:
        items = []
        for feed, label in [
            ("https://api.whale-alert.io/v1/feed?limit=5", "Whale Alert"),
            ("https://www.blockchain.com/eth/rss", "Blockchain.com"),
        ]:
            try:
                raw = self._request("GET", feed, headers=UA)[0].decode("utf-8", errors="replace")
                if label == "Whale Alert":
                    import json
                    data = __import__("json").loads(raw)
                    for tx in data.get("transactions", [])[:4]:
                        txtype = tx.get("transaction_type", "transfer")
                        symbols = ", ".join(tx.get("symbols", [])) or "crypto"
                        amount = tx.get("amount", 0)
                        items.append({
                            "category": self.category,
                            "timestamp": self._fmt(tx.get("timestamp", "")),
                            "headline": self._trunc(f"Whale Alert: {amount:,.0f} {symbols} ({txtype})"),
                            "bullet_points": ["Large on-chain movement detected"],
                            "source": "Whale Alert",
                            "confidence": 89,
                            "url": "https://whale-alert.io",
                        })
                else:
                    for item in re.findall(r"<item>(.*?)</item>", raw, re.S)[:4]:
                        title = self._text(item, r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>")
                        link = self._text(item, r"<link[^>]*>(.*?)</link>")
                        pub = self._text(item, r"<pubDate[^>]*>(.*?)</pubDate>")
                        if not title:
                            continue
                        items.append({
                            "category": self.category,
                            "timestamp": self._fmt(pub),
                            "headline": self._trunc(f"On-chain: {title}", 170),
                            "bullet_points": ["Blockchain Mempool / Block feed"],
                            "source": "Blockchain.com",
                            "confidence": 84,
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
