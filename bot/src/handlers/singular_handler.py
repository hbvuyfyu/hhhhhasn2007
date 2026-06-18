import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access, check_and_reserve_usage, confirm_usage, rollback_usage
from src.services.singular import send_singular
from src.utils.navigation import nav_push, nav_clear, nav_add_back_row

logger = logging.getLogger(__name__)

SNG_AIFA, SNG_IDFA, SNG_IDFV, SNG_UID, SNG_UID_IOS, SNG_EVENTS, SNG_CUSTOM_LEVEL, SNG_CUSTOM_CONFIRM, SNG_CUSTOM_EVENT_NAME, SNG_CUSTOM_EVENT_LEVEL = range(300, 311)


def _result_text(status: int, resp: str) -> str:
    if status == 200:
        return "✅ *تم الإرسال بنجاح!*"
    return f"❌ *فشل الإرسال*\nالكود: `{status}`\n`{resp[:200]}`"


def _back_kb(data: str = "singular_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="go_back"), InlineKeyboardButton("🏠 القائمة", callback_data="main_menu")]
    ])


@require_access
async def singular_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nav_push(context, "main_menu")
    games = db.get_all_games_singular()
    if not games:
        await query.edit_message_text(
            "❌ *لا توجد ألعاب Singular*",
            parse_mode="Markdown",
            reply_markup=_back_kb("main_menu"),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"sg_game_{g['id']}")]
        for g in games
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text(
        "🌟 *اختر اللعبة - Singular*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def singular_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nav_push(context, "singular_menu")
    game_id = int(query.data.replace("sg_game_", ""))
    game = db.get_game_singular_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ خطأ: اللعبة غير موجودة", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["sg_game_id"] = game_id
    context.user_data["sg_game"] = dict(game)
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)

    if platform == "ios":
        await query.edit_message_text(
            f"🍎 *iOS - Singular*\n🎮 {game['display_name']}\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
            parse_mode="Markdown",
        )
        return SNG_IDFA
    else:
        await query.edit_message_text(
            f"🤖 *Android - Singular*\n🎮 {game['display_name']}\n\n📱 *أدخل AIFA (GAID):*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
            parse_mode="Markdown",
        )
        return SNG_AIFA


@require_access
async def singular_aifa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_aifa"] = update.message.text.strip()
    await update.message.reply_text(
        "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id_123`",
        parse_mode="Markdown",
    )
    return SNG_UID


@require_access
async def singular_idfa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_idfa"] = update.message.text.strip()
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return SNG_IDFV


@require_access
async def singular_idfv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_idfv"] = update.message.text.strip()
    await update.message.reply_text(
        "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id_123`",
        parse_mode="Markdown",
    )
    return SNG_UID_IOS


@require_access
async def singular_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_uid"] = update.message.text.strip()
    return await _show_singular_events(update, context)


@require_access
async def singular_uid_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_uid"] = update.message.text.strip()
    return await _show_singular_events(update, context)


async def _show_singular_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_id = context.user_data.get("sg_game_id")
    game = context.user_data.get("sg_game", {})
    events = db.get_singular_events(game_id)
    if not events:
        await update.message.reply_text(
            "❌ *لا توجد أحداث لهذه اللعبة*",
            parse_mode="Markdown",
            reply_markup=_back_kb("singular_menu"),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(ev["display_name"], callback_data=f"sg_send_{ev['id']}")]
        for ev in events
    ]
    kb.append([InlineKeyboardButton("🎯 لفل مخصص", callback_data="sg_custom_level")])
    kb.append([InlineKeyboardButton("📝 حدث مخصص", callback_data="sg_custom_event_start")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="singular_menu")])
    await update.message.reply_text(
        f"🎯 *اختر الحدث*\n🎮 {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return SNG_EVENTS


@require_access
async def singular_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.replace("sg_send_", ""))

    game_id = context.user_data.get("sg_game_id")
    if not game_id:
        await query.edit_message_text(
            "❌ *انتهت الجلسة. ابدأ من جديد.*",
            parse_mode="Markdown",
            reply_markup=_back_kb("singular_menu"),
        )
        return

    events = db.get_singular_events(game_id)
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        await query.edit_message_text("❌ خطأ: الحدث غير موجود", parse_mode="Markdown")
        return

    game = context.user_data.get("sg_game", {})
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

    status, resp = send_singular(
        event_name=event["event_name"],
        aifa=context.user_data.get("sg_aifa", ""),
        uid=context.user_data.get("sg_uid", ""),
        package=game.get("package", ""),
        app_key=game.get("app_key", ""),
        level=event.get("level_value"),
        proxy=dict(proxy_row) if proxy_row else None,
        platform=platform,
        idfa=context.user_data.get("sg_idfa"),
        idfv=context.user_data.get("sg_idfv"),
        singular_uid=context.user_data.get("sg_uid"),
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
        [InlineKeyboardButton("🎯 حدث آخر", callback_data=f"sg_game_{game.get('id')}")],
        [InlineKeyboardButton("🔙 قائمة الألعاب", callback_data="singular_menu")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        f"{result_text}\n\n📝 *الحدث:* {event['display_name']}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def singular_custom_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show events list for custom level selection."""
    query = update.callback_query
    await query.answer()
    game_id = context.user_data.get("sg_game_id")
    events = db.get_singular_events(game_id)
    if not events:
        await query.edit_message_text(
            "❌ *لا توجد أحداث لهذه اللعبة*",
            parse_mode="Markdown",
            reply_markup=_back_kb("singular_menu"),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(ev["display_name"], callback_data=f"sg_custom_evt_{ev['id']}")]
        for ev in events
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"sg_game_{game_id}")])
    await query.edit_message_text(
        "🎯 *اختر الحدث للفل المخصص*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def singular_custom_evt_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for custom level value."""
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.replace("sg_custom_evt_", ""))
    context.user_data["sg_custom_event_id"] = event_id
    await query.edit_message_text(
        "📊 *أدخل الفل المخصص:*\nمثال: `15` أو `20`",
        parse_mode="Markdown",
    )
    return SNG_CUSTOM_LEVEL


@require_access
async def singular_custom_level_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom level input and show confirmation."""
    try:
        level = int(update.message.text.strip())
        if level < 1:
            raise ValueError("Level must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ *أدخل رقماً صحيحاً موجباً*",
            parse_mode="Markdown",
        )
        return SNG_CUSTOM_LEVEL

    context.user_data["sg_custom_level"] = level
    event_id = context.user_data.get("sg_custom_event_id")
    game_id = context.user_data.get("sg_game_id")
    events = db.get_singular_events(game_id)
    event = next((e for e in events if e["id"] == event_id), None)
    game = context.user_data.get("sg_game", {})

    if not event:
        await update.message.reply_text(
            "❌ خطأ: الحدث غير موجود",
            parse_mode="Markdown",
            reply_markup=_back_kb("singular_menu"),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton("✅ تأكيد", callback_data="sg_custom_confirm")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"sg_game_{game_id}")],
    ]
    await update.message.reply_text(
        f"🎯 *تأكيد الفل المخصص*\n\n🎮 اللعبة: {game.get('display_name', '')}\n📝 الحدث: {event['display_name']}\n📊 الفل: `{level}`",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return SNG_CUSTOM_CONFIRM


@require_access
async def singular_custom_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send event with custom level."""
    query = update.callback_query
    await query.answer()

    event_id = context.user_data.get("sg_custom_event_id")
    game_id = context.user_data.get("sg_game_id")
    if not game_id:
        await query.edit_message_text(
            "❌ *انتهت الجلسة. ابدأ من جديد.*",
            parse_mode="Markdown",
            reply_markup=_back_kb("singular_menu"),
        )
        return

    events = db.get_singular_events(game_id)
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        await query.edit_message_text("❌ خطأ: الحدث غير موجود", parse_mode="Markdown")
        return

    game = context.user_data.get("sg_game", {})
    uid = update.effective_user.id
    custom_level = context.user_data.get("sg_custom_level", 1)

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

    status, resp = send_singular(
        event_name=event["event_name"],
        aifa=context.user_data.get("sg_aifa", ""),
        uid=context.user_data.get("sg_uid", ""),
        package=game.get("package", ""),
        app_key=game.get("app_key", ""),
        level=custom_level,
        proxy=dict(proxy_row) if proxy_row else None,
        platform=platform,
        idfa=context.user_data.get("sg_idfa"),
        idfv=context.user_data.get("sg_idfv"),
        singular_uid=context.user_data.get("sg_uid"),
    )

    result_text = _result_text(status, resp)

    if status == 200:
        confirm_usage(uid)
        result_text += "\n\n📊 *تم احتساب العملية*"
    else:
        rollback_usage(uid)
        result_text += "\n\n📊 *لم يتم احتساب العملية (فشل الإرسال)*"

    kb = [
        [InlineKeyboardButton("🎯 حدث آخر", callback_data=f"sg_game_{game.get('id')}")],
        [InlineKeyboardButton("🔙 قائمة الألعاب", callback_data="singular_menu")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        f"{result_text}\n\n📝 *الحدث:* {event['display_name']}\n📊 *الفل المخصص:* {custom_level}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


# ==================== Custom Event (اسم حدث مخصص) ====================

@require_access
async def singular_custom_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user for custom event name."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *أدخل اسم الحدث المخصص:*\nمثال: `level_complete` أو `purchase`",
        parse_mode="Markdown",
    )
    return SNG_CUSTOM_EVENT_NAME


@require_access
async def singular_custom_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store event name and ask for level."""
    event_name = update.message.text.strip()
    context.user_data["sg_custom_event_name"] = event_name
    await update.message.reply_text(
        "📊 *أدخل رقم الفل:*\nمثال: `15` أو `20`",
        parse_mode="Markdown",
    )
    return SNG_CUSTOM_EVENT_LEVEL


@require_access
async def singular_custom_event_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle level input and show confirmation."""
    try:
        level = int(update.message.text.strip())
        if level < 1:
            raise ValueError("Level must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ *أدخل رقماً صحيحاً موجباً*",
            parse_mode="Markdown",
        )
        return SNG_CUSTOM_EVENT_LEVEL

    context.user_data["sg_custom_event_level"] = level
    game = context.user_data.get("sg_game", {})
    event_name = context.user_data.get("sg_custom_event_name", "")

    kb = [
        [InlineKeyboardButton("✅ تأكيد الإرسال", callback_data="sg_custom_event_send")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"sg_game_{game.get('id')}")],
    ]
    await update.message.reply_text(
        f"🎯 *تأكيد الحدث المخصص*\n\n🎮 اللعبة: {game.get('display_name', '')}\n📝 اسم الحدث: `{event_name}`\n📊 الفل: `{level}`",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def singular_custom_event_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send custom event with custom name and level."""
    query = update.callback_query
    await query.answer()

    game_id = context.user_data.get("sg_game_id")
    if not game_id:
        await query.edit_message_text(
            "❌ *انتهت الجلسة. ابدأ من جديد.*",
            parse_mode="Markdown",
            reply_markup=_back_kb("singular_menu"),
        )
        return

    game = context.user_data.get("sg_game", {})
    uid = update.effective_user.id
    event_name = context.user_data.get("sg_custom_event_name", "")
    custom_level = context.user_data.get("sg_custom_event_level", 1)

    # Check and reserve usage slot
    from src.config import ADMIN_IDS
    if uid not in ADMIN_IDS:
        if not check_and_reserve_usage(uid):
            sub = db.get_active_subscription(uid)
            used = sub.get("daily_used", 0) if sub else 0
            limit = sub.get("daily_limit", 0) if sub else 0
            await query.edit_message_text(
                f"⚠️ *تم استنفاد الحد اليومي*\n\n📊 الاستخدام: `{used}/{limit}`",
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

    status, resp = send_singular(
        event_name=event_name,
        aifa=context.user_data.get("sg_aifa", ""),
        uid=context.user_data.get("sg_uid", ""),
        package=game.get("package", ""),
        app_key=game.get("app_key", ""),
        level=custom_level,
        proxy=dict(proxy_row) if proxy_row else None,
        platform=platform,
        idfa=context.user_data.get("sg_idfa"),
        idfv=context.user_data.get("sg_idfv"),
        singular_uid=context.user_data.get("sg_uid"),
    )

    result_text = _result_text(status, resp)

    if status == 200:
        confirm_usage(uid)
        result_text += "\n\n📊 *تم احتساب العملية*"
    else:
        rollback_usage(uid)
        result_text += "\n\n📊 *لم يتم احتساب العملية (فشل الإرسال)*"

    kb = [
        [InlineKeyboardButton("🎯 حدث آخر", callback_data=f"sg_game_{game.get('id')}")],
        [InlineKeyboardButton("🔙 قائمة الألعاب", callback_data="singular_menu")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        f"{result_text}\n\n📝 *الحدث المخصص:* `{event_name}`\n📊 *الفل:* {custom_level}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


def get_handlers():
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(singular_menu, pattern="^singular_menu$"),
            CallbackQueryHandler(singular_game, pattern=r"^sg_game_\d+$"),
        ],
        states={
            SNG_AIFA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_aifa)],
            SNG_IDFA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_idfa)],
            SNG_IDFV:    [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_idfv)],
            SNG_UID:     [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_uid)],
            SNG_UID_IOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_uid_ios)],
            SNG_EVENTS: [
                CallbackQueryHandler(singular_send, pattern=r"^sg_send_\d+$"),
                CallbackQueryHandler(singular_custom_level, pattern="^sg_custom_level$"),
                CallbackQueryHandler(singular_custom_event_start, pattern="^sg_custom_event_start$"),
            ],
            SNG_CUSTOM_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_custom_level_input)],
            SNG_CUSTOM_CONFIRM: [CallbackQueryHandler(singular_custom_send, pattern="^sg_custom_confirm$")],
            SNG_CUSTOM_EVENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_custom_event_name)],
            SNG_CUSTOM_EVENT_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_custom_event_level)],
        },
        fallbacks=[CallbackQueryHandler(singular_menu, pattern="^singular_menu$")],
        allow_reentry=True,
    )
    return [
        conv,
        CallbackQueryHandler(singular_custom_evt_select, pattern=r"^sg_custom_evt_\d+$"),
        CallbackQueryHandler(singular_custom_event_send, pattern="^sg_custom_event_send$"),
    ]
