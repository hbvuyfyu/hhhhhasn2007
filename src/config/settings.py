import os
from typing import List


BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

ADMIN_IDS: List[int] = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "6075014046,5697155314,8114043468").split(",")
    if x.strip().isdigit()
]

SUPPORT_USER: str = os.environ.get("SUPPORT_USER", "@abodnft")

SDK_VERSION: str = os.environ.get("SDK_VERSION", "6.15.0")
MAX_WORKERS: int = int(os.environ.get("MAX_WORKERS", "50"))
CACHE_TTL: int = int(os.environ.get("CACHE_TTL", "300"))
DB_POOL_MIN: int = int(os.environ.get("DB_POOL_MIN", "1"))
DB_POOL_MAX: int = int(os.environ.get("DB_POOL_MAX", "20"))
