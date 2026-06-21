#!/usr/bin/env python3
"""AlphaIntel production-ready dashboard updater.

Fetches from public no-auth sources, validates against the dashboard schema,
writes data.json with backup rotation, and logs structured output.

Exit codes:
  0  Success
  1  Partial failure (some sources failed, but data was written)
  2  Total failure (no data written)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

OUTPUT = Path(__file__).with_name("data.json")
BACKUP_DIR = Path(__file__).with_name("backups")
MAX_BACKUPS = 5

LOG_FMT = "%(asctime)s %(levelname)-7s %(message)s"
LOG_DT_FMT = "%Y-%m-%d %H:%M:%S"

REQUIRED_FIELDS = {"category", "timestamp", "headline", "bullet_points", "source", "confidence"}
VALID_CATEGORIES = {"finance", "security", "trends"}

HEADERS = {
    "User-Agent": "AlphaIntelBot/1.0 (+nichaas-dashboard; contact: bodea.mircea@gmail.com)",
    "Accept": "application/json, application/rss+xml, text/xml, */*",
}

TIMEOUT = 20

logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DT_FMT, stream=sys.stdout)
log = logging.getLogger("alphaintel")


class AlphaIntelError(Exception):
    pass


# ------------------------------------------------------------------
# HTTP helpers
# ------------------------------------------------------------------
def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def fetch_json(url: str):
    return json.loads(fetch(url))


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------
def validate_item(item: dict, index: int) -> None:
    if not isinstance(item, dict):
        raise AlphaIntelError(f"Item {index} is not an object")
    missing = REQUIRED_FIELDS - item.keys()
    if missing:
        raise AlphaIntelError(f"Item {index} missing fields: {', '.join(sorted(missing))}")
    if item["category"] not in VALID_CATEGORIES:
        raise AlphaIntelError(f"Item {index} invalid category: {item['category']}")
    if not isinstance(item["confidence"], (int, float)) or not (0 <= item["confidence"] <= 100):
        raise AlphaIntelError(f"Item {index} confidence out of range: {item['confidence']}")
    if not isinstance(item["bullet_points"], list):
        raise AlphaIntelError(f"Item {index} bullet_points must be array")
    if not isinstance(item["headline"], str) or not item["headline"].strip():
        raise AlphaIntelError(f"Item {index} headline empty")


def validate_stream(stream: list[dict]) -> None:
    for idx, item in enumerate(stream):
        validate_item(item, idx)


# ------------------------------------------------------------------
# Sources
# ------------------------------------------------------------------
def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _fmt(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M UTC")


def _trunc(text: str, n: int = 180) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


import re as _re


def _strip_html(text: str) -> str:
    text = _re.sub(r"<[^>]+>", " ", text)
    return _re.sub(r"\s+", " ", text).strip()


def build_security() -> list[dict]:
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    data = fetch_json(url)
    vulns = data.get("vulnerabilities", [])
    out: list[dict] = []
    for v in vulns[:5]:
        cve = v.get("cveID", "unknown CVE")
        vendor = v.get("vendorProject", "Unknown vendor")
        product = v.get("product", "Unknown product")
        due = v.get("dueDate", "TBD")
        name = v.get("vulnerabilityName", "Exploitation confirmed active.")
        out.append(
            {
                "category": "security",
                "timestamp": _fmt(_now()),
                "headline": _trunc(f"CISA adds {cve} ({vendor} {product}) to KEV catalog"),
                "bullet_points": [
                    _trunc(f"Federal agencies must remediate by {due}.", 120),
                    _trunc(name, 120),
                ],
                "source": "CISA KEV",
                "confidence": 98,
            }
        )
    return out


def build_finance() -> list[dict]:
    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        "?action=getcurrent&type=8-K&dateb=&owner=include&count=10&output=atom"
    )
    xml = fetch(url).decode("utf-8", errors="replace")
    entries = _re.findall(r"<entry>(.*?)</entry>", xml, _re.S)
    out: list[dict] = []
    for raw in entries[:6]:
        tm = _re.search(r"<title[^>]*>(.*?)</title>", raw, _re.S)
        title = _strip_html(tm.group(1)) if tm else "SEC 8-K filing"
        um = _re.search(r"<updated[^>]*>(.*?)</updated>", raw, _re.S)
        updated = _strip_html(um.group(1)) if um else _fmt(_now())
        out.append(
            {
                "category": "finance",
                "timestamp": updated,
                "headline": _trunc(title, 160),
                "bullet_points": ["Latest SEC 8-K disclosure detected from EDGAR current filings."],
                "source": "SEC EDGAR",
                "confidence": 91,
            }
        )
    return out


def build_trends() -> list[dict]:
    url = "https://hnrss.org/frontpage"
    xml = fetch(url).decode("utf-8", errors="replace")
    entries = _re.findall(r"<item>(.*?)</item>", xml, _re.S)
    out: list[dict] = []
    for raw in entries[:10]:
        tm = _re.search(
            r"<title[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</title>",
            raw,
            _re.S,
        )
        title = ""
        if tm:
            title = next(g for g in tm.groups() if g is not None)
        title = title.strip() or "Hacker News story"
        lm = _re.search(r"<link[^>]*>(.*?)</link>", raw, _re.S)
        link = _strip_html(lm.group(1)) if lm else ""
        out.append(
            {
                "category": "trends",
                "timestamp": _fmt(_now()),
                "headline": _trunc(title, 160),
                "bullet_points": [_trunc(f"Source: {link}", 120)] if link else [],
                "source": "Hacker News",
                "confidence": 78,
            }
        )
    return out


# ------------------------------------------------------------------
# Backup / write
# ------------------------------------------------------------------
def _rotate_backups() -> None:
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("data-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[MAX_BACKUPS:]:
        try:
            old.unlink()
            log.info("Rotated old backup: %s", old.name)
        except OSError as exc:
            log.warning("Backup rotation failed for %s: %s", old.name, exc)


def backup_current() -> Path | None:
    if not OUTPUT.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"data-{stamp}.json"
    shutil.copy2(OUTPUT, dest)
    _rotate_backups()
    log.info("Backed up current data.json -> %s", dest.name)
    return dest


def write_output(stream: list[dict], dest: Path) -> None:
    dest.write_text(json.dumps({"intel_stream": stream}, indent=2) + "\n", encoding="utf-8")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def build_stream() -> tuple[list[dict], list[str]]:
    stream: list[dict] = []
    errors: list[str] = []
    for builder in (build_security, build_finance, build_trends):
        name = builder.__name__
        try:
            items = builder()
            log.info("Source %s produced %d items", name, len(items))
            stream.extend(items)
        except Exception as exc:  # noqa: BLE001
            msg = f"{name}: {exc}"
            errors.append(msg)
            log.error("Source %s failed: %s", name, exc)
    return stream, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="AlphaIntel production updater")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default=str(OUTPUT))
    args = parser.parse_args()

    stream, errors = build_stream()

    if not stream:
        log.error("All sources failed: %s", "; ".join(errors))
        return 2

    try:
        validate_stream(stream)
        log.info("Schema validation passed for %d items", len(stream))
    except AlphaIntelError as exc:
        log.error("Schema validation failed: %s", exc)
        return 2

    dest = Path(args.output)

    if not args.dry_run:
        backup_current()
        write_output(stream, dest)
        log.info("Wrote %d items -> %s", len(stream), dest)

    if errors:
        log.warning("Completed with partial failures: %s", "; ".join(errors))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
