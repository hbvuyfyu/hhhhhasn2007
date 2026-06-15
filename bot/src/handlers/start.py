import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

from src.config import ADMIN_IDS
from src.database import queries as db

logger = logging.getLogger(__name__)


def _build_main_keyboard(uid: int) -> InlineKeyboardMarkup:
    platform = db.get_user_platform(uid)
    platform_emoji = "🤖" if platform == "android" else "🍎"
    kb = []
    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
    kb.append([InlineKeyboardButton("📱 AppsFlyer",       callback_data="af_menu")])
    kb.append([InlineKeyboardButton("📊 Adjust",          callback_data="adj_menu")])
    kb.append([InlineKeyboardButton("🌟 Singular",        callback_data="singular_menu")])
    kb.append([InlineKeyboardButton("🌾 مزرعة الجمبرة",  callback_data="jumper_farm")])
    kb.append([InlineKeyboardButton("📦 اشتراك",         callback_data="sub_menu")])
    kb.append([InlineKeyboardButton("🔧 إعدادات البروكسي", callback_data="proxy_settings")])
    kb.append([InlineKeyboardButton(f"{platform_emoji} نظام التشغيل", callback_data="select_platform")])
    return InlineKeyboardMarkup(kb)


def _sub_status_line(uid: int) -> str:
    if uid in ADMIN_IDS or db.is_allowed(uid):
        return "👑 *حساب مميز — بلا قيود*"
    sub = db.get_active_subscription(uid)
    if not sub:
        return "🔒 *لا يوجد اشتراك نشط* — اضغط 📦 اشتراك"
    end = sub.get("end_date")
    if end:
        try:
            if isinstance(end, str):
                end = datetime.fromisoformat(end)
            remaining_days = max(0, (end.date() - datetime.now().date()).days)
            exp_str = f"({remaining_days} يوم متبقٍ)"
        except Exception:
            exp_str = ""
    else:
        exp_str = ""
    used  = sub.get("daily_used", 0)
    limit = sub.get("daily_limit", 0)
    return (
        f"✅ *اشتراك نشط* — {sub.get('plan_name','')}\n"
        f"📊 الاستخدام اليوم: `{used}/{limit}` عملية {exp_str}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    db.upsert_user(uid, user.username or "", user.full_name or "")
    db.ensure_user_platform(uid)

    platform      = db.get_user_platform(uid)
    platform_name = "Android 🤖" if platform == "android" else "iOS 🍎"
    status_line   = _sub_status_line(uid)

    text = (
        "🔥 *AK Jumper Bot* 🔥\n\n"
        f"{status_line}\n\n"
        "✨ *اختر الخدمة:*\n"
        "┃ 📱 AppsFlyer\n"
        "┃ 📊 Adjust\n"
        "┃ 🌟 Singular\n"
        "┃ 🌾 مزرعة الجمبرة\n\n"
        f"📱 النظام الحالي: {platform_name}"
    )
    kb = _build_main_keyboard(uid)

    if update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def clean_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.upsert_user(uid, update.effective_user.username or "", update.effective_user.full_name or "")
    db.set_user_platform(uid, "android")
    await update.message.reply_text(
        "✅ *تم التنظيف الشامل*\n\nالمنصة: Android\nاستخدم /start للبدء.",
        parse_mode="Markdown",
    )


def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("clean", clean_start),
    ]
