from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from intel.accounts import accounts, alert_rules, watchlists

logger = logging.getLogger(__name__)
app = FastAPI(title="AlphaIntel API", version="0.1.0")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    tier: str = "free"


class WatchlistCreate(BaseModel):
    name: str = Field(default="My Watchlist")
    tickers: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    categories: List[str] = Field(defaultFactory=lambda: ["finance", "security", "trends", "geopower"])


class AlertRuleCreate(BaseModel):
    name: str
    condition: Dict = Field(default_factory=dict)
    action: Dict = Field(default_factory=lambda: {"type": "telegram"})


TELEGRAM_RELAY = "C:\\Users\\bmtyg\\telegram_send.py"


def _user_from_token(token: Optional[str]) -> Optional[Dict]:
    if not token:
        return None
    return accounts.get_user_by_session(token)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    try:
        user = accounts.register(req.email, req.password, req.tier)
        return {"user_id": user.id, "tier": user.tier}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Register failed: %s", exc)
        raise HTTPException(status_code=500, detail="register_failed") from exc


@app.post("/auth/login")
def auth_login(req: LoginRequest):
    try:
        user = accounts.login(req.email, req.password)
        token = accounts.create_session(user)
        return {"token": token, "tier": user.tier, "user_id": user.id}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Login failed: %s", exc)
        raise HTTPException(status_code=500, detail="login_failed") from exc


@app.get("/watchlists")
def list_watchlists(x_aleph_token: Optional[str] = None):
    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    items = watchlists.list_for_user(user.id)
    return [w.to_dict() for w in items]


@app.post("/watchlists")
def create_watchlist(req: WatchlistCreate, x_aleph_token: Optional[str] = None):
    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    if user.tier not in {"pro", "elite"}:
        raise HTTPException(status_code=403, detail="watchlist_tier_required")
    wl = watchlists.create(user.id, req.name, req.tickers, req.keywords, req.categories)
    return wl.to_dict()


@app.delete("/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: str, x_aleph_token: Optional[str] = None):
    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    if user.tier not in {"pro", "elite"}:
        raise HTTPException(status_code=403, detail="watchlist_tier_required")
    ok = watchlists.delete(watchlist_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="watchlist_not_found")
    return {"status": "deleted"}


@app.get("/alert_rules")
def list_alert_rules(x_aleph_token: Optional[str] = None):
    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    items = alert_rules.list_for_user(user.id)
    return [r.to_dict() for r in items]


@app.post("/alert_rules")
def create_alert_rule(req: AlertRuleCreate, x_aleph_token: Optional[str] = None):
    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    if user.tier not in {"pro", "elite"}:
        raise HTTPException(status_code=403, detail="alert_tier_required")
    rule = alert_rules.create(user.id, req.name, req.condition, req.action)
    return rule.to_dict()


class TelegramLink(BaseModel):
    chat_id: str


@app.post("/telegram/link")
def link_telegram(req: TelegramLink, x_aleph_token: Optional[str] = None):
    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    user = accounts.link_telegram(user.id, req.chat_id)
    return {"status": "linked", "telegram_chat_id": user.telegram_chat_id}


@app.get("/export/watchlist")
def export_watchlist_csv(x_aleph_token: Optional[str] = None):
    from fastapi.responses import PlainTextResponse

    user = _user_from_token(x_aleph_token)
    if not user:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)
    if user.tier not in {"pro", "elite"}:
        raise HTTPException(status_code=403, detail="export_tier_required")

    wls = watchlists.list_for_user(user.id)
    rows = ["headline,tategory,source,tickers,confidence,timestamp,url"]
    for wl in wls:
        # The serializer cannot access intel engine here.
        # Kept as a stub export until data.json filter is wired.
        rows.append(f'"{wl.name}","watchlist","n/a","{",".join(wl.tickers)}","n/a","n/a",""')

    return PlainTextResponse(content="\n".join(rows), media_type="text/csv")
