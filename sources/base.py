from __future__ import annotations

import datetime as dt
import email.utils
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    items: List[Dict[str, Any]]
    source_name: str
    category: str = "trends"
    success: bool = True
    error: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": self.items,
            "source_name": self.source_name,
            "category": self.category,
            "success": self.success,
            "error": self.error,
            "fetched_at": self.fetched_at,
        }


class BaseSource(ABC):
    name: str = "base"
    category: str = "trends"
    timeout: int = 25
    retries: int = 2

    @abstractmethod
    def fetch(self) -> SourceResult:
        raise NotImplementedError

    def _request(self, method: str, url: str, **kwargs):
        import urllib.request
        headers = kwargs.pop("headers", {})
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read(), resp.status
        except Exception as exc:
            raise RuntimeError(f"{self.name} request failed: {exc}") from exc

    def _safe_fetch(self) -> SourceResult:
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                result = self.fetch()
                logger.info("[%s] attempt %d success: %d items", self.name, attempt, len(result.items))
                return result
            except Exception as exc:
                last_err = exc
                logger.warning("[%s] attempt %d failed: %s", self.name, attempt, exc)
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 10))
        return SourceResult(
            items=[], source_name=self.name, category=self.category, success=False, error=str(last_err)
        )


def _text(text, pattern):
    m = re.search(pattern, text, re.S)
    if not m:
        return ""
    return next(g for g in m.groups() if g is not None).strip()


def _parse_dt(raw):
    raw = raw.strip()
    if not raw:
        return None
    try:
        return email.utils.parsedate_to_datetime(raw)
    except Exception:
        return None


def _fmt(raw):
    raw = raw.strip()
    if not raw:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        t = email.utils.parsedate_to_datetime(raw)
        return t.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return raw


def _trunc(text, n=180):
    t = text.strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"
