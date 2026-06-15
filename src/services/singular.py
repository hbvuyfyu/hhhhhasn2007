import requests
import logging
import time
import random
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

SINGULAR_URL = "https://s2s.singular.net/api/v1/evt"


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


def send_singular(
    event_name: str,
    aifa: str,
    uid: str,
    package: str,
    app_key: str,
    level: int = None,
    proxy: Optional[Dict] = None,
    platform: str = "android",
    idfa: str = None,
    idfv: str = None,
    singular_uid: str = None,
) -> Tuple[int, str]:
    if platform == "ios":
        advertising_id = idfa or aifa
        id_param = "idfa"
    else:
        advertising_id = aifa
        id_param = "aifa"

    payload: Dict = {
        "a": app_key,
        "p": package,
        "i": package,
        "av": "1.0.0",
        "n": event_name,
        id_param: advertising_id,
        "e": event_name,
        "custom_user_id": singular_uid or uid,
        "ts": str(int(time.time())),
        "ip": f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        "ve": "1.0.0",
        "ma": "samsung",
        "mo": "SM-A515F",
        "country": "SA",
        "lc": "ar_SA",
    }

    if idfv:
        payload["idfv"] = idfv
    if level is not None:
        payload["level"] = str(level)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "okhttp/4.9.1",
    }

    try:
        proxies = _build_proxy(proxy)
        r = requests.post(SINGULAR_URL, json=payload, headers=headers, timeout=30, proxies=proxies)
        logger.info(f"[SNG] {package} | {event_name} | status={r.status_code}")
        return r.status_code, r.text[:500]
    except Exception as e:
        logger.error(f"[SNG] Exception: {e}")
        return 500, str(e)
