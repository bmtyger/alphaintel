import datetime as dt
import re
import urllib.request
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}
_CUTOFF_DAYS = 30


class FinanceRssSource(BaseSource):
    name = "finance_rss"
    category = "finance"
    feeds = [
        ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("FT", "http://www.ft.com/rss/home"),
        ("Economist Finance", "https://www.economist.com/finance-and-economics/rss.xml"),
        ("Bloomberg", "https://feeds.bloomberg.com/business/news.rss"),
        ("Bank of England", "https://www.bankofengland.co.uk/rss/news"),
        ("Chainalysis", "https://blog.chainalysis.com/rss/"),
        ("Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
        ("Livemint", "https://www.livemint.com/rss/markets"),
        ("Investors.com", "https://www.investors.com/feed/"),
        ("Kiplingers", "https://www.kiplinger.com/feed/rss"),
        ("NerdWallet", "https://www.nerdwallet.com/blog/feed/"),
        ("Fortune", "https://fortune.com/feed/"),
        ("Benzinga", "https://www.benzinga.com/feed"),
        ("Moodys", "https://www.moodys.com/research/rss"),
        ("Fitch", "https://www.fitchratings.com/rss"),
        ("DBRS", "https://www.dbrs.com/rss"),
        ("Dealogic", "https://www.dealogic.com/feed/"),
        ("S&amp;P Global", "https://www.spglobal.com/feed/"),
        ("Business Insider", "https://www.businessinsider.com/rss"),
        ("CryptoSlate", "https://cryptoslate.com/feed/"),
        ("Mastercard News", "https://newsroom.mastercard.com/feed/"),
        ("Visa Blog", "https://usa.visa.com/visa-ethereum-blog/rss.xml"),
        ("Stripe Blog", "https://stripe.com/blog/rss"),
        ("PayPal News", "https://www.paypal.com/us/webapps/mpp/merchant/rss"),
        ("Adyen Blog", "https://www.adyen.com/blog/rss.xml"),
        ("Kaiko", "https://blog.kaiko.com/feed"),
        ("CoinGecko", "https://www.coingecko.com/en/news/feed/rss"),
        ("The Block", "https://www.theblock.co/rss.xml"),
        ("Federal Register CFTC", "https://www.federalregister.gov/rss/agencies/commodity-futures-trading-commission"),
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
                    tickers = _extract_tickers(title)
                    items.append(
                        {
                            "category": self.category,
                            "timestamp": self._fmt(pub),
                            "headline": self._trunc(title, 170),
                            "bullet_points": [
                                self._trunc(
                                    f"Finance: {org} — market updates, crypto, macro"
                                , 120)
                            ],
                            "source": org,
                            "confidence": _finance_conf(title),
                            "url": link,
                            "tickers": tickers[:6],
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


def _finance_conf(text: str) -> int:
    low = text.lower()
    score = 75
    if any(w in low for w in
           ("market", "stock", "bond", "rate", "fed", "ecb", "bank",
            "gdp", "inflation", "earnings", "ipo", "merger", "acquisition",
            "crypto", "bitcoin", "ethereum", "blockchain", "tariff",
            "trade", "recession", "bull", "bear", "volatility")):
        score += 10
    if any(w in low for w in
           ("breaking", "alert", "exclusive", "just in")):
        score += 8
    return min(96, score)


def _extract_tickers(text: str):
    text = text.upper()
    tickers = set()
    for m in re.finditer(r"\b([A-Z]{1,5})\b", text):
        t = m.group(1)
        if t in {
            "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "WILL",
            "NOT", "HAVE", "WERE", "COMPANY", "INC", "CORP", "LLC",
            "SEC", "USD", "EUR", "GBP", "JPY", "CNY", "NEWS", "MARKET",
            "FINANCE", "BLOG", "REPORT", "DATA", "TIME", "YEAR",
        }:
            continue
        tickers.add(t)
    return sorted(tickers)[:6]
