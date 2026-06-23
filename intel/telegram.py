from __future__ import annotations

import logging
import os
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)
TELEGRAM_SEND = os.getenv(
    "ALPHAINTEL_TELEGRAM_SEND",
    r"C:\Users\bmtyg\telegram_send.py",
)


def _run_send(text: str, chat_id: Optional[str] = None) -> bool:
    if not chat_id:
        return False
    try:
        subprocess.run(
            ["python", TELEGRAM_SEND, "--chat", str(chat_id), "--text", text],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except Exception as exc:
        logger.warning("Telegram dispatch failed: %s", exc)
        return False


def dispatch(rule_name: str, item: Dict, user: Dict) -> bool:
    chat_id = (user or {}).get("telegram_chat_id")
    if not chat_id:
        return False
    text = (
        f"AlphaIntel alert: {rule_name}\n"
        f"{item.get('headline') or 'Signal'}\n"
        f"Source: {item.get('source')}\n"
        f"Confidence: {item.get('confidence')}%\n"
        f"Tickers: {', '.join((item.get('tickers') or [])[:6])}\n"
        f"Link: {item.get('url') or ''}"
    )
    return _run_send(text, chat_id)
