import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import ADMIN_IDS
from src.database import queries as db

logger = logging.getLogger(__name__)


def require_access(func):
    """
    أي أدمن → يمر مباشرة.
    محظور → يُرفض.
    مستخدم ذو اشتراك نشط + لم يتجاوز الحد اليومي → يمر + يُحسب.
    مستخدم مُضاف يدوياً (allowed) → يمر بدون حد.
    غير ذلك → رسالة اشتراك.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        uid   = user.id
        uname = user.username or ""
        name  = user.full_name or ""

        db.upsert_user(uid, uname, name)
        db.ensure_user_platform(uid)

        # ── أدمن ──────────────────────────────────────────
        if uid in ADMIN_IDS:
            db.increment_requests(uid)
            return await func(update, context, *args, **kwargs)

        # ── محظور ─────────────────────────────────────────
        if db.is_banned(uid):
            await _reply(update, "🚫 *أنت محظور من استخدام البوت*")
            return

        # ── مُضاف يدوياً من الأدمن (بدون اشتراك) ─────────
        if db.is_allowed(uid):
            db.increment_requests(uid)
            return await func(update, context, *args, **kwargs)

        # ── اشتراك نشط ────────────────────────────────────
        sub = db.get_active_subscription(uid)
        if sub is None:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 اشتراك الآن", callback_data="sub_menu")],
            ])
            await _reply_kb(
                update,
                "🔒 *يجب الاشتراك أولاً*\n\nاضغط الزر لعرض الباقات المتاحة:",
                kb,
            )
            return

        if sub["daily_used"] >= sub["daily_limit"]:
            await _reply(
                update,
                f"⏰ *تجاوزت الحد اليومي*\n\n"
                f"الحد: `{sub['daily_limit']}` عملية/يوم\n"
                f"يتجدد الحد منتصف الليل تلقائياً.",
            )
            return

        db.increment_subscription_usage(uid)
        db.increment_requests(uid)
        return await func(update, context, *args, **kwargs)

    return wrapper


# ── helpers ───────────────────────────────────────────────

async def _reply(update: Update, text: str):
    if update.callback_query:
        try:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            pass
    elif update.message:
        await update.message.reply_text(text, parse_mode="Markdown")


async def _reply_kb(update: Update, text: str, kb: InlineKeyboardMarkup):
    if update.callback_query:
        try:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                text, parse_mode="Markdown", reply_markup=kb
            )
        except Exception:
            pass
    elif update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
