from __future__ import annotations

import json
import logging
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from intel.accounts import accounts, alert_rules, watchlists
from intel.config import ALLOWED_ORIGINS, DEFAULT_SESSION_TTL_DAYS

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1]

request_log: list[dict[str, Any]] = []
request_log_lock = Lock()
request_log_max = 500


def _record_request(status: int, method: str, path: str, elapsed: float, status_detail: str = "") -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "path": path,
        "status": status,
        "ms": round(elapsed, 2),
        "detail": status_detail,
    }
    with request_log_lock:
        request_log.append(entry)
        if len(request_log) > request_log_max:
            del request_log[: len(request_log) - request_log_max]


def get_metrics() -> Dict[str, int]:
    with request_log_lock:
        if not request_log:
            return {"requests": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
        metrics = {"requests": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
        for item in request_log:
            bucket = "{0}xx".format(item["status"] // 100)
            metrics["requests"] += 1
            if bucket in metrics:
                metrics[bucket] += 1
        return metrics


def get_recent_requests(limit: int = 50) -> list[dict[str, Any]]:
    with request_log_lock:
        return list(request_log[-limit:])


class _ApiHandler(BaseHTTPRequestHandler):
    def _cors_origin(self) -> str:
        origin = self.headers.get("Origin") or ""
        allowed = {o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()}
        if not allowed:
            return "*"
        if origin in allowed:
            return origin
        if "*" in allowed:
            return "*"
        return "null"

    def _send_json(self, status: int, payload):
        body = json.dumps(payload).encode("utf-8")
        acc = self._cors_origin()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", acc)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
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

    def _match_route(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        method = self.command.upper()
        qs = urllib.parse.parse_qs(parsed.query)
        single_qs = {k: (v[0] if v else "") for k, v in qs.items()}
        return method, path, single_qs

    def do_OPTIONS(self):
        acc = self._cors_origin()
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", acc)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def do_DELETE(self):
        self._route()

    def do_HEAD(self):
        self._route()

    def _route(self):
        method, path, qs = self._match_route()
        user = self._current_user()
        start_ns = time.monotonic()
        status_code = 500
        status_detail = "internal_error"
        try:
            accounts.prune_expired_sessions()
            if path == "/health":
                status_code = 200
                return self._send_json(status_code, {"status": "ok"})
            if path == "/auth/register":
                if method != "POST":
                    status_code = 405
                    return self._send_json(status_code, {"detail": "method_not_allowed"})
                body = self._read_json()
                user_obj = accounts.register(body.get("email", ""), body.get("password", ""), body.get("tier", "free"))
                status_code = 200
                return self._send_json(status_code, {"user_id": user_obj.id, "tier": user_obj.tier})
            if path == "/auth/login":
                if method != "POST":
                    status_code = 405
                    return self._send_json(status_code, {"detail": "method_not_allowed"})
                body = self._read_json()
                user_obj = accounts.login(body.get("email", ""), body.get("password", ""))
                token = accounts.create_session(user_obj, ttl_days=DEFAULT_SESSION_TTL_DAYS)
                status_code = 200
                return self._send_json(status_code, {"token": token, "tier": user_obj.tier, "user_id": user_obj.id})
            if path == "/watchlists":
                if not user:
                    status_code = 401
                    return self._send_json(status_code, {"detail": "unauthenticated"})
                if method == "GET":
                    status_code = 200
                    return self._send_json(status_code, [w.to_dict() for w in watchlists.list_for_user(user.id)])
                if method == "POST":
                    if user.tier not in {"pro", "elite"}:
                        status_code = 403
                        return self._send_json(status_code, {"detail": "watchlist_tier_required"})
                    body = self._read_json()
                    name = body.get("name", "My Watchlist")
                    tickers = body.get("tickers", []) or []
                    keywords = body.get("keywords", []) or []
                    categories = body.get("categories", ["finance", "security", "trends", "geopower"]) or []
                    wl = watchlists.create(user.id, name, tickers, keywords, categories)
                    status_code = 200
                    return self._send_json(status_code, wl.to_dict())
                status_code = 405
                return self._send_json(status_code, {"detail": "method_not_allowed"})
            if path.startswith("/watchlists/") and len(path.split("/")) == 3:
                wl_id = path.split("/")[2]
                if not user:
                    status_code = 401
                    return self._send_json(status_code, {"detail": "unauthenticated"})
                if method == "DELETE":
                    if user.tier not in {"pro", "elite"}:
                        status_code = 403
                        return self._send_json(status_code, {"detail": "watchlist_tier_required"})
                    ok = watchlists.delete(wl_id, user.id)
                    if not ok:
                        status_code = 404
                        return self._send_json(status_code, {"detail": "watchlist_not_found"})
                    status_code = 200
                    return self._send_json(status_code, {"status": "deleted"})
                status_code = 405
                return self._send_json(status_code, {"detail": "method_not_allowed"})
            if path == "/alert_rules":
                if not user:
                    status_code = 401
                    return self._send_json(status_code, {"detail": "unauthenticated"})
                if method == "GET":
                    status_code = 200
                    return self._send_json(status_code, [r.to_dict() for r in alert_rules.list_for_user(user.id)])
                if method == "POST":
                    if user.tier not in {"pro", "elite"}:
                        status_code = 403
                        return self._send_json(status_code, {"detail": "alert_tier_required"})
                    body = self._read_json()
                    rule = alert_rules.create(
                        user.id,
                        body.get("name", "Untitled"),
                        body.get("condition", {}),
                        body.get("action", {}),
                    )
                    status_code = 200
                    return self._send_json(status_code, rule.to_dict())
                status_code = 405
                return self._send_json(status_code, {"detail": "method_not_allowed"})
            if path == "/telegram/link":
                if not user:
                    status_code = 401
                    return self._send_json(status_code, {"detail": "unauthenticated"})
                if method != "POST":
                    status_code = 405
                    return self._send_json(status_code, {"detail": "method_not_allowed"})
                body = self._read_json()
                chat_id = str(body.get("chat_id") or "")
                if not chat_id:
                    status_code = 400
                    return self._send_json(status_code, {"detail": "chat_id_required"})
                user_obj = accounts.link_telegram(user.id, chat_id)
                status_code = 200
                return self._send_json(status_code, {"status": "linked", "telegram_chat_id": user_obj.telegram_chat_id})
            if path == "/export/watchlist":
                if not user:
                    status_code = 401
                    return self._send_json(status_code, {"detail": "unauthenticated"})
                if user.tier not in {"pro", "elite"}:
                    status_code = 403
                    return self._send_json(status_code, {"detail": "export_tier_required"})
                wls = watchlists.list_for_user(user.id)
                rows = ["headline,category,source,tickers,confidence,timestamp,url"]
                for item in wls:
                    rows.append('"{0}","watchlist","n/a","{1}","n/a","n/a",""'.format(item.name, ",".join(item.tickers)))
                payload = "\n".join(rows)
                status_code = 200
                self.send_response(status_code)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Length", str(len(payload.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
                return
            status_code = 404
            return self._send_json(status_code, {"detail": "not_found"})
        except Exception as exc:
            logger.exception("API error: %s", exc)
            status_code = 500
            status_detail = "internal_error"
            return self._send_json(status_code, {"detail": status_detail})
        finally:
            elapsed = time.monotonic() - start_ns
            effective_detail = status_detail if status_code == 500 and status_detail else str(status_code)
            _record_request(status_code, method, path, elapsed * 1000, effective_detail)

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
