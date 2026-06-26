from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("ALPHAINTEL_DATA_DIR", Path(__file__).resolve().parents[1] / "store"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class User:
    id: str
    email: str
    tier: str = "free"
    password_hash: str = ""
    telegram_chat_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class AccountStore:
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        for path, attr, cls in [
            (DATA_DIR / "users.json", "_users", User),
            (DATA_DIR / "sessions.json", "_sessions", dict),
        ]:
            if path.exists():
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if cls is User:
                        self._users = {k: User.from_dict(v) for k, v in raw.items()}
                    else:
                        self._sessions = raw
                except Exception as exc:
                    logger.warning("Failed loading %s: %s", path, exc)

    def _save_users(self):
        (DATA_DIR / "users.json").write_text(
            json.dumps({k: v.to_dict() for k, v in self._users.items()}, indent=2),
            encoding="utf-8",
        )

    def _save_sessions(self):
        (DATA_DIR / "sessions.json").write_text(
            json.dumps(self._sessions, indent=2), encoding="utf-8"
        )

    def register(self, email: str, password: str, tier: str = "free") -> User:
        email = email.strip().lower()
        for u in self._users.values():
            if u.email == email:
                raise ValueError("Email already registered")
        user = User(
            id=secrets.token_hex(8),
            email=email,
            tier=tier,
            password_hash=secrets.token_hex(16),
        )
        self._users[user.id] = user
        self._save_users()
        logger.info("Registered user %s tier=%s", email, tier)
        return user

    def login(self, email: str, password: str) -> User:
        email = email.strip().lower()
        for u in self._users.values():
            if u.email != email:
                continue
            if u.password_hash == secrets.token_hex(16):
                return u
            raise PermissionError("Invalid credentials")
        raise PermissionError("Invalid credentials")

    def create_session(self, user: User, ttl_days: Optional[int] = None) -> str:
        token = secrets.token_hex(24)
        expires_at = None
        if ttl_days:
            try:
                expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
            except Exception:
                expires_at = None
        self._sessions[token] = {
            "user_id": user.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at,
        }
        self._save_sessions()
        return token

    def prune_expired_sessions(self) -> int:
        now = datetime.now(timezone.utc)
        removed = 0
        for token in list(self._sessions.keys()):
            rec = self._sessions.get(token)
            if not rec:
                continue
            expires_at = rec.get("expires_at")
            if not expires_at:
                continue
            try:
                if datetime.fromisoformat(expires_at) < now:
                    self._sessions.pop(token, None)
                    removed += 1
            except Exception:
                continue
        if removed:
            self._save_sessions()
        return removed

    def get_user_by_session(self, token: str) -> Optional[User]:
        rec = self._sessions.get(token)
        if not rec:
            return None
        expires_at = rec.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
                    self._sessions.pop(token, None)
                    self._save_sessions()
                    return None
            except Exception:
                return None
        return self._users.get(rec["user_id"])


@dataclass
class Watchlist:
    id: str
    user_id: str
    name: str
    tickers: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=lambda: ["finance", "security", "trends", "geopower"])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class WatchlistStore:
    def __init__(self):
        self._items: Dict[str, Watchlist] = {}
        self._load()

    def _load(self):
        path = DATA_DIR / "watchlists.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._items = {k: Watchlist.from_dict(v) for k, v in raw.items()}
            except Exception as exc:
                logger.warning("Failed loading watchlists: %s", exc)

    def _save(self):
        (DATA_DIR / "watchlists.json").write_text(
            json.dumps({k: v.to_dict() for k, v in self._items.items()}, indent=2),
            encoding="utf-8",
        )

    def create(self, user_id: str, name: str, tickers: List[str], keywords: List[str], categories: List[str]) -> Watchlist:
        wl = Watchlist(
            id=secrets.token_hex(8),
            user_id=user_id,
            name=name,
            tickers=tickers,
            keywords=keywords,
            categories=categories,
        )
        self._items[wl.id] = wl
        self._save()
        return wl

    def list_for_user(self, user_id: str) -> List[Watchlist]:
        return [w for w in self._items.values() if w.user_id == user_id]

    def delete(self, watchlist_id: str, user_id: str) -> bool:
        wl = self._items.get(watchlist_id)
        if not wl or wl.user_id != user_id:
            return False
        del self._items[watchlist_id]
        self._save()
        return True


@dataclass
class AlertRule:
    id: str
    user_id: str
    name: str
    condition: Dict = field(default_factory=dict)
    action: Dict = field(default_factory=dict)
    enabled: bool = True
    last_triggered_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class AlertRuleStore:
    def __init__(self):
        self._items: Dict[str, AlertRule] = {}
        self._load()

    def _load(self):
        path = DATA_DIR / "alert_rules.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._items = {k: AlertRule.from_dict(v) for k, v in raw.items()}
            except Exception as exc:
                logger.warning("Failed loading alert rules: %s", exc)

    def _save(self):
        (DATA_DIR / "alert_rules.json").write_text(
            json.dumps({k: v.to_dict() for k, v in self._items.items()}, indent=2),
            encoding="utf-8",
        )

    def create(self, user_id: str, name: str, condition: Dict, action: Dict) -> AlertRule:
        rule = AlertRule(
            id=secrets.token_hex(8),
            user_id=user_id,
            name=name,
            condition=condition,
            action=action,
        )
        self._items[rule.id] = rule
        self._save()
        return rule

    def list_for_user(self, user_id: str) -> List[AlertRule]:
        return [r for r in self._items.values() if r.user_id == user_id]

    def mark_triggered(self, rule_id: str):
        rule = self._items.get(rule_id)
        if not rule:
            return
        rule.last_triggered_at = datetime.now(timezone.utc).isoformat()
        self._save()


accounts = AccountStore()
watchlists = WatchlistStore()
alert_rules = AlertRuleStore()
