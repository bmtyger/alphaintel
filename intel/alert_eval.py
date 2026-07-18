from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from intel.accounts import alert_rules, accounts
from intel.telegram import dispatch

logger = logging.getLogger(__name__)
DATA_PATH = Path(os.getenv("ALPHAINTEL_DATA_PATH", "data.json"))
COOLDOWN_MINUTES = 15
MAX_ALERTS_PER_RUN = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cooldown_ok(rule: Dict) -> bool:
    last = rule.get("last_triggered_at")
    if not last:
        return True
    try:
        then = datetime.fromisoformat(last)
        return (_now() - then).total_seconds() >= (COOLDOWN_MINUTES * 60)
    except Exception:
        return True


def _load_stream() -> List[Dict[str, Any]]:
    try:
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        items = raw.get("intel_stream") if isinstance(raw, dict) else raw
        return items if isinstance(items, list) else []
    except Exception as exc:
        logger.warning("Alert eval load failed: %s", exc)
        return []


def _matches_category(condition: Dict, item: Dict) -> bool:
    allowed = condition.get("categories")
    if not allowed:
        return True
    return item.get("category") in set(allowed)


def _matches_ticker(condition: Dict, item: Dict) -> bool:
    tickers = condition.get("tickers")
    if not tickers:
        return True
    found = {t.lower() for t in (item.get("tickers") or [])}
    return any(str(t).lower() in found for t in tickers)


def _matches_keywords(condition: Dict, item: Dict) -> bool:
    keywords = condition.get("keywords")
    if not keywords:
        return True
    haystack = " ".join(
        [
            item.get("headline") or "",
            *(item.get("bullet_points") or []),
        ]
    ).lower()
    return any(str(k).lower() in haystack for k in keywords)


def _satisfies_confidence(condition: Dict, item: Dict) -> bool:
    conf = condition.get("min_confidence")
    if conf is None:
        return True
    try:
        return (item.get("confidence") or 0) >= int(conf)
    except Exception:
        return True


def _satisfies_impact(condition: Dict, item: Dict) -> bool:
    min_score = condition.get("min_market_impact_score")
    if min_score is None:
        return True
    try:
        impact = item.get("market_impact") or {}
        return (impact.get("score") or 0) >= int(min_score)
    except Exception:
        return True


def evaluate() -> Dict[str, Any]:
    stream = _load_stream()
    rules = [r.to_dict() for r in alert_rules._items.values() if r.enabled]
    fired: List[Dict[str, Any]] = []
    for rule in rules:
        if not _cooldown_ok(rule):
            continue
        for item in stream:
            cond = rule.get("condition") or {}
            if not (
                _matches_category(cond, item)
                and _matches_ticker(cond, item)
                and _matches_keywords(cond, item)
                and _satisfies_confidence(cond, item)
                and _satisfies_impact(cond, item)
            ):
                continue
            user = accounts.get_user_by_session(rule.get("user_id"))
            if not user:
                user_map = {u.id: u for u in accounts._users.values()}
                user = user_map.get(rule.get("user_id"))
            if not user:
                continue
            ok = dispatch(rule.get("name") or "Alert", item, user.to_dict())
            if ok:
                alert_rules.mark_triggered(rule.get("id"))
                fired.append({"rule_id": rule.get("id"), "headline": item.get("headline"), "url": item.get("url")})
            if len(fired) >= MAX_ALERTS_PER_RUN:
                return {"fired": fired, "scanned": len(stream), "truncated": True}
    return {"fired": fired, "scanned": len(stream), "truncated": False}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = evaluate()
    print(json.dumps(result, indent=2))
