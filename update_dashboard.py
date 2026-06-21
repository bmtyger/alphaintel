#!/usr/bin/env python3
"""AlphaIntel production updater — multi-source engine.

Uses the sources registry + PipelineEngine for fetching, enrichment,
validation, deduplication, and backup.  Falls back to synthetic random
items if the engine returns an empty stream (so the dashboard never blanks).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import shutil
import sys
from pathlib import Path

from sources.engine import PipelineEngine
from sources.signals import enrich_item

OUTPUT = Path(__file__).with_name("data.json")
BACKUP_DIR = Path(__file__).with_name("backups")
MAX_BACKUPS = 5

LOG_FMT = "%(asctime)s %(levelname)-7s %(message)s"
LOG_DT_FMT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DT_FMT, stream=sys.stdout)
log = logging.getLogger("alphaintel")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _fmt(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M UTC")


def _rotate_backups() -> None:
    if not BACKUP_DIR.exists():
        return
    backups = sorted(
        BACKUP_DIR.glob("data-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
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


def build_stream(categories: list[str] | None = None, max_items: int = 50) -> tuple[list[dict], list[str]]:
    engine = PipelineEngine(categories=categories)
    payload = engine.run()
    raw = payload.get("intel_stream", [])
    errors = payload.get("errors", [])

    # Schema validation
    problems = PipelineEngine.validate_schema(raw)
    if problems:
        for p in problems[:10]:
            log.error("Schema: %s", p)
        if not raw:
            log.error("Schema validation failed — empty stream")
            return [], errors + ["schema_validation_failed"]

    # Trim to max_items (high-impact first)
    stream = raw[:max_items]

    # Fallback: if engine produced nothing, inject a synthetic item so dashboard isn't blank
    if not stream:
        log.warning("Engine returned empty stream — injecting fallback items")
        stream = [
            {
                "category": cat,
                "timestamp": _fmt(_now()),
                "headline": f"{cat.title()} feed active. Sources connecting.",
                "bullet_points": ["Live intelligence loading.", "Check back shortly for curated signals."],
                "source": "AlphaIntel System",
                "confidence": 70,
            }
            for cat in (categories or ["finance", "security", "trends", "geopower"])
        ]
    return stream, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="AlphaIntel production updater (engine)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default=str(OUTPUT))
    parser.add_argument("--category", action="append", choices=["finance", "security", "trends", "geopower"])
    parser.add_argument("--max-items", type=int, default=50)
    args = parser.parse_args()

    categories = args.category or None
    stream, errors = build_stream(categories=categories, max_items=args.max_items)

    if args.dry_run:
        print(json.dumps({"intel_stream": stream}, indent=2))
        return 0

    dest = Path(args.output)
    backup_current()
    write_output(stream, dest)
    count = len(stream)
    log.info("Wrote %d items -> %s", count, dest)

    if errors:
        log.warning("Completed with partial failures: %s", "; ".join(errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
