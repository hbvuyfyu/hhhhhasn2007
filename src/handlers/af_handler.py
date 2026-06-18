import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access, check_and_reserve_usage, confirm_usage, rollback_usage
from src.services.appsflyer import send_af
from src.utils.navigation import nav_push, nav_clear, nav_add_back_row

logger = logging.getLogger(__name__)

AF_GAID, AF_IDFA, AF_IDFV, AF_UID, AF_UID_IOS, AF_CUSTOM_LEVEL = range(100, 106)


def _result_text(status: int, resp: str) -> str:
    if status == 200:
        return "✅ *تم الإرسال بنجاح!*"
    return f"❌ *فشل الإرسال*\nالكود: `{status}`\n`{resp[:200]}`"


def _back_kb(data: str = "af_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="go_back"), InlineKeyboardButton("🏠 القائمة", callback_data="main_menu")]
    ])


@require_access
async def af_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nav_push(context, "main_menu")
    games = db.get_all_games_af()
    if not games:
        await query.edit_message_text(
            "❌ *لا توجد ألعاب AppsFlyer*",
            parse_mode="Markdown",
            reply_markup=_back_kb("main_menu"),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"af_game_{g['id']}")]
        for g in games
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text(
        "📱 *اختر اللعبة - AppsFlyer*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def af_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nav_push(context, "af_menu")
    game_id = int(query.data.replace("af_game_", ""))
    game = db.get_game_af_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ خطأ: اللعبة غير موجودة", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["af_game_id"] = game_id
    context.user_data["af_game"] = dict(game)
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)

    if platform == "ios":
        await query.edit_message_text(
            f"🍎 *iOS - AppsFlyer*\n🎮 {game['display_name']}\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
            parse_mode="Markdown",
        )
        return AF_IDFA
    else:
        await query.edit_message_text(
            f"🤖 *Android - AppsFlyer*\n🎮 {game['display_name']}\n\n📱 *أدخل GAID:*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
            parse_mode="Markdown",
        )
        return AF_GAID


@require_access
async def af_gaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gaid = update.message.text.strip()
    context.user_data["af_gaid"] = gaid
    await update.message.reply_text(
        "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`",
        parse_mode="Markdown",
    )
    return AF_UID


@require_access
async def af_idfa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idfa = update.message.text.strip()
    context.user_data["af_idfa"] = idfa
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return AF_IDFV


@require_access
async def af_idfv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idfv = update.message.text.strip()
    context.user_data["af_idfv"] = idfv
    await update.message.reply_text(
        "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`",
        parse_mode="Markdown",
    )
    return AF_UID_IOS


@require_access
async def af_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["af_uid"] = update.message.text.strip()
    return await _show_af_events(update, context)


@require_access
async def af_uid_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["af_uid"] = update.message.text.strip()
    return await _show_af_events(update, context)


async def _show_af_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_id = context.user_data.get("af_game_id")
    game = context.user_data.get("af_game", {})
    events = db.get_af_events(game_id)
    if not events:
        await update.message.reply_text(
            "❌ *لا توجد أحداث لهذه اللعبة*",
            parse_mode="Markdown",
            reply_markup=_back_kb("af_menu"),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(ev["display_name"], callback_data=f"af_send_{ev['id']}")]
        for ev in events
    ]
    # Add custom event button if enabled for this game
    if db.is_custom_event_enabled("af", game_id):
        kb.append([InlineKeyboardButton("🎯 حدث مخصص", callback_data="af_custom_event")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="af_menu")])
    await update.message.reply_text(
        f"🎯 *اختر الحدث*\n🎮 {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def af_custom_event_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to enter custom level."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎯 *حدد رقم اللفل*\n\n"
        "📝 أدخل رقم اللفل المطلوب\n"
        "مثال: `45` أو `100`",
        parse_mode="Markdown",
    )
    return AF_CUSTOM_LEVEL


@require_access
async def af_custom_level_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process custom level and send event."""
    try:
        level = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return AF_CUSTOM_LEVEL

    context.user_data["af_custom_level"] = level
    game_id = context.user_data.get("af_game_id")
    game = context.user_data.get("af_game", {})
    uid = update.effective_user.id

    # Check and reserve usage slot before sending
    from src.config import ADMIN_IDS
    if uid not in ADMIN_IDS:
        if not check_and_reserve_usage(uid):
            sub = db.get_active_subscription(uid)
            used = sub.get("daily_used", 0) if sub else 0
            limit = sub.get("daily_limit", 0) if sub else 0
            await update.message.reply_text(
                f"⚠️ *تم استنفاد الحد اليومي*\n\n📊 الاستخدام: `{used}/{limit}`\n\nيرجى الانتظار حتى الغد أو ترقية اشتراكك.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 اشتراك", callback_data="sub_menu")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
                ]),
            )
            return ConversationHandler.END

    platform = db.get_user_platform(uid)
    proxy_row = db.get_proxy_for_user(uid)

    await update.message.reply_text("🔄 *جاري الإرسال...*", parse_mode="Markdown")

    # Determine event name pattern for custom level
    # Use a generic level event name pattern
    base_event_name = f"af_level_{level}_completed"

    status, resp = send_af(
        pkg=game.get("package", ""),
        dev_key=game.get("dev_key", ""),
        gaid=context.user_data.get("af_gaid", ""),
        af_uid=context.user_data.get("af_uid", ""),
        event_name=base_event_name,
        revenue=None,
        proxy=dict(proxy_row) if proxy_row else None,
        platform=platform,
        idfa=context.user_data.get("af_idfa"),
        idfv=context.user_data.get("af_idfv"),
        level=level,
    )

    result_text = _result_text(status, resp)

    if status == 200:
        confirm_usage(uid)
        result_text += "\n\n📊 *تم احتساب العملية*"
    else:
        rollback_usage(uid)
        result_text += "\n\n📊 *لم يتم احتساب العملية (فشل الإرسال)*"

    kb = [
        [InlineKeyboardButton("🎯 حدث آخر", callback_data=f"af_game_{game.get('id')}")],
        [InlineKeyboardButton("🔙 قائمة الألعاب", callback_data="af_menu")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
    ]
    await update.message.reply_text(
        f"{result_text}\n\n📝 *الحدث:* Level {level}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def af_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.replace("af_send_", ""))

    game_id = context.user_data.get("af_game_id")
    if not game_id:
        await query.edit_message_text(
            "❌ *انتهت الجلسة. ابدأ من جديد.*",
            parse_mode="Markdown",
            reply_markup=_back_kb("af_menu"),
        )
        return

    events = db.get_af_events(game_id)
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        await query.edit_message_text("❌ خطأ: الحدث غير موجود", parse_mode="Markdown")
        return

    game = context.user_data.get("af_game", {})
    uid = update.effective_user.id

    # Check and reserve usage slot before sending
    from src.config import ADMIN_IDS
    if uid not in ADMIN_IDS:
            if not check_and_reserve_usage(uid):
                sub = db.get_active_subscription(uid)
                used = sub.get("daily_used", 0) if sub else 0
                limit = sub.get("daily_limit", 0) if sub else 0
                await query.edit_message_text(
                    f"⚠️ *تم استنفاد الحد اليومي*\n\n📊 الاستخدام: `{used}/{limit}`\n\nيرجى الانتظار حتى الغد أو ترقية اشتراكك.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📦 اشتراك", callback_data="sub_menu")],
                        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
                    ]),
                )
                return

    platform = db.get_user_platform(uid)
    proxy_row = db.get_proxy_for_user(uid)

    await query.edit_message_text("🔄 *جاري الإرسال...*", parse_mode="Markdown")

    status, resp = send_af(
        pkg=game.get("package", ""),
        dev_key=game.get("dev_key", ""),
        gaid=context.user_data.get("af_gaid", ""),
        af_uid=context.user_data.get("af_uid", ""),
        event_name=event["event_name"],
        revenue=event.get("revenue"),
        proxy=dict(proxy_row) if proxy_row else None,
        platform=platform,
        idfa=context.user_data.get("af_idfa"),
        idfv=context.user_data.get("af_idfv"),
        level=event.get("level_value"),
    )

    result_text = _result_text(status, resp)

    # Only count operation if successful (already reserved), rollback on failure
    if status == 200:
        confirm_usage(uid)
        result_text += "\n\n📊 *تم احتساب العملية*"
    else:
        rollback_usage(uid)
        result_text += "\n\n📊 *لم يتم احتساب العملية (فشل الإرسال)*"

    kb = [
        [InlineKeyboardButton("🎯 حدث آخر", callback_data=f"af_game_{game.get('id')}")],
        [InlineKeyboardButton("🔙 قائمة الألعاب", callback_data="af_menu")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        f"{result_text}\n\n📝 *الحدث:* {event['display_name']}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


def get_handlers():
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(af_menu, pattern="^af_menu$"),
            CallbackQueryHandler(af_game, pattern=r"^af_game_\d+$"),
        ],
        states={
            AF_GAID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, af_gaid)],
            AF_IDFA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, af_idfa)],
            AF_IDFV:    [MessageHandler(filters.TEXT & ~filters.COMMAND, af_idfv)],
            AF_UID:     [MessageHandler(filters.TEXT & ~filters.COMMAND, af_uid)],
            AF_UID_IOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_uid_ios)],
            AF_CUSTOM_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_custom_level_entered)],
        },
        fallbacks=[CallbackQueryHandler(af_menu, pattern="^af_menu$")],
        allow_reentry=True,
    )
    return [
        conv,
        CallbackQueryHandler(af_send, pattern=r"^af_send_\d+$"),
        CallbackQueryHandler(af_custom_event_prompt, pattern="^af_custom_event$"),
    ]
