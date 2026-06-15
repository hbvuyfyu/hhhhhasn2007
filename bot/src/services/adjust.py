import requests
import logging
import time
import random
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

ADJ_URL = "https://s2s.adjust.com/event"


def _build_proxy(proxy: Optional[Dict]) -> Optional[Dict]:
    if not proxy:
        return None
    host = proxy.get("host", "")
    port = proxy.get("port", "")
    ptype = proxy.get("proxy_type", "http").lower()
    user = proxy.get("username", "")
    password = proxy.get("password", "")
    if user and password:
        auth = f"{user}:{password}@"
    else:
        auth = ""
    proxy_url = f"{ptype}://{auth}{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def send_adj(
    app_token: str,
    event_token: str,
    gps_adid: str,
    proxy: Optional[Dict] = None,
    platform: str = "android",
    idfa: str = None,
    idfv: str = None,
    level: int = None,
) -> Tuple[int, str]:
    if platform == "ios":
        advertising_id = idfa or gps_adid
        id_param = "idfa"
    else:
        advertising_id = gps_adid
        id_param = "gps_adid"

    params = {
        "app_token": app_token,
        "event_token": event_token,
        id_param: advertising_id,
        "environment": "production",
        "created_at": str(int(time.time())),
        "ip_address": f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
    }

    if idfv:
        params["idfv"] = idfv
    if level is not None:
        params["level"] = str(level)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    try:
        proxies = _build_proxy(proxy)
        r = requests.get(ADJ_URL, params=params, headers=headers, timeout=30, proxies=proxies)
        logger.info(f"[ADJ] {app_token} | {event_token} | status={r.status_code}")
        return r.status_code, r.text[:500]
    except Exception as e:
        logger.error(f"[ADJ] Exception: {e}")
        return 500, str(e)
