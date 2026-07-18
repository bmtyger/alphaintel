import re
import urllib.request
from .base import BaseSource, SourceResult

HEADERS = {
    "User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)",
    "Accept": "application/atom+xml, application/xml, text/xml, */*",
}


class SecEdgarSource(BaseSource):
    name = "sec_edgar"
    category = "finance"

    def fetch(self) -> SourceResult:
        items: list[dict] = []
        seen_titles = set()
        for feed_url in [
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=15&output=atom",
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=10&output=atom",
        ]:
            try:
                data = self._request("GET", feed_url, headers=HEADERS)[0].decode("utf-8", errors="replace")
                entries = re.findall(r"<entry>(.*?)</entry>", data, re.S)
                for raw in entries[:8]:
                    title = self._text(raw, r"<title[^>]*>(.*?)</title>")
                    updated = self._text(raw, r"<updated[^>]*>(.*?)</updated>")
                    link_m = re.search(r"<link[^>]+href=\"([^\"]+)\"", raw)
                    link = link_m.group(1) if link_m else ""
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)
                    tickers = self._extract_tickers(title + " " + self._text(raw, r"<summary[^>]*>(.*?)</summary>"))
                    items.append({
                        "category": self.category,
                        "timestamp": self._clean_ts(updated),
                        "headline": self._trunc(title, 160),
                        "bullet_points": [
                            f"SEC filing: {tickers[0] if tickers else 'Entity'}",
                            f"Source: EDGAR ({feed_url.split('type=')[1].split('&')[0]})",
                        ],
                        "source": "SEC EDGAR",
                        "confidence": 90 if tickers else 82,
                        "tickers": tickers,
                        "url": link,
                    })
            except Exception as exc:
                # don't abort whole pipeline
                pass
        return SourceResult(items=items, source_name=self.name, category=self.category)

    @staticmethod
    def _text(text, pattern):
        m = re.search(pattern, text, re.S)
        return SecEdgarSource._strip(m.group(1)) if m else ""

    @staticmethod
    def _strip(text):
        return re.sub(r"<[^>]+>", " ", text).strip()

    @staticmethod
    def _trunc(text, n=180):
        t = text.strip()
        return t if len(t) <= n else t[: n-1].rstrip() + "…"

    @staticmethod
    def _clean_ts(raw):
        raw = raw.strip()
        if raw and not raw.endswith("Z"):
            raw += "Z"
        try:
            dt = __import__("datetime").datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return raw or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def _extract_tickers(text):
        text = text.upper()
        tickers = set()
        for m in re.finditer(r"\b([A-Z]{2,5})\b", text):
            t = m.group(1)
            if t in {"SEC", "EDGAR", "FORM", "ITEM", "EXHIBIT", "COMPANY", "INC", "CORP", "LLC", "THE", "AND"}:
                continue
            tickers.add(t)
        return sorted(tickers)[:6]
