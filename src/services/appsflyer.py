import requests
import random
import uuid
import logging
import time
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

AF_API_URL = "https://api2.appsflyer.com/inappevent/{package}"

DEVICE_MODEL = "SM-S911B"
OS_VERSION   = "Android 14"
SDK_VERSION  = "6.15.0"
APP_VERSION  = "2.3.0"


def _build_proxy(proxy: Optional[Dict]) -> Optional[Dict]:
    if not proxy:
        return None
    host  = proxy.get("host", "")
    port  = proxy.get("port", "")
    ptype = proxy.get("proxy_type", "http").lower()
    user  = proxy.get("username", "")
    password = proxy.get("password", "")
    auth  = f"{user}:{password}@" if user and password else ""
    proxy_url = f"{ptype}://{auth}{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def send_af(
    pkg: str,
    dev_key: str,
    gaid: str,
    af_uid: str,
    event_name: str,
    revenue: float = None,
    proxy: Optional[Dict] = None,
    platform: str = "android",
    idfa: str = None,
    idfv: str = None,
    level: int = None,
) -> Tuple[int, str]:

    if not pkg or pkg == "None":
        return 400, "Error: Package name is required"
    if not dev_key:
        return 400, "Error: Dev Key is required"

    url = AF_API_URL.format(package=pkg)
    current_ts = int(time.time() * 1000)

    if platform == "ios":
        advertising_id      = idfa or gaid
        advertising_id_key  = "idfa"
    else:
        advertising_id      = gaid
        advertising_id_key  = "advertising_id"

    payload: Dict = {
        "appsflyer_id":    af_uid,
        advertising_id_key: advertising_id,
        "eventName":       event_name,
        "eventTime":       current_ts,
        "eventValue":      {},
        "device_model":    DEVICE_MODEL,
        "os_version":      OS_VERSION,
        "sdk_version":     SDK_VERSION,
        "app_version_name": APP_VERSION,
        "network":         "WiFi",
        "language":        "en-US",
        "timezone":        "Asia/Riyadh",
    }

    if revenue is not None:
        payload["eventRevenue"]  = str(revenue)
        payload["eventCurrency"] = "USD"
        payload["eventValue"] = {
            "af_content_id":    f"combo_{random.randint(1, 50)}",
            "af_content_type":  "purchase",
            "af_receipt_id":    str(uuid.uuid4()),
            "af_transaction_id": str(uuid.uuid4()),
            "af_currency":      "USD",
            "af_price":         str(revenue),
        }
    else:
        level_num = level if level is not None else _extract_level(event_name)
        if level_num:
            payload["eventValue"] = {
                "af_level":    str(level_num),
                "af_score":    str(random.randint(1000, 50000)),
                "af_duration": str(random.randint(30, 300)),
            }

    headers = {
        "Authentication":  dev_key,
        "User-Agent":      f"AppsFlyer-Android-SDK/{SDK_VERSION} (Linux; Android 14; {DEVICE_MODEL})",
        "Content-Type":    "application/json",
        "Accept":          "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
    }

    try:
        proxies = _build_proxy(proxy)
        r = requests.post(url, json=payload, headers=headers, timeout=30, proxies=proxies)
        logger.info(f"[AF] {pkg} | {event_name} | status={r.status_code}")
        return r.status_code, r.text
    except Exception as e:
        logger.error(f"[AF] Exception: {e}")
        return 500, str(e)


def _extract_level(event_name: str) -> Optional[str]:
    digits = ''.join(filter(str.isdigit, event_name))
    return digits if digits else None
