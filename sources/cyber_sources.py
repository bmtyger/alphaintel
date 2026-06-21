import re
import urllib.request
import json as _json
from .base import BaseSource, SourceResult

UA = {"User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)"}


class CisaKevSource(BaseSource):
    name = "cisa_kev"
    category = "security"

    def fetch(self) -> SourceResult:
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        data = _json.loads(self._request("GET", url, headers=UA)[0])
        vulns = data.get("vulnerabilities", [])
        items = []
        for v in vulns[:8]:
            cve = v.get("cveID", "CVE-unknown")
            vendor = v.get("vendorProject", "Unknown")
            product = v.get("product", "product")
            due = v.get("dueDate", "TBD")
            name = v.get("vulnerabilityName", "Active exploitation confirmed")
            items.append({
                "category": self.category,
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "headline": self._trunc(f"CISA KEV: {cve} ({vendor} {product})"),
                "bullet_points": [
                    self._trunc(f"Agency remediation deadline: {due}", 120),
                    self._trunc(name, 120),
                ],
                "source": "CISA KEV",
                "confidence": 98,
                "cves": [cve],
            })
        return SourceResult(items=items, source_name=self.name, category=self.category)

    @staticmethod
    def _trunc(text, n=180):
        t = text.strip()
        return t if len(t) <= n else t[: n-1].rstrip() + "…"


class NvdSource(BaseSource):
    name = "nvd_api"
    category = "security"

    def fetch(self) -> SourceResult:
        # NVD NIST API 2.0 — additional headers for rate limit etiquette
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=10&startIndex=0"
        headers = {
            "User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)",
            "Accept": "application/json",
        }
        data = _json.loads(self._request("GET", url, headers=headers)[0])
        vulns = data.get("vulnerabilities", [])
        items = []
        for v in vulns[:8]:
            cve = v.get("cve", {}).get("id", "CVE-unknown")
            desc = ""
            descs = v.get("cve", {}).get("descriptions", [])
            for d in descs:
                if d.get("lang") == "en":
                    desc = d.get("value", "").strip()
                    break
            severity = ""
            metrics = v.get("cve", {}).get("metrics", {})
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if key in metrics:
                    severity = metrics[key][0].get("cvssData", {}).get("baseSeverity", "")
                    break
            conf = 92 if severity.upper() in {"HIGH", "CRITICAL"} else 84
            items.append({
                "category": self.category,
                "timestamp": v.get("cve", {}).get("published", "").replace("T", " ").replace("Z", " UTC"),
                "headline": self._trunc(f"NVD: {cve} ({severity})"),
                "bullet_points": [self._trunc(desc or "No description", 120)],
                "source": "NVD",
                "confidence": conf,
                "cves": [cve],
            })
        return SourceResult(items=items, source_name=self.name, category=self.category)

    @staticmethod
    def _trunc(text, n=180):
        t = text.strip()
        return t if len(t) <= n else t[: n-1].rstrip() + "…"
