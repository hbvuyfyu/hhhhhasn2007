import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access

logger = logging.getLogger(__name__)

PROXY_TYPE, PROXY_IP_PORT, PROXY_AUTH_CHOICE, PROXY_USERNAME, PROXY_PASSWORD = range(500, 505)


def _back_kb(data: str = "proxy_settings") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=data)]])


def _format_proxy_info(proxy) -> str:
    if not proxy:
        return "❌ *لا يوجد بروكسي*"
    auth = f"{proxy['username']}:{proxy['password']}@" if proxy.get("username") else ""
    return f"✅ *البروكسي الحالي:*\n📡 `{proxy['proxy_type']}://{auth}{proxy['host']}:{proxy['port']}`"


@require_access
async def proxy_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    proxy = db.get_proxy_for_user(uid)
    status_text = _format_proxy_info(proxy)

    kb = [
        [InlineKeyboardButton("➕ إضافة / تغيير بروكسي", callback_data="proxy_add")],
    ]
    if proxy:
        kb.append([InlineKeyboardButton("🧪 اختبار البروكسي", callback_data="proxy_test")])
        kb.append([InlineKeyboardButton("🗑️ حذف البروكسي", callback_data="proxy_del")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])

    await query.edit_message_text(
        f"🔧 *إعدادات البروكسي*\n\n{status_text}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def proxy_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    proxy = db.get_proxy_for_user(uid)
    if not proxy:
        await query.edit_message_text("❌ *لا يوجد بروكسي للاختبار*", parse_mode="Markdown", reply_markup=_back_kb())
        return

    await query.edit_message_text("🔄 *جاري اختبار البروكسي...*", parse_mode="Markdown")

    ptype = proxy["proxy_type"].lower()
    host = proxy["host"]
    port = proxy["port"]
    user = proxy.get("username", "")
    pwd = proxy.get("password", "")
    auth = f"{user}:{pwd}@" if user and pwd else ""
    proxy_url = f"{ptype}://{auth}{host}:{port}"
    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        r = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=15)
        ip = r.json().get("origin", "unknown")
        await query.edit_message_text(
            f"✅ *البروكسي يعمل!*\n🌐 IP: `{ip}`",
            reply_markup=_back_kb(),
            parse_mode="Markdown",
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ *البروكسي لا يعمل:*\n`{str(e)[:200]}`",
            reply_markup=_back_kb(),
            parse_mode="Markdown",
        )


@require_access
async def proxy_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    db.delete_proxy(uid)
    await query.edit_message_text("✅ *تم حذف البروكسي*", parse_mode="Markdown", reply_markup=_back_kb())


@require_access
async def proxy_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("🔒 HTTP / HTTPS", callback_data="proxy_type_http")],
        [InlineKeyboardButton("🔒 SOCKS5", callback_data="proxy_type_socks5")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="proxy_settings")],
    ]
    await query.edit_message_text(
        "🔧 *اختر نوع البروكسي:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return PROXY_TYPE


@require_access
async def proxy_type_http(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["proxy_type"] = "http"
    await query.edit_message_text(
        "📡 *أدخل IP:Port*\nمثال: `192.168.1.1:8080`",
        parse_mode="Markdown",
    )
    return PROXY_IP_PORT


@require_access
async def proxy_type_socks5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["proxy_type"] = "socks5"
    await query.edit_message_text(
        "📡 *أدخل IP:Port*\nمثال: `192.168.1.1:1080`",
        parse_mode="Markdown",
    )
    return PROXY_IP_PORT


@require_access
async def proxy_ip_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    parts = raw.split(":")
    if len(parts) != 2:
        await update.message.reply_text("❌ *صيغة خاطئة*\nاستخدم: `ip:port`", parse_mode="Markdown")
        return PROXY_IP_PORT
    ip, port_str = parts
    try:
        port = int(port_str)
    except ValueError:
        await update.message.reply_text("❌ *المنفذ يجب أن يكون رقماً*", parse_mode="Markdown")
        return PROXY_IP_PORT

    context.user_data["proxy_host"] = ip
    context.user_data["proxy_port"] = port

    kb = [
        [InlineKeyboardButton("✅ لا، بدون مصادقة", callback_data="proxy_no_auth")],
        [InlineKeyboardButton("🔐 نعم، إضافة مصادقة", callback_data="proxy_need_auth")],
    ]
    await update.message.reply_text(
        "🔐 *هل يحتاج البروكسي مصادقة؟*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return PROXY_AUTH_CHOICE


@require_access
async def proxy_no_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _save_proxy(update, context, "", "")
    return ConversationHandler.END


@require_access
async def proxy_need_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 *أدخل اسم المستخدم (Username):*", parse_mode="Markdown")
    return PROXY_USERNAME


@require_access
async def proxy_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proxy_user"] = update.message.text.strip()
    await update.message.reply_text("🔑 *أدخل كلمة المرور (Password):*", parse_mode="Markdown")
    return PROXY_PASSWORD


@require_access
async def proxy_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd = update.message.text.strip()
    await _save_proxy(update, context, context.user_data.get("proxy_user", ""), pwd)
    return ConversationHandler.END


async def _save_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str, password: str):
    uid = update.effective_user.id
    db.save_proxy(
        user_id=uid,
        proxy_type=context.user_data.get("proxy_type", "http"),
        host=context.user_data.get("proxy_host", ""),
        port=context.user_data.get("proxy_port", 0),
        username=username,
        password=password,
    )
    kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="proxy_settings")]]
    msg = "📡 *تم حفظ البروكسي بنجاح!*"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(proxy_add, pattern="^proxy_add$")],
        states={
            PROXY_TYPE: [
                CallbackQueryHandler(proxy_type_http, pattern="^proxy_type_http$"),
                CallbackQueryHandler(proxy_type_socks5, pattern="^proxy_type_socks5$"),
            ],
            PROXY_IP_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_ip_port)],
            PROXY_AUTH_CHOICE: [
                CallbackQueryHandler(proxy_no_auth, pattern="^proxy_no_auth$"),
                CallbackQueryHandler(proxy_need_auth, pattern="^proxy_need_auth$"),
            ],
            PROXY_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_username)],
            PROXY_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_password)],
        },
        fallbacks=[CallbackQueryHandler(proxy_settings, pattern="^proxy_settings$")],
        allow_reentry=True,
    )


def get_handlers():
    return [
        get_conversation_handler(),
        CallbackQueryHandler(proxy_settings, pattern="^proxy_settings$"),
        CallbackQueryHandler(proxy_test, pattern="^proxy_test$"),
        CallbackQueryHandler(proxy_del, pattern="^proxy_del$"),
    ]
