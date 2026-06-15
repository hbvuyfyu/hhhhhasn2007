import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access
from src.services.appsflyer import send_af
from src.services.adjust import send_adj
from src.services.singular import send_singular

logger = logging.getLogger(__name__)

# States — use range 400-420 to avoid clashes
(
    FARM_GAID, FARM_IDFA_AF, FARM_IDFV_AF, FARM_AF_UID, FARM_AF_UID_IOS,
    FARM_GPS_ADID, FARM_IDFA_ADJ, FARM_IDFV_ADJ,
    FARM_AIFA, FARM_IDFA_SNG, FARM_IDFV_SNG, FARM_SNG_UID, FARM_SNG_UID_IOS,
    FARM_START_LEVEL, FARM_END_LEVEL, FARM_TOTAL_DAYS, FARM_MODE_SELECT,
    FARM_CONFIRM, FARM_STOP_SELECT,
) = range(400, 419)

LEVELS_PER_DAY = {"safe": 1, "normal": 3, "fast": 5}


def _back_kb(data: str = "jumper_farm") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=data)]])


# ==================== Farm main menu ====================

@require_access
async def jumper_farm_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("🌱 مزرعة جديدة", callback_data="farm_new")],
        [InlineKeyboardButton("📋 مزارعي", callback_data="farm_list")],
        [InlineKeyboardButton("⏹️ إيقاف مزرعة", callback_data="farm_stop")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "🌾 *مزرعة الجمبرة*\n\nاختر العملية:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def farm_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    tasks = db.get_active_farm_tasks(uid)
    if not tasks:
        await query.edit_message_text(
            "📋 *لا توجد مزارع نشطة*",
            parse_mode="Markdown",
            reply_markup=_back_kb(),
        )
        return

    mode_names = {"safe": "🛡️ آمن", "normal": "⚡ عادي", "fast": "🚀 سريع"}
    txt = "📋 *مزارعك النشطة:*\n\n"
    for t in tasks:
        mode_display = mode_names.get(t.get("mode", "normal"), t.get("mode", ""))
        txt += (
            f"• *{t['task_name']}*\n"
            f"  🎮 {t['game_name']}\n"
            f"  🎯 {t['start_level']} → {t['end_level']} (حالياً {t['current_level']})\n"
            f"  📊 {t['current_day']}/{t['total_days']} أيام\n"
            f"  ⚙️ {mode_display}\n\n"
        )
    kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="jumper_farm")]]
    await query.edit_message_text(txt[:4000], reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@require_access
async def farm_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    tasks = db.get_stoppable_tasks(uid)
    if not tasks:
        await query.edit_message_text(
            "📋 *لا توجد مزارع نشطة للإيقاف*",
            parse_mode="Markdown",
            reply_markup=_back_kb(),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(f"⏹️ {t['task_name']}", callback_data=f"farm_stop_task_{t['id']}")]
        for t in tasks
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="jumper_farm")])
    await query.edit_message_text(
        "⏹️ *اختر المزرعة لإيقافها*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return FARM_STOP_SELECT


@require_access
async def farm_stop_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.replace("farm_stop_task_", ""))
    uid = update.effective_user.id
    db.stop_farm_task(task_id, uid)
    await query.edit_message_text(
        "✅ *تم إيقاف المزرعة بنجاح!*",
        parse_mode="Markdown",
        reply_markup=_back_kb(),
    )
    return ConversationHandler.END


@require_access
async def farm_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="farm_platform_af")],
        [InlineKeyboardButton("📊 Adjust", callback_data="farm_platform_adj")],
        [InlineKeyboardButton("🌟 Singular", callback_data="farm_platform_singular")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="jumper_farm")],
    ]
    await query.edit_message_text(
        "🌾 *اختر المنصة*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def farm_platform_af(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["farm_platform"] = "af"
    games = db.get_all_games_af()
    if not games:
        await query.edit_message_text("❌ *لا توجد ألعاب AppsFlyer*", parse_mode="Markdown", reply_markup=_back_kb())
        return
    kb = [
        [InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"farm_game_af_{g['id']}")]
        for g in games
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="farm_new")])
    await query.edit_message_text(
        "🎮 *اختر اللعبة*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def farm_platform_adj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["farm_platform"] = "adj"
    games = db.get_all_games_adj()
    if not games:
        await query.edit_message_text("❌ *لا توجد ألعاب Adjust*", parse_mode="Markdown", reply_markup=_back_kb())
        return
    kb = [
        [InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"farm_game_adj_{g['id']}")]
        for g in games
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="farm_new")])
    await query.edit_message_text(
        "🎮 *اختر اللعبة*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def farm_platform_singular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["farm_platform"] = "singular"
    games = db.get_all_games_singular()
    if not games:
        await query.edit_message_text("❌ *لا توجد ألعاب Singular*", parse_mode="Markdown", reply_markup=_back_kb())
        return
    kb = [
        [InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"farm_game_singular_{g['id']}")]
        for g in games
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="farm_new")])
    await query.edit_message_text(
        "🎮 *اختر اللعبة*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


# ==================== Game selection — entry_point for conversation ====================

@require_access
async def farm_game_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = update.effective_user.id
    platform_os = db.get_user_platform(uid)

    if data.startswith("farm_game_af_"):
        gid = int(data.replace("farm_game_af_", ""))
        game = db.get_game_af_by_id(gid)
        context.user_data["farm_platform"] = "af"
        context.user_data["farm_game_id"] = gid
        context.user_data["farm_game_name"] = game["display_name"] if game else ""
        if platform_os == "ios":
            await query.edit_message_text(
                f"🍎 *iOS - AppsFlyer*\n🎮 {context.user_data['farm_game_name']}\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
                parse_mode="Markdown",
            )
            return FARM_IDFA_AF
        else:
            await query.edit_message_text(
                f"🤖 *Android - AppsFlyer*\n🎮 {context.user_data['farm_game_name']}\n\n📱 *أدخل GAID:*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
                parse_mode="Markdown",
            )
            return FARM_GAID

    elif data.startswith("farm_game_adj_"):
        gid = int(data.replace("farm_game_adj_", ""))
        game = db.get_game_adj_by_id(gid)
        context.user_data["farm_platform"] = "adj"
        context.user_data["farm_game_id"] = gid
        context.user_data["farm_game_name"] = game["display_name"] if game else ""
        if platform_os == "ios":
            await query.edit_message_text(
                f"🍎 *iOS - Adjust*\n🎮 {context.user_data['farm_game_name']}\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
                parse_mode="Markdown",
            )
            return FARM_IDFA_ADJ
        else:
            await query.edit_message_text(
                f"🤖 *Android - Adjust*\n🎮 {context.user_data['farm_game_name']}\n\n📱 *أدخل GPS ADID:*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
                parse_mode="Markdown",
            )
            return FARM_GPS_ADID

    elif data.startswith("farm_game_singular_"):
        gid = int(data.replace("farm_game_singular_", ""))
        game = db.get_game_singular_by_id(gid)
        context.user_data["farm_platform"] = "singular"
        context.user_data["farm_game_id"] = gid
        context.user_data["farm_game_name"] = game["display_name"] if game else ""
        if platform_os == "ios":
            await query.edit_message_text(
                f"🍎 *iOS - Singular*\n🎮 {context.user_data['farm_game_name']}\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
                parse_mode="Markdown",
            )
            return FARM_IDFA_SNG
        else:
            await query.edit_message_text(
                f"🤖 *Android - Singular*\n🎮 {context.user_data['farm_game_name']}\n\n📱 *أدخل AIFA (GAID):*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
                parse_mode="Markdown",
            )
            return FARM_AIFA

    return ConversationHandler.END


# ==================== AF device IDs ====================

@require_access
async def farm_gaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_gaid"] = update.message.text.strip()
    await update.message.reply_text(
        "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`",
        parse_mode="Markdown",
    )
    return FARM_AF_UID


@require_access
async def farm_idfa_af(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_idfa"] = update.message.text.strip()
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return FARM_IDFV_AF


@require_access
async def farm_idfv_af(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_idfv"] = update.message.text.strip()
    await update.message.reply_text(
        "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`",
        parse_mode="Markdown",
    )
    return FARM_AF_UID_IOS


@require_access
async def farm_af_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_af_uid"] = update.message.text.strip()
    return await _ask_start_level(update)


@require_access
async def farm_af_uid_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_af_uid"] = update.message.text.strip()
    return await _ask_start_level(update)


# ==================== ADJ device IDs ====================

@require_access
async def farm_gps_adid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_gps"] = update.message.text.strip()
    return await _ask_start_level(update)


@require_access
async def farm_idfa_adj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_idfa"] = update.message.text.strip()
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return FARM_IDFV_ADJ


@require_access
async def farm_idfv_adj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_idfv"] = update.message.text.strip()
    return await _ask_start_level(update)


# ==================== Singular device IDs ====================

@require_access
async def farm_aifa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_aifa"] = update.message.text.strip()
    await update.message.reply_text(
        "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id_123`",
        parse_mode="Markdown",
    )
    return FARM_SNG_UID


@require_access
async def farm_idfa_singular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_idfa"] = update.message.text.strip()
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return FARM_IDFV_SNG


@require_access
async def farm_idfv_singular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_idfv"] = update.message.text.strip()
    await update.message.reply_text(
        "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id_123`",
        parse_mode="Markdown",
    )
    return FARM_SNG_UID_IOS


@require_access
async def farm_singular_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_singular_uid"] = update.message.text.strip()
    return await _ask_start_level(update)


@require_access
async def farm_singular_uid_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["farm_singular_uid"] = update.message.text.strip()
    return await _ask_start_level(update)


# ==================== Level & days ====================

async def _ask_start_level(update: Update) -> int:
    await update.message.reply_text(
        "🔢 *مستوى البداية:*\nمثال: `1`",
        parse_mode="Markdown",
    )
    return FARM_START_LEVEL


@require_access
async def farm_start_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sl = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return FARM_START_LEVEL
    context.user_data["farm_start"] = sl
    await update.message.reply_text(
        f"🔢 *مستوى النهاية:* (يجب أن يكون أكبر من {sl})\nمثال: `50`",
        parse_mode="Markdown",
    )
    return FARM_END_LEVEL


@require_access
async def farm_end_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        el = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return FARM_END_LEVEL
    sl = context.user_data.get("farm_start", 1)
    if el <= sl:
        await update.message.reply_text(
            f"❌ *يجب أن يكون أكبر من {sl}*",
            parse_mode="Markdown",
        )
        return FARM_END_LEVEL
    context.user_data["farm_end"] = el
    total = el - sl
    await update.message.reply_text(
        f"📅 *عدد الأيام:* (إجمالي {total} مستوى)\nمثال: `7`",
        parse_mode="Markdown",
    )
    return FARM_TOTAL_DAYS


@require_access
async def farm_total_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return FARM_TOTAL_DAYS
    if days <= 0:
        await update.message.reply_text("❌ *عدد الأيام يجب أن يكون أكبر من 0*", parse_mode="Markdown")
        return FARM_TOTAL_DAYS
    context.user_data["farm_days"] = days

    sl = context.user_data.get("farm_start", 1)
    el = context.user_data.get("farm_end", 10)
    total_levels = el - sl

    kb = [
        [InlineKeyboardButton("🛡️ آمن (1 لفل/يوم)", callback_data="farm_mode_safe")],
        [InlineKeyboardButton("⚡ عادي (3 لفل/يوم)", callback_data="farm_mode_normal")],
        [InlineKeyboardButton("🚀 سريع (5 لفل/يوم)", callback_data="farm_mode_fast")],
    ]
    await update.message.reply_text(
        f"⚙️ *اختر وضع الزراعة*\n\n"
        f"📊 المستويات: {sl} → {el} ({total_levels} مستوى)\n"
        f"📅 الأيام: {days}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return FARM_MODE_SELECT


@require_access
async def farm_mode_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data.replace("farm_mode_", "")
    context.user_data["farm_mode"] = mode

    mode_names = {"safe": "🛡️ آمن (1/يوم)", "normal": "⚡ عادي (3/يوم)", "fast": "🚀 سريع (5/يوم)"}
    mode_display = mode_names.get(mode, mode)

    sl = context.user_data.get("farm_start", 1)
    el = context.user_data.get("farm_end", 10)
    total_levels = el - sl

    kb = [
        [InlineKeyboardButton("✅ تأكيد وبدء الزراعة", callback_data="farm_confirm_start")],
        [InlineKeyboardButton("🔙 إلغاء", callback_data="jumper_farm")],
    ]
    await query.edit_message_text(
        f"🌾 *تأكيد المزرعة*\n\n"
        f"🎮 {context.user_data.get('farm_game_name', '')}\n"
        f"🎯 المستويات: {sl} → {el} ({total_levels} مستوى)\n"
        f"📅 الأيام: {context.user_data.get('farm_days', 1)}\n"
        f"⚙️ الوضع: {mode_display}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return FARM_CONFIRM


@require_access
async def farm_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    task_name = f"{context.user_data.get('farm_game_name', 'farm')}_{datetime.now().strftime('%m%d%H%M')}"

    task_id = db.create_farm_task(
        user_id=uid,
        task_name=task_name,
        platform=context.user_data.get("farm_platform", "af"),
        game_id=context.user_data.get("farm_game_id", 0),
        game_name=context.user_data.get("farm_game_name", ""),
        start_level=context.user_data.get("farm_start", 1),
        end_level=context.user_data.get("farm_end", 10),
        total_days=context.user_data.get("farm_days", 1),
        mode=context.user_data.get("farm_mode", "normal"),
        aifa=context.user_data.get("farm_aifa", ""),
        gaid=context.user_data.get("farm_gaid", ""),
        af_uid=context.user_data.get("farm_af_uid", ""),
        gps_adid=context.user_data.get("farm_gps", ""),
        idfa=context.user_data.get("farm_idfa", ""),
        idfv=context.user_data.get("farm_idfv", ""),
        singular_uid=context.user_data.get("farm_singular_uid", ""),
    )

    kb = [[InlineKeyboardButton("🔙 المزرعة", callback_data="jumper_farm")]]
    await query.edit_message_text(
        f"✅ *تم بدء المزرعة!*\n\n🌾 *{task_name}*\n🆔 `{task_id}`",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

    if task_id:
        asyncio.get_event_loop().create_task(
            run_farm_task(task_id, query.message.chat_id, context)
        )

    return ConversationHandler.END


# ==================== Farm background runner ====================

async def run_farm_task(task_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    task = db.get_farm_task_by_id(task_id)
    if not task:
        return

    platform = task["platform"]
    mode = task.get("mode", "normal")
    levels_per_day = LEVELS_PER_DAY.get(mode, 3)
    delay_seconds = 86400 / levels_per_day
    current_level = task["current_level"]
    end_level = task["end_level"]
    game_id = task["game_id"]

    while True:
        fresh = db.get_farm_task_by_id(task_id)
        if not fresh or fresh["status"] != "running":
            break
        if current_level >= end_level:
            db.complete_farm_task(task_id)
            try:
                await context.bot.send_message(
                    chat_id,
                    f"✅ *اكتملت المزرعة!*\n🌾 {task['task_name']}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            break

        proxy_row = db.get_proxy_for_user(task["user_id"])
        proxy = dict(proxy_row) if proxy_row else None
        status = 0

        try:
            is_ios = bool(task.get("idfa"))
            plat = "ios" if is_ios else "android"

            if platform == "af":
                game = db.get_game_af_by_id(game_id)
                events = db.get_af_events(game_id)
                ev = events[0] if events else None
                if game and ev:
                    status, _ = send_af(
                        pkg=game["package"], dev_key=game["dev_key"],
                        gaid=task["gaid"], af_uid=task["af_uid"],
                        event_name=ev["event_name"], revenue=ev.get("revenue"),
                        proxy=proxy, platform=plat,
                        idfa=task["idfa"] or None, idfv=task["idfv"] or None,
                        level=current_level,
                    )
            elif platform == "adj":
                game = db.get_game_adj_by_id(game_id)
                events = db.get_adj_events(game_id)
                ev = events[0] if events else None
                if game and ev:
                    status, _ = send_adj(
                        app_token=game["app_token"], event_token=ev["event_token"],
                        gps_adid=task["gps_adid"], proxy=proxy, platform=plat,
                        idfa=task["idfa"] or None, idfv=task["idfv"] or None,
                        level=current_level,
                    )
            elif platform == "singular":
                game = db.get_game_singular_by_id(game_id)
                events = db.get_singular_events(game_id)
                ev = events[0] if events else None
                if game and ev:
                    status, _ = send_singular(
                        event_name=ev["event_name"], aifa=task["aifa"],
                        uid=task["singular_uid"] or "", package=game["package"],
                        app_key=game["app_key"], level=current_level,
                        proxy=proxy, platform=plat,
                        idfa=task["idfa"] or None, idfv=task["idfv"] or None,
                        singular_uid=task["singular_uid"] or None,
                    )

            emoji = "✅" if status == 200 else "❌"
            logger.info(f"[FARM {task_id}] Level {current_level}: {emoji} status={status}")
            current_level += 1
            db.update_farm_task_level(task_id, current_level, fresh.get("current_day", 1) + 1)

        except Exception as e:
            logger.error(f"[FARM {task_id}] Error at level {current_level}: {e}")

        await asyncio.sleep(delay_seconds)


def get_handlers():
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(jumper_farm_menu, pattern="^jumper_farm$"),
            # Game selection triggers the conversation for device ID input
            CallbackQueryHandler(farm_game_select, pattern=r"^farm_game_(af|adj|singular)_\d+$"),
            # Stop farm also needs conversation for the selection step
            CallbackQueryHandler(farm_stop, pattern="^farm_stop$"),
        ],
        states={
            FARM_GAID:        [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_gaid)],
            FARM_IDFA_AF:     [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_idfa_af)],
            FARM_IDFV_AF:     [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_idfv_af)],
            FARM_AF_UID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_af_uid)],
            FARM_AF_UID_IOS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_af_uid_ios)],
            FARM_GPS_ADID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_gps_adid)],
            FARM_IDFA_ADJ:    [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_idfa_adj)],
            FARM_IDFV_ADJ:    [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_idfv_adj)],
            FARM_AIFA:        [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_aifa)],
            FARM_IDFA_SNG:    [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_idfa_singular)],
            FARM_IDFV_SNG:    [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_idfv_singular)],
            FARM_SNG_UID:     [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_singular_uid)],
            FARM_SNG_UID_IOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_singular_uid_ios)],
            FARM_START_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_start_level)],
            FARM_END_LEVEL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_end_level)],
            FARM_TOTAL_DAYS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, farm_total_days)],
            FARM_MODE_SELECT: [CallbackQueryHandler(farm_mode_select, pattern=r"^farm_mode_")],
            FARM_CONFIRM:     [CallbackQueryHandler(farm_confirm, pattern="^farm_confirm_start$")],
            FARM_STOP_SELECT: [CallbackQueryHandler(farm_stop_task, pattern=r"^farm_stop_task_\d+$")],
        },
        fallbacks=[CallbackQueryHandler(jumper_farm_menu, pattern="^jumper_farm$")],
        allow_reentry=True,
    )
    return [
        conv,
        # These are pure navigation — no conversation state needed
        CallbackQueryHandler(farm_list, pattern="^farm_list$"),
        CallbackQueryHandler(farm_new, pattern="^farm_new$"),
        CallbackQueryHandler(farm_platform_af, pattern="^farm_platform_af$"),
        CallbackQueryHandler(farm_platform_adj, pattern="^farm_platform_adj$"),
        CallbackQueryHandler(farm_platform_singular, pattern="^farm_platform_singular$"),
    ]
