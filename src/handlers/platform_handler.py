import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from src.database import queries as db
from src.middlewares.auth import require_access
from src.utils.cache import cache_clear

logger = logging.getLogger(__name__)


@require_access
async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    kb = [
        [InlineKeyboardButton("🤖 Android (GAID / AF UID)", callback_data="set_platform_android")],
        [InlineKeyboardButton("🍎 iOS (IDFA / IDFV)", callback_data="set_platform_ios")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "📱 *اختر نظام التشغيل:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def set_platform_android(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    db.set_user_platform(uid, "android")
    cache_clear(f"access_{uid}")
    await query.edit_message_text("✅ *تم التغيير إلى Android* 🤖", parse_mode="Markdown")
    from src.handlers.start import start
    await start(update, context)


@require_access
async def set_platform_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    db.set_user_platform(uid, "ios")
    cache_clear(f"access_{uid}")
    await query.edit_message_text(
        "✅ *تم التغيير إلى iOS* 🍎\n\n⚠️ سيتم طلب IDFA, IDFV عند الاستخدام.",
        parse_mode="Markdown",
    )
    from src.handlers.start import start
    await start(update, context)


def get_handlers():
    return [
        CallbackQueryHandler(select_platform, pattern="^select_platform$"),
        CallbackQueryHandler(set_platform_android, pattern="^set_platform_android$"),
        CallbackQueryHandler(set_platform_ios, pattern="^set_platform_ios$"),
        CallbackQueryHandler(select_platform, pattern="^main_menu$"),
    ]
