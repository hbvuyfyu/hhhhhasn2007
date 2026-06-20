import hashlib
import hmac
import time
import logging
import requests
from typing import Tuple
from urllib.parse import urlencode

logger = logging.getLogger(_name_)

MEXC_API = "https://api.mexc.com"


def _sign(secret: str, params: dict) -> str:
    query_string = urlencode(params)
    return hmac.new(
        secret.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_usdt_deposit(api_key: str, api_secret: str, tx_id: str, expected_amount: float) -> Tuple[bool, str]:
    """
    التحقق من عملية USDT عبر MEXC API.
    يعيد (True, رسالة) إذا تم التحقق، أو (False, سبب الرفض).
    """

    if not api_key or not api_secret:
        return False, "❌ MEXC API غير مهيأ — يرجى التواصل مع الإدارة"

    timestamp = int(time.time() * 1000)

    params = {
        "coin": "USDT",
        "timestamp": timestamp,
        "recvWindow": 5000
    }

    signature = _sign(api_secret, params)
    params["signature"] = signature

    headers = {
        "X-MEXC-APIKEY": api_key
    }

    url = f"{MEXC_API}/api/v3/capital/deposit/hisrec"

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)

        if r.status_code == 401:
            return False, "❌ خطأ في مفاتيح MEXC API"

        if r.status_code != 200:
            logger.error(f"[MEXC] HTTP Error: {r.text}")
            return False, f"❌ خطأ من MEXC: {r.status_code}"

        deposits = r.json()

        if not isinstance(deposits, list) or not deposits:
            return False, "❌ لم يتم العثور على العملية — تأكد من رقم العملية"

        for dep in deposits:

            # نفس اسم المتغير بدون تغيير
            if dep.get("txId") == tx_id or dep.get("transHash") == tx_id:

                status = int(dep.get("status", 0))
                amount = float(dep.get("amount", 0))

                # ❗ MEXC statuses (4/5 pending, 1 confirmed)
                if status not in [1, 5]:
                    return False, f"❌ العملية لم تكتمل بعد (الحالة: {status})"

                if amount < expected_amount * 0.97:
                    return False, f"❌ المبلغ غير كافٍ: {amount} USDT (المطلوب: {expected_amount})"

                return True, f"✅ تم التحقق: {amount} USDT"

        return False, "❌ رقم العملية غير موجود في سجل الإيداعات"

    except requests.exceptions.Timeout:
        return False, "❌ انتهت مهلة الاتصال بـ MEXC"

    except Exception as e:
        logger.error(f"[MEXC] Exception: {e}")
        return False, f"❌ خطأ في التحقق: {e}"
