from __future__ import annotations

import os

DEFAULT_SESSION_TTL_DAYS = int(os.getenv("ALPHAINTEL_SESSION_TTL_DAYS", "30"))
ALLOWED_ORIGINS = os.getenv("ALPHAINTEL_ALLOWED_ORIGINS", "")
