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


def check_and_reserve_usage(user_id: int) -> bool:
    """Atomically check daily limit and reserve one usage slot.
    Returns True if the user has remaining quota and a slot was reserved.
    Must be followed by confirm_usage() on success or rollback_usage() on failure."""
    sub = db.get_active_subscription(user_id)
    if not sub:
        return False
    used = sub.get("daily_used", 0)
    limit = sub.get("daily_limit", 0)
    if used >= limit:
        return False
    db.increment_subscription_usage(user_id)
    return True


def confirm_usage(user_id: int) -> None:
    """Confirm the reserved usage slot (already incremented in check_and_reserve_usage)."""
    pass  # Already incremented in check_and_reserve_usage


def rollback_usage(user_id: int) -> None:
    """Roll back a reserved usage slot if the operation failed."""
    db.decrement_subscription_usage(user_id)


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
