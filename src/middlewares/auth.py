import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import SUPPORT_USER, ADMIN_IDS
from src.database import queries as db
from src.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)


def require_access(func):
    """Allow all users to access bot, but block operations for non-subscribers."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        uid = user.id
        uname = user.username or ""
        name = user.full_name or ""

        db.upsert_user(uid, uname, name)
        db.ensure_user_platform(uid)

        # Admin always has full access
        if uid in ADMIN_IDS:
            db.increment_requests(uid)
            return await func(update, context, *args, **kwargs)

        # Check if banned
        cache_key = f"banned_{uid}"
        banned = cache_get(cache_key)
        if banned is None:
            banned = db.is_banned(uid)
            cache_set(cache_key, banned)

        if banned:
            await _reply(update, f"🚫 *أنت محظور*\n\nللتواصل مع الدعم: {SUPPORT_USER}")
            return

        # Check subscription for operational commands
        sub = db.get_active_subscription(uid)
        if sub:
            # Check daily limit
            used = sub.get("daily_used", 0)
            limit = sub.get("daily_limit", 0)
            if used >= limit:
                await _reply(update, f"⚠️ *تم استنفاد الحد اليومي*\n\n📊 الاستخدام: `{used}/{limit}`\n\nيرجى الانتظار حتى الغد أو ترقية اشتراكك.")
                return
            db.increment_requests(uid)
            return await func(update, context, *args, **kwargs)

        # No subscription - block operation and show subscription prompt
        await _reply(update,
            f"⚠️ *غير مشترك*\n\n"
            f"يرجى الاشتراك لاستخدام هذه الميزة.\n\n"
            f"للتواصل مع الدعم: {SUPPORT_USER}",
            show_sub_button=True
        )
        return

    return wrapper


def increment_usage_if_success(user_id: int) -> None:
    """Increment usage counter after successful operation."""
    db.increment_subscription_usage(user_id)


def allow_free_access(func):
    """Decorator for commands that don't require subscription (like subscription menu)."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        uid = user.id
        uname = user.username or ""
        name = user.full_name or ""

        db.upsert_user(uid, uname, name)
        db.ensure_user_platform(uid)

        # Check if banned
        cache_key = f"banned_{uid}"
        banned = cache_get(cache_key)
        if banned is None:
            banned = db.is_banned(uid)
            cache_set(cache_key, banned)

        if banned:
            await _reply(update, f"🚫 *أنت محظور*\n\nللتواصل مع الدعم: {SUPPORT_USER}")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


async def _reply(update: Update, text: str, show_sub_button: bool = False):
    if show_sub_button:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 اشتراك", callback_data="sub_menu")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ])
    else:
        kb = None

    if update.callback_query:
        try:
            await update.callback_query.answer()
            if kb:
                await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
            else:
                await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            pass
    elif update.message:
        if kb:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
