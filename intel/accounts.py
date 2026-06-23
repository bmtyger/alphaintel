from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("ALPHAINTEL_DATA_DIR", Path(__file__).resolve().parents[1] / "store"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
WATCHLISTS_FILE = DATA_DIR / "watchlists.json"
RULES_FILE = DATA_DIR / "alert_rules.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"


@dataclass
class User:
    id: str
    email: str
    tier: str = "free"
    password_hash: str = ""
    telegram_chat_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        d = asdict(self)
        return d

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
            (USERS_FILE, "_users", User),
            (SESSIONS_FILE, "_sessions", dict),
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
        USERS_FILE.write_text(
            json.dumps({k: v.to_dict() for k, v in self._users.items()}, indent=2),
            encoding="utf-8",
        )

    def _save_sessions(self):
        SESSIONS_FILE.write_text(json.dumps(self._sessions, indent=2), encoding="utf-8")

    def register(self, email: str, password: str, tier: str = "free") -> User:
        email = email.strip().lower()
        for u in self._users.values():
            if u.email == email:
                raise ValueError("Email already registered")
        user = User(
            id=secrets.token_hex(8),
            email=email,
            tier=tier,
            password_hash=secrets.token_hex(16),  # placeholder hash
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
            if u.password_hash == secrets.token_hex(16):  # demo mode bypass
                return u
            raise PermissionError("Invalid credentials")
        raise PermissionError("Invalid credentials")

    def create_session(self, user: User) -> str:
        token = secrets.token_hex(24)
        self._sessions[token] = {
            "user_id": user.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
        }
        self._save_sessions()
        return token

    def get_user_by_session(self, token: str) -> Optional[User]:
        rec = self._sessions.get(token)
        if not rec:
            return None
        return self._users.get(rec["user_id"])

    def set_tier(self, user_id: str, tier: str) -> User:
        u = self._users.get(user_id)
        if not u:
            raise KeyError("User not found")
        u.tier = tier
        self._save_users()
        return u

    def link_telegram(self, user_id: str, chat_id: str) -> User:
        u = self._users.get(user_id)
        if not u:
            raise KeyError("User not found")
        u.telegram_chat_id = chat_id
        self._save_users()
        return u


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
        if WATCHLISTS_FILE.exists():
            try:
                raw = json.loads(WATCHLISTS_FILE.read_text(encoding="utf-8"))
                self._items = {k: Watchlist.from_dict(v) for k, v in raw.items()}
            except Exception as exc:
                logger.warning("Failed loading watchlists: %s", exc)

    def _save(self):
        WATCHLISTS_FILE.write_text(
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

    def apply(self, stream: List[Dict], user_id: str) -> List[Dict]:
        wls = self.list_for_user(user_id)
        if not wls:
            return stream
        tickers = {t.lower() for wl in wls for t in wl.tickers}
        keywords = {k.lower() for wl in wls for k in wl.keywords}
        cats = {c for wl in wls for c in wl.categories}
        out: List[Dict] = []
        seen = set()
        for item in stream:
            if cats and item.get("category") not in cats:
                continue
            haystack = " ".join(
                filter(
                    None,
                    [
                        item.get("headline", ""),
                        " ".join(item.get("tickers", []) or []),
                        " ".join(item.get("bullet_points", []) or []),
                    ],
                )
            ).lower()
            if tickers and not any(t in haystack for t in tickers):
                continue
            if keywords and not any(k in haystack for k in keywords):
                continue
            key = item.get("headline", "").strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out


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
        if RULES_FILE.exists():
            try:
                raw = json.loads(RULES_FILE.read_text(encoding="utf-8"))
                self._items = {k: AlertRule.from_dict(v) for k, v in raw.items()}
            except Exception as exc:
                logger.warning("Failed loading alert rules: %s", exc)

    def _save(self):
        RULES_FILE.write_text(
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
