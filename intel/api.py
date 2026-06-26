from __future__ import annotations

import json
import logging
import os
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional

from intel.accounts import accounts, alert_rules, watchlists
from intel.alert_eval import evaluate

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1]


class _ApiHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_token(self) -> Optional[str]:
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip() or None
        return None

    def _current_user(self):
        token = self._get_token()
        if not token:
            return None
        return accounts.get_user_by_session(token)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)

    def _route(self):
        method = self.command.upper()
        parsed = os.path.normpath(self.path)
        qs = ""
        if "?" in self.path:
            parsed, qs = self.path.split("?", 1)
        parsed = parsed.rstrip("/") or "/"

        def route_ok(path, required=None):  # required is reserved for future gating
            nonlocal method, parsed, qs
            return parsed == path

        user = self._current_user()
        try:
            if route_ok("/health"):
                return self._send_json(200, {"status": "ok", "phase": "1", "endpoints": ["/auth/login","/watchlists","/alert_rules","/alerts/evaluate","/export/watchlist"]})

            if route_ok("/auth/register"):
                if method != "POST":
                    return self._send_json(405, {"detail": "method_not_allowed"})
                body = self._read_json()
                user_obj = accounts.register(body.get("email", ""), body.get("password", ""), body.get("tier", "free"))
                return self._send_json(200, {"user_id": user_obj.id, "tier": user_obj.tier})
            if route_ok("/auth/login"):
                if method != "POST":
                    return self._send_json(405, {"detail": "method_not_allowed"})
                body = self._read_json()
                user_obj = accounts.login(body.get("email", ""), body.get("password", ""))
                token = accounts.create_session(user_obj)
                return self._send_json(200, {"token": token, "tier": user_obj.tier, "user_id": user_obj.id})

            if route_ok("/watchlists"):
                if not user:
                    return self._send_json(401, {"detail": "unauthenticated"})
                if method == "GET":
                    return self._send_json(200, [w.to_dict() for w in watchlists.list_for_user(user.id)])
                if method == "POST":
                    if user.tier not in {"pro", "elite"}:
                        return self._send_json(403, {"detail": "watchlist_tier_required"})
                    body = self._read_json()
                    wl = watchlists.create(user.id, body.get("name", "My Watchlist"), body.get("tickers", []) or [], body.get("keywords", []) or [], body.get("categories", ["finance", "security", "trends", "geopower"]) or [])
                    return self._send_json(200, wl.to_dict())
                return self._send_json(405, {"detail": "method_not_allowed"})

            if parsed.startswith("/watchlists/") and len(parsed.split("/")) == 3:
                wl_id = parsed.split("/")[2]
                if not user:
                    return self._send_json(401, {"detail": "unauthenticated"})
                if method == "DELETE":
                    if user.tier not in {"pro", "elite"}:
                        return self._send_json(403, {"detail": "watchlist_tier_required"})
                    ok = watchlists.delete(wl_id, user.id)
                    if not ok:
                        return self._send_json(404, {"detail": "watchlist_not_found"})
                    return self._send_json(200, {"status": "deleted"})
                return self._send_json(405, {"detail": "method_not_allowed"})

            if route_ok("/alert_rules"):
                if not user:
                    return self._send_json(401, {"detail": "unauthenticated"})
                if method == "GET":
                    return self._send_json(200, [r.to_dict() for r in alert_rules.list_for_user(user.id)])
                if method == "POST":
                    if user.tier not in {"pro", "elite"}:
                        return self._send_json(403, {"detail": "alert_tier_required"})
                    body = self._read_json()
                    rule = alert_rules.create(user.id, body.get("name", "Untitled"), body.get("condition", {}), body.get("action", {}))
                    return self._send_json(200, rule.to_dict())
                return self._send_json(405, {"detail": "method_not_allowed"})

            if route_ok("/alerts/evaluate"):
                if not user:
                    return self._send_json(401, {"detail": "unauthenticated"})
                if user.tier not in {"pro", "elite"}:
                    return self._send_json(403, {"detail": "alerts_tier_required"})
                result = evaluate()
                return self._send_json(200, result)

            if route_ok("/telegram/link"):
                if not user:
                    return self._send_json(401, {"detail": "unauthenticated"})
                if method != "POST":
                    return self._send_json(405, {"detail": "method_not_allowed"})
                body = self._read_json()
                chat_id = str(body.get("chat_id") or "")
                if not chat_id:
                    return self._send_json(400, {"detail": "chat_id_required"})
                user_obj = accounts.link_telegram(user.id, chat_id)
                return self._send_json(200, {"status": "linked", "telegram_chat_id": user_obj.telegram_chat_id})

            if route_ok("/export/watchlist"):
                if not user:
                    return self._send_json(401, {"detail": "unauthenticated"})
                if user.tier not in {"pro", "elite"}:
                    return self._send_json(403, {"detail": "export_tier_required"})
                wls = watchlists.list_for_user(user.id)
                rows = ["headline,category,source,tickers,confidence,timestamp,url"]
                for wl in wls:
                    rows.append(f'"{wl.name}","watchlist","n/a","{",".join(wl.tickers)}","n/a","n/a",""')
                payload = "\n".join(rows)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Length", str(len(payload.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
                return

            return self._send_json(404, {"detail": "not_found"})
        except Exception as exc:
            logger.exception("API error: %s", exc)
            return self._send_json(500, {"detail": "internal_error"})

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)


def create_app(host: str = "0.0.0.0", port: int = 8787):
    handler = _ApiHandler
    server = HTTPServer((host, port), handler)
    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = create_app()
    logger.info("AlphaIntel API on http://%s:%d", "0.0.0.0", 8787)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
