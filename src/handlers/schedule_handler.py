import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access
from src.utils.navigation import nav_push

logger = logging.getLogger(__name__)

# States — range 600-609 to avoid clashes with other handlers
(
    SCH_PLATFORM, SCH_GAME, SCH_EVENTS,
    SCH_INTERVAL, SCH_GAID, SCH_AF_UID, SCH_CONFIRM,
    SCH_CUSTOM_LEVEL,
) = range(600, 608)

_INTERVAL_LABELS = {15: "15 دقيقة", 25: "25 دقيقة", 60: "ساعة واحدة", 120: "ساعتان"}
_PLAT_LABELS = {"af": "📱 AppsFlyer", "adj": "📊 Adjust", "sg": "🌟 Singular"}


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data="go_back"),
        InlineKeyboardButton("🏠 القائمة", callback_data="main_menu"),
    ]])


@require_access
async def sched_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    nav_push(context, "main_menu")
    kb = [
        [InlineKeyboardButton("➕ مجموعة جديدة", callback_data="sched_new")],
        [InlineKeyboardButton("📋 مجموعاتي", callback_data="sched_list")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "🗓 *جدولة عمليات*\n\nاختر العملية:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def sched_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["sched"] = {}
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="sched_plat_af")],
        [InlineKeyboardButton("📊 Adjust", callback_data="sched_plat_adj")],
        [InlineKeyboardButton("🌟 Singular", callback_data="sched_plat_sg")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="sched_menu")],
    ]
    await query.edit_message_text(
        "🗓 *جدولة جديدة*\n\n📡 *اختر المنصة:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return SCH_PLATFORM


@require_access
async def sched_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plat_map = {"sched_plat_af": "af", "sched_plat_adj": "adj", "sched_plat_sg": "sg"}
    plat = plat_map.get(query.data)
    if not plat:
        return SCH_PLATFORM

    context.user_data.setdefault("sched", {})["platform"] = plat

    if plat == "af":
        games = db.get_all_games_af()
    elif plat == "adj":
        games = db.get_all_games_adj()
    else:
        games = db.get_all_games_singular()

    if not games:
        await query.edit_message_text(
            f"❌ *لا توجد ألعاب لـ {_PLAT_LABELS[plat]}*",
            parse_mode="Markdown",
            reply_markup=_back_kb(),
        )
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"sched_game_{g['id']}")]
        for g in games
    ]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="sched_new")])
    await query.edit_message_text(
        f"🗓 *{_PLAT_LABELS[plat]}*\n\n🎮 *اختر اللعبة:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return SCH_GAME


@require_access
async def sched_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = int(query.data.replace("sched_game_", ""))
    plat = context.user_data.get("sched", {}).get("platform", "af")

    if plat == "af":
        game = db.get_game_af_by_id(game_id)
        events = db.get_af_events(game_id)
    elif plat == "adj":
        game = db.get_game_adj_by_id(game_id)
        events = db.get_adj_events(game_id)
    else:
        game = db.get_game_singular_by_id(game_id)
        events = db.get_singular_events(game_id)

    if not game:
        await query.edit_message_text("❌ *اللعبة غير موجودة*", parse_mode="Markdown", reply_markup=_back_kb())
        return ConversationHandler.END

    if not events:
        await query.edit_message_text("❌ *لا توجد أحداث لهذه اللعبة*", parse_mode="Markdown", reply_markup=_back_kb())
        return ConversationHandler.END

    context.user_data["sched"]["game_id"] = game_id
    context.user_data["sched"]["game_name"] = game["display_name"]
    context.user_data["sched"]["events_pool"] = [dict(e) for e in events]
    context.user_data["sched"]["selected_events"] = []

    await _show_event_selection(query, context)
    return SCH_EVENTS


_PLAT_TYPE_MAP = {"af": "af", "adj": "adj", "sg": "singular"}


async def _show_event_selection(query, context: ContextTypes.DEFAULT_TYPE):
    sched = context.user_data["sched"]
    events_pool = sched["events_pool"]
    selected = sched["selected_events"]
    selected_ids = {e["id"]: idx + 1 for idx, e in enumerate(selected)}

    kb = []
    for ev in events_pool:
        num = selected_ids.get(ev["id"])
        label = f"✅ {num}. {ev['display_name']}" if num else f"⬜ {ev['display_name']}"
        kb.append([InlineKeyboardButton(label, callback_data=f"sched_ev_{ev['id']}")])

    # Add custom event button if enabled for this game
    plat = sched.get("platform", "af")
    game_type = _PLAT_TYPE_MAP.get(plat, plat)
    game_id = sched.get("game_id")
    if game_id and db.is_custom_event_enabled(game_type, game_id):
        kb.append([InlineKeyboardButton("🎯 إضافة لفل مخصص", callback_data="sched_custom_ev")])

    if selected:
        kb.append([InlineKeyboardButton("💾 حفظ الترتيب والمتابعة ◀", callback_data="sched_save_events")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="sched_new")])

    selected_text = ""
    if selected:
        lines = "\n".join(f"  {i+1}. {e['display_name']}" for i, e in enumerate(selected))
        selected_text = f"\n\n*الأحداث المختارة:*\n{lines}"

    await query.edit_message_text(
        f"🗓 *اختر الأحداث بالترتيب*\n🎮 {sched['game_name']}\n\n"
        f"اضغط على الحدث لإضافته — اضغط مجدداً لإلغائه{selected_text}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def sched_toggle_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = int(query.data.replace("sched_ev_", ""))
    sched = context.user_data.get("sched", {})
    events_pool = sched.get("events_pool", [])
    selected = sched.get("selected_events", [])

    event = next((e for e in events_pool if e["id"] == event_id), None)
    if not event:
        return SCH_EVENTS

    already = next((e for e in selected if e["id"] == event_id), None)
    if already:
        selected.remove(already)
    else:
        selected.append(dict(event))

    context.user_data["sched"]["selected_events"] = selected
    await _show_event_selection(query, context)
    return SCH_EVENTS


@require_access
async def sched_save_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected = context.user_data.get("sched", {}).get("selected_events", [])
    if not selected:
        await query.answer("⚠️ يرجى اختيار حدث واحد على الأقل", show_alert=True)
        return SCH_EVENTS

    kb = [
        [InlineKeyboardButton("⏱ 15 دقيقة", callback_data="sched_int_15")],
        [InlineKeyboardButton("⏱ 25 دقيقة", callback_data="sched_int_25")],
        [InlineKeyboardButton("⏱ 1 ساعة", callback_data="sched_int_60")],
        [InlineKeyboardButton("⏱ 2 ساعة", callback_data="sched_int_120")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="sched_back_to_events")],
    ]
    await query.edit_message_text(
        "⏱ *اختر الفاصل الزمني بين الأحداث:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return SCH_INTERVAL


@require_access
async def sched_back_to_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _show_event_selection(query, context)
    return SCH_EVENTS


@require_access
async def sched_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    minutes = int(query.data.replace("sched_int_", ""))
    context.user_data["sched"]["interval"] = minutes
    context.user_data["sched"]["interval_label"] = _INTERVAL_LABELS.get(minutes, f"{minutes} دقيقة")

    plat = context.user_data["sched"]["platform"]
    if plat == "adj":
        prompt = "📱 *أدخل GPS ADID:*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`"
    elif plat == "sg":
        prompt = "📱 *أدخل AIFA (GAID):*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`"
    else:
        prompt = "📱 *أدخل GAID:*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`"

    await query.edit_message_text(prompt, parse_mode="Markdown")
    return SCH_GAID


@require_access
async def sched_gaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gaid = update.message.text.strip()
    context.user_data["sched"]["gaid"] = gaid

    plat = context.user_data["sched"]["platform"]
    if plat == "adj":
        context.user_data["sched"]["af_uid"] = ""
        return await _show_sched_confirm(update, context)
    elif plat == "sg":
        prompt = "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id_123`"
    else:
        prompt = "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`"

    await update.message.reply_text(prompt, parse_mode="Markdown")
    return SCH_AF_UID


@require_access
async def sched_af_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sched"]["af_uid"] = update.message.text.strip()
    return await _show_sched_confirm(update, context)


async def _show_sched_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sched = context.user_data["sched"]
    plat_label = _PLAT_LABELS.get(sched["platform"], sched["platform"])
    selected = sched["selected_events"]
    n_events = len(selected)

    events_text = "\n".join(f"  {i+1}. {e['display_name']}" for i, e in enumerate(selected))
    af_uid_line = f"\n🆔 *AF UID / Custom ID:* `{sched['af_uid']}`" if sched.get("af_uid") else ""

    text = (
        f"📋 *تفاصيل الجدولة*\n\n"
        f"📡 *المنصة:* {plat_label}\n"
        f"🎮 *اللعبة:* {sched['game_name']}\n"
        f"🎯 *الأحداث بالترتيب:*\n{events_text}\n\n"
        f"⏱ *الفاصل الزمني:* {sched['interval_label']}\n"
        f"📱 *GAID:* `{sched['gaid']}`"
        f"{af_uid_line}\n\n"
        f"⚠️ سيتم خصم *{n_events} عملية* من رصيدك فور التأكيد."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد وبدء الجدولة", callback_data="sched_confirm")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="sched_menu")],
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    return SCH_CONFIRM


@require_access
async def sched_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    sched = context.user_data.get("sched", {})
    selected = sched.get("selected_events", [])
    n_events = len(selected)

    if not n_events:
        await query.edit_message_text("❌ *خطأ: لا توجد أحداث محددة*", parse_mode="Markdown")
        return ConversationHandler.END

    from src.config import ADMIN_IDS
    if uid not in ADMIN_IDS:
        sub = db.get_active_subscription(uid)
        if not sub:
            await query.edit_message_text(
                "⚠️ *غير مشترك*\n\nيرجى الاشتراك أولاً.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📦 اشتراك", callback_data="sub_menu"),
                ]]),
            )
            return ConversationHandler.END

        used = sub.get("daily_used", 0)
        limit = sub.get("daily_limit", 0)
        remaining = limit - used
        if remaining < n_events:
            await query.edit_message_text(
                f"⚠️ *رصيد غير كافٍ*\n\n"
                f"الأحداث المطلوبة: `{n_events}`\n"
                f"الرصيد المتبقي: `{remaining}`\n\n"
                f"يرجى ترقية اشتراكك أو تقليل عدد الأحداث.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📦 اشتراك", callback_data="sub_menu"),
                ]]),
            )
            return ConversationHandler.END

        for _ in range(n_events):
            db.increment_subscription_usage(uid)

    group_id = db.create_scheduled_group(
        user_id=uid,
        platform=sched["platform"],
        game_id=sched["game_id"],
        game_name=sched["game_name"],
        gaid=sched["gaid"],
        af_uid=sched.get("af_uid", ""),
        interval_minutes=sched["interval"],
        events=selected,
    )

    await query.edit_message_text(
        f"✅ *تم بدء الجدولة!*\n\n"
        f"🆔 رقم المجموعة: `{group_id}`\n"
        f"🎯 عدد الأحداث: `{n_events}`\n"
        f"⏱ الفاصل الزمني: {sched['interval_label']}\n\n"
        f"ستصلك إشعارات بعد كل عملية تلقائياً.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
        ]]),
    )

    asyncio.get_event_loop().create_task(
        run_scheduled_group(group_id, uid, context)
    )
    return ConversationHandler.END


@require_access
async def sched_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    groups = db.get_active_scheduled_groups(uid)

    if not groups:
        await query.edit_message_text(
            "📋 *لا توجد مجموعات نشطة*",
            parse_mode="Markdown",
            reply_markup=_back_kb(),
        )
        return ConversationHandler.END

    txt = "📋 *مجموعاتي النشطة:*\n\n"
    for g in groups:
        plat_label = _PLAT_LABELS.get(g["platform"], g["platform"])
        txt += (
            f"• *#{g['id']}* — {plat_label}\n"
            f"  🎮 {g['game_name']}\n"
            f"  ⏱ {g['interval_minutes']} دقيقة | "
            f"📍 {g['current_event_index']}/{g['total_events']} حدث\n\n"
        )

    kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="sched_menu")]]
    await query.edit_message_text(
        txt[:4000], reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return ConversationHandler.END


async def run_scheduled_group(group_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    group = db.get_scheduled_group_by_id(group_id)
    if not group:
        return

    events = db.get_scheduled_group_events(group_id)
    if not events:
        return

    proxy_row = db.get_proxy_for_user(group["user_id"])
    proxy = dict(proxy_row) if proxy_row else None
    platform = group["platform"]
    interval_seconds = group["interval_minutes"] * 60

    from src.services.appsflyer import send_af
    from src.services.adjust import send_adj
    from src.services.singular import send_singular

    for i, event in enumerate(events):
        fresh = db.get_scheduled_group_by_id(group_id)
        if not fresh or fresh["status"] != "active":
            break

        if i > 0:
            await asyncio.sleep(interval_seconds)

        status = 0
        try:
            if platform == "af":
                game = db.get_game_af_by_id(group["game_id"])
                if game:
                    status, _ = send_af(
                        pkg=game["package"],
                        dev_key=game["dev_key"],
                        gaid=group["gaid"],
                        af_uid=group["af_uid"],
                        event_name=event["event_name"],
                        revenue=event.get("revenue"),
                        proxy=proxy,
                        platform="android",
                        level=event.get("level_value"),
                    )
            elif platform == "adj":
                game = db.get_game_adj_by_id(group["game_id"])
                if game:
                    status, _ = send_adj(
                        app_token=game["app_token"],
                        event_token=event.get("event_token", event["event_name"]),
                        gps_adid=group["gaid"],
                        proxy=proxy,
                        platform="android",
                        level=event.get("level_value"),
                    )
            elif platform == "sg":
                game = db.get_game_singular_by_id(group["game_id"])
                if game:
                    status, _ = send_singular(
                        event_name=event["event_name"],
                        aifa=group["gaid"],
                        uid=group["af_uid"],
                        package=game["package"],
                        app_key=game["app_key"],
                        level=event.get("level_value"),
                        proxy=proxy,
                        platform="android",
                        singular_uid=group["af_uid"] or None,
                    )

            emoji = "✅" if status == 200 else "❌"
            result_text = "تم الإرسال بنجاح" if status == 200 else f"فشل الإرسال (كود: {status})"
            db.update_scheduled_group_index(group_id, i + 1)

            try:
                await context.bot.send_message(
                    chat_id,
                    f"{emoji} *إشعار جدولة #{group_id}*\n\n"
                    f"🎯 *الحدث:* {event['display_name']}\n"
                    f"📍 *التسلسل:* {i+1}/{len(events)}\n"
                    f"📊 *النتيجة:* {result_text}",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"[SCHED {group_id}] notify error: {e}")

        except Exception as e:
            logger.error(f"[SCHED {group_id}] error at event {i}: {e}")

    db.complete_scheduled_group(group_id)
    try:
        await context.bot.send_message(
            chat_id,
            f"✅ *اكتملت الجدولة #{group_id}!*\n\n"
            f"🎮 {group['game_name']}\n"
            f"🎯 تم تنفيذ جميع الأحداث بنجاح.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
            ]]),
        )
    except Exception:
        pass


@require_access
async def sched_custom_event_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user to enter a custom level number for the scheduled group."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎯 *إضافة لفل مخصص*\n\n"
        "📝 أدخل رقم اللفل المطلوب:\n"
        "مثال: `45` أو `100`",
        parse_mode="Markdown",
    )
    return SCH_CUSTOM_LEVEL


@require_access
async def sched_custom_level_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the custom level number entered by the user and add it to the event pool."""
    try:
        level = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً فقط*", parse_mode="Markdown")
        return SCH_CUSTOM_LEVEL

    if level < 1:
        await update.message.reply_text("❌ *يجب أن يكون رقم اللفل أكبر من 0*", parse_mode="Markdown")
        return SCH_CUSTOM_LEVEL

    sched = context.user_data.get("sched", {})
    plat = sched.get("platform", "af")

    # Build platform-specific event data (same approach as standalone custom handlers)
    if plat == "af":
        event_name = f"af_level_{level}_completed"
        event_token = ""
    elif plat == "adj":
        event_name = f"level_{level}"
        event_token = f"level_{level}"
    else:  # sg (Singular)
        event_name = "sng_level_achieved"
        event_token = ""

    # Generate a unique positive ID that won't clash with real DB event IDs
    custom_count = sched.get("custom_count", 0) + 1
    context.user_data["sched"]["custom_count"] = custom_count
    custom_id = 90000 + custom_count * 100 + (level % 100)

    custom_event = {
        "id": custom_id,
        "display_name": f"🎯 لفل مخصص ({level})",
        "event_name": event_name,
        "event_token": event_token,
        "level_value": level,
        "revenue": None,
        "is_custom": True,
    }

    # Add to both pool (so user can toggle it off later) and selected
    context.user_data["sched"].setdefault("events_pool", []).append(custom_event)
    context.user_data["sched"].setdefault("selected_events", []).append(custom_event)

    # Re-build the event selection keyboard and show it as a new message
    sched = context.user_data["sched"]
    events_pool = sched["events_pool"]
    selected = sched["selected_events"]
    selected_ids = {e["id"]: idx + 1 for idx, e in enumerate(selected)}

    kb = []
    for ev in events_pool:
        num = selected_ids.get(ev["id"])
        label = f"✅ {num}. {ev['display_name']}" if num else f"⬜ {ev['display_name']}"
        kb.append([InlineKeyboardButton(label, callback_data=f"sched_ev_{ev['id']}")])

    game_type = _PLAT_TYPE_MAP.get(plat, plat)
    game_id = sched.get("game_id")
    if game_id and db.is_custom_event_enabled(game_type, game_id):
        kb.append([InlineKeyboardButton("🎯 إضافة لفل مخصص", callback_data="sched_custom_ev")])

    kb.append([InlineKeyboardButton("💾 حفظ الترتيب والمتابعة ◀", callback_data="sched_save_events")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="sched_new")])

    selected_lines = "\n".join(f"  {i+1}. {e['display_name']}" for i, e in enumerate(selected))

    await update.message.reply_text(
        f"✅ *تمت إضافة لفل مخصص ({level})*\n\n"
        f"🗓 *اختر الأحداث بالترتيب*\n🎮 {sched['game_name']}\n\n"
        f"اضغط على الحدث لإضافته — اضغط مجدداً لإلغائه\n\n"
        f"*الأحداث المختارة:*\n{selected_lines}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return SCH_EVENTS


def get_handlers():
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(sched_menu, pattern="^sched_menu$"),
            CallbackQueryHandler(sched_new, pattern="^sched_new$"),
        ],
        states={
            SCH_PLATFORM: [
                CallbackQueryHandler(sched_platform, pattern=r"^sched_plat_(af|adj|sg)$"),
            ],
            SCH_GAME: [
                CallbackQueryHandler(sched_game, pattern=r"^sched_game_\d+$"),
            ],
            SCH_EVENTS: [
                CallbackQueryHandler(sched_toggle_event, pattern=r"^sched_ev_\d+$"),
                CallbackQueryHandler(sched_save_events, pattern="^sched_save_events$"),
                CallbackQueryHandler(sched_back_to_events, pattern="^sched_back_to_events$"),
                CallbackQueryHandler(sched_custom_event_prompt, pattern="^sched_custom_ev$"),
            ],
            SCH_INTERVAL: [
                CallbackQueryHandler(sched_interval, pattern=r"^sched_int_(15|25|60|120)$"),
            ],
            SCH_GAID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sched_gaid),
            ],
            SCH_AF_UID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sched_af_uid),
            ],
            SCH_CONFIRM: [
                CallbackQueryHandler(sched_confirm, pattern="^sched_confirm$"),
            ],
            SCH_CUSTOM_LEVEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sched_custom_level_entered),
                CallbackQueryHandler(sched_custom_event_prompt, pattern="^sched_custom_ev$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(sched_menu, pattern="^sched_menu$"),
        ],
        allow_reentry=True,
        name="schedule_conv",
        persistent=False,
    )
    return [
        conv,
        CallbackQueryHandler(sched_list, pattern="^sched_list$"),
    ]
