import hashlib
import hmac
import time
import logging
import requests
from typing import Tuple

logger = logging.getLogger(__name__)

BINANCE_API = "https://api.binance.com"


def _sign(secret: str, params: str) -> str:
    return hmac.new(secret.encode(), params.encode(), hashlib.sha256).hexdigest()


def verify_usdt_deposit(api_key: str, api_secret: str, tx_id: str, expected_amount: float) -> Tuple[bool, str]:
    """
    التحقق من عملية USDT TRC20 عبر Binance API.
    يعيد (True, رسالة) إذا تم التحقق، أو (False, سبب الرفض).
    """
    if not api_key or not api_secret:
        return False, "❌ Binance API غير مهيأ — يرجى التواصل مع الإدارة"

    timestamp = int(time.time() * 1000)
    params = f"coin=USDT&txId={tx_id}&timestamp={timestamp}"
    signature = _sign(api_secret, params)
    url = f"{BINANCE_API}/sapi/v1/capital/deposit/hisrec?{params}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 401:
            return False, "❌ خطأ في مفاتيح Binance API"
        if r.status_code != 200:
            return False, f"❌ خطأ من Binance: {r.status_code}"

        deposits = r.json()
        if not isinstance(deposits, list) or not deposits:
            return False, "❌ لم يتم العثور على العملية — تأكد من رقم العملية"

        for dep in deposits:
            if dep.get("txId") == tx_id:
                status = dep.get("status")
                if status != 1:
                    return False, f"❌ العملية لم تكتمل بعد (الحالة: {status})"
                amount = float(dep.get("amount", 0))
                if amount < expected_amount * 0.97:
                    return False, f"❌ المبلغ غير كافٍ: {amount} USDT (المطلوب: {expected_amount})"
                return True, f"✅ تم التحقق: {amount} USDT"

        return False, "❌ رقم العملية غير موجود في سجل الإيداعات"
    except requests.exceptions.Timeout:
        return False, "❌ انتهت مهلة الاتصال بـ Binance"
    except Exception as e:
        logger.error(f"[Binance] Exception: {e}")
        return False, f"❌ خطأ في التحقق: {e}"
