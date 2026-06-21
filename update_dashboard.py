#!/usr/bin/env python3
"""AlphaIntel dashboard updater.

Generates structured intel items for the dashboard and writes them to
data.json.  Designed to be replaced or extended with real scraping
logic later.

Usage:
  python update_dashboard.py          # refresh data.json with generated items
  python update_dashboard.py --dry-run   # print to stdout only
  python update_dashboard.py --count 10  # generate N items instead of default 6
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_COUNT = 6

CATEGORIES = ["finance", "security", "trends"]

SOURCES = {
    "finance": ["BloombergNEF", "Reuters", "FT", "CoinDesk", "SEC docket"],
    "security": ["CISA", "BleepingComputer", "KrebsOnSecurity", "Snyk", "Rapid7"],
    "trends": ["SemiAnalysis", "The Information", "Stratechery", "ArsTechnica", "The Verge"],
}

HEADLINES = {
    "finance": [
        "Global markets reprice AI capex as efficiency gains outpace compute spend",
        "New ETF structure bundles sovereign AI-chip supply-chain equities",
        "Treasury issues guidance on tokenized carbon/commodity settlement rails",
        "MiCA implementation pushes 40+ stablecoin issuers into EU licensing queue",
        "Dark-pool surveillance rules tighten after unexplained volatility cluster",
    ],
    "security": [
        "Major CI/CD pipeline platform discloses supply-chain injection path",
        "3 popular MLOps stacks ship hardcoded keys in default configs",
        "APT group targets fintech APIs with novel semantic-parsing phishing",
        "Enterprise VPN zero-click chain extended to 5 additional vendors",
        "Zero-trust vendor consolidation drives 2 M&A deals above $300M",
    ],
    "trends": [
        "Open-weight models hit parity on legal reasoning benchmarks",
        "Robotics simulation frameworks converge on MuJoCo-compatible interchange",
        "Autonomous dev-loop agent reduces 10k-line PR review to 12 minutes",
        "Edge model compression breakthrough enables on-device multi-modal agents",
        "WebAssembly runtime becomes default target for portable AI toolchains",
    ],
}

BULLETS_TEMPLATES = {
    "finance": [
        "Regulator signals intent to require quarterly model-risk attestations for algorithmic trading desks.",
        "Institutional investors open first tokenized commodity futures positions.",
        "Capital-markets infra vendors report 3x YoY demand for AI audit tooling.",
    ],
    "security": [
        "Patch management windows shrink to 48h for actively exploited CVEs.",
        "Zero-trust adoption slows due to identity-provider scaling constraints.",
        "Threat-intel sharing consortia double membership in H1.",
    ],
    "trends": [
        "Developer survey shows 60% of new projects ship with embedded AI co-pilots.",
        "Open-source hardware ecosystem reaches 20k reproducible designs milestone.",
        "Edge deployment cost drops 40% YoY as quantization matures.",
    ],
}


def rand_item(base: list[str]) -> str:
    return random.choice(base)


def generate_item(now: datetime) -> dict:
    category = rand_item(CATEGORIES)
    source = rand_item(SOURCES[category])
    headline = rand_item(HEADLINES[category])
    bullets = random.sample(BULLETS_TEMPLATES[category], k=random.randint(2, 3))
    confidence = random.randint(82, 99)

    ts = now - timedelta(minutes=random.randint(0, 180))
    timestamp = ts.strftime("%Y-%m-%d %H:%M UTC")

    return {
        "category": category,
        "timestamp": timestamp,
        "headline": headline,
        "bullet_points": bullets,
        "source": source,
        "confidence": confidence,
    }


def build_stream(count: int) -> list[dict]:
    now = datetime.utcnow()
    return [generate_item(now) for _ in range(count)]


def write_json(stream: list[dict], dest: Path) -> None:
    payload = {"intel_stream": stream}
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="AlphaIntel dashboard updater")
    parser.add_argument("--dry-run", action="store_true", help="print JSON instead of writing file")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="number of items to generate")
    parser.add_argument("--output", type=str, default=str(Path(__file__).with_name("data.json")))
    args = parser.parse_args()

    stream = build_stream(args.count)
    payload = {"intel_stream": stream}

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    dest = Path(args.output)
    write_json(stream, dest)
    print(f"Wrote {len(stream)} items -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
