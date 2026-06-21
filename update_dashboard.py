#!/usr/bin/env python3
"""AlphaIntel real-data updater.

Fetches from public, no-auth sources:
- CISA Known Exploited Vulnerabilities catalog -> security items
- SEC EDGAR filings feed -> finance/regulatory items
- Hacker News top stories -> trends items

Outputs dashboard data.json in the same directory.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

OUTPUT = Path(__file__).with_name("data.json")

HEADERS = {
    "User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}

TIMEOUT = 20


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def fetch_json(url: str) -> dict | list:
    return json.loads(fetch(url))


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, n: int = 180) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def format_ts(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M UTC")


# ------------------------------------------------------------------
# Sources
# ------------------------------------------------------------------
def build_security_items() -> list[dict]:
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    data = fetch_json(url)
    vulnerabilities = data.get("vulnerabilities", [])
    items: list[dict] = []
    for vuln in vulnerabilities[:5]:
        cve = vuln.get("cveID", "unknown CVE")
        vendor = vuln.get("vendorProject", "Unknown vendor")
        product = vuln.get("product", "Unknown product")
        due = vuln.get("dueDate", "")
        headline = f"CISA adds {cve} ({vendor} {product}) to Known Exploited Vulnerabilities catalog"
        bullets = [
            f"Federal agencies must remediate by {due}.",
            vuln.get("vulnerabilityName", "Exploitation confirmed active."),
        ]
        items.append(
            {
                "category": "security",
                "timestamp": format_ts(now_utc()),
                "headline": truncate(headline, 160),
                "bullet_points": [truncate(b, 120) for b in bullets],
                "source": "CISA KEV",
                "confidence": 98,
            }
        )
    return items


def build_finance_items() -> list[dict]:
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=10&output=atom"
    xml = fetch(url).decode("utf-8", errors="replace")
    # Super-simple atom-ish parser
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
    items: list[dict] = []
    for raw in entries[:6]:
        title_m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S)
        title = strip_html(title_m.group(1)) if title_m else "SEC 8-K filing"
        updated_m = re.search(r"<updated[^>]*>(.*?)</updated>", raw, re.S)
        updated = strip_html(updated_m.group(1)) if updated_m else format_ts(now_utc())
        items.append(
            {
                "category": "finance",
                "timestamp": updated,
                "headline": truncate(title, 160),
                "bullet_points": [
                    "Latest SEC 8-K disclosure detected from EDGAR current filings."
                ],
                "source": "SEC EDGAR",
                "confidence": 91,
            }
        )
    return items


def build_trends_items() -> list[dict]:
    url = "https://hnrss.org/frontpage"
    xml = fetch(url).decode("utf-8", errors="replace")
    entries = re.findall(r"<item>(.*?)</item>", xml, re.S)
    items: list[dict] = []
    for raw in entries[:10]:
        title_m = re.search(r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>", raw, re.S)
        title = ""
        if title_m:
            title = next(g for g in title_m.groups() if g is not None)
        title = title.strip()
        if not title:
            title = "Hacker News story"
        link_m = re.search(r"<link[^>]*>(.*?)</link>", raw, re.S)
        link = strip_html(link_m.group(1)) if link_m else ""
        items.append(
            {
                "category": "trends",
                "timestamp": format_ts(now_utc()),
                "headline": truncate(title, 160),
                "bullet_points": [truncate(f"Source: {link}", 120)] if link else [],
                "source": "Hacker News",
                "confidence": 78,
            }
        )
    return items


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def build_stream() -> list[dict]:
    stream: list[dict] = []
    errors: list[str] = []

    for builder in (build_security_items, build_finance_items, build_trends_items):
        try:
            stream.extend(builder())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{builder.__name__}: {exc}")

    if not stream:
        raise RuntimeError("All sources failed: " + "; ".join(errors))

    return stream


def write_output(stream: list[dict], dest: Path) -> None:
    payload = {"intel_stream": stream}
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="AlphaIntel real-data dashboard updater")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default=str(OUTPUT))
    args = parser.parse_args()

    stream = build_stream()

    if args.dry_run:
        print(json.dumps({"intel_stream": stream}, indent=2))
        return 0

    write_output(stream, Path(args.output))
    print(f"Wrote {len(stream)} items -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
