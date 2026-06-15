import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
)

from src.config import ADMIN_IDS
from src.database import queries as db
from src.middlewares.auth import require_access

logger = logging.getLogger(__name__)

# States
(
    ADMIN_ADD_USER, ADMIN_REMOVE_USER, ADMIN_BAN, ADMIN_UNBAN,
    ADMIN_BROADCAST_MSG,
    ADD_GAME_TYPE, ADD_GAME_NAME, ADD_GAME_DISPLAY, ADD_GAME_PACKAGE, ADD_GAME_KEY, ADD_GAME_EMOJI,
    ADD_EVENT_TYPE, ADD_EVENT_GAME, ADD_EVENT_NAME, ADD_EVENT_DISPLAY, ADD_EVENT_TOKEN,
    DEL_GAME_TYPE, DEL_GAME_SELECT,
    DEL_EVENT_TYPE, DEL_EVENT_GAME, DEL_EVENT_SELECT,
    PAYMENT_EDIT_ADDRESS, PAYMENT_EDIT_INSTRUCTIONS, PAYMENT_EDIT_API_KEY, PAYMENT_EDIT_API_SECRET,
    PLAN_ADD_NAME, PLAN_ADD_DURATION, PLAN_ADD_PRICE, PLAN_ADD_LIMIT,
    PLAN_EDIT_NAME, PLAN_EDIT_DURATION, PLAN_EDIT_PRICE, PLAN_EDIT_LIMIT,
) = range(600, 633)


def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def _admin_required(func):
    from functools import wraps
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        uid = update.effective_user.id
        if not _is_admin(uid):
            if update.callback_query:
                await update.callback_query.answer("❌ غير مصرح", show_alert=True)
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def _back_kb(data: str = "admin_panel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=data)]])


# ==================== Admin panel ====================

@_admin_required
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("👥 المستخدمون", callback_data="admin_users")],
        [InlineKeyboardButton("➕ إضافة مستخدم", callback_data="admin_add_user")],
        [InlineKeyboardButton("🗑️ حذف مستخدم", callback_data="admin_remove_user")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban")],
        [InlineKeyboardButton("🔓 إلغاء حظر", callback_data="admin_unban")],
        [InlineKeyboardButton("📋 المحظورين", callback_data="admin_banned_list")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎮 إدارة الألعاب", callback_data="admin_games")],
        [InlineKeyboardButton("🎯 إدارة الأحداث", callback_data="admin_events")],
        [InlineKeyboardButton("💳 إعدادات الدفع", callback_data="admin_payment")],
        [InlineKeyboardButton("📦 إدارة الباقات", callback_data="admin_plans")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    await query.edit_message_text("👑 *لوحة تحكم المدير*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stats = db.get_stats()
    txt = (
        f"📊 *الإحصائيات*\n\n"
        f"👥 إجمالي المستخدمين: `{stats['total']}`\n"
        f"✅ المسموح لهم: `{stats['allowed']}`\n"
        f"🚫 المحظورون: `{stats['banned']}`\n"
        f"📨 إجمالي الطلبات: `{stats['requests']}`\n"
        f"🌾 مزارع نشطة: `{stats['farms']}`\n"
        f"📦 اشتراكات نشطة: `{stats.get('active_subs', 0)}`\n"
        f"⏳ طلبات دفع معلقة: `{stats.get('pending_reqs', 0)}`"
    )
    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=_back_kb())


@_admin_required
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = db.get_all_users()
    txt = "👥 *قائمة المستخدمين:*\n\n"
    for u in users[:30]:
        ban = "🚫 " if u.get("banned") else ""
        allowed = "✅ " if u.get("allowed") else "⏳ "
        last = (u.get("last_use") or "")[:10]
        txt += f"• `{u['user_id']}` {ban}{allowed} | @{u.get('username') or '-'} | {u.get('name') or '-'} | {last}\n"
    await query.message.reply_text(txt[:4000], parse_mode="Markdown", reply_markup=_back_kb())


@_admin_required
async def admin_allowed_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = db.get_allowed_users()
    txt = "✅ *المستخدمون المسموح لهم:*\n\n"
    for u in users:
        txt += f"• `{u['user_id']}` | @{u.get('username') or '-'} | {u.get('name') or '-'}\n"
    await query.message.reply_text(txt[:4000] or "لا يوجد مستخدمون مسموح لهم", parse_mode="Markdown", reply_markup=_back_kb())


@_admin_required
async def admin_banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = db.get_banned_users()
    txt = "🚫 *المحظورون:*\n\n"
    for u in users:
        txt += f"• `{u['user_id']}` | @{u.get('username') or '-'} | {u.get('name') or '-'}\n"
    await query.message.reply_text(txt[:4000] or "لا يوجد محظورون", parse_mode="Markdown", reply_markup=_back_kb())


# ==================== Add user ====================

@_admin_required
async def admin_add_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ *أدخل معرف المستخدم (ID)*\nمثال: `6075014046`",
        parse_mode="Markdown",
    )
    return ADMIN_ADD_USER


@_admin_required
async def admin_add_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *معرف غير صالح*", parse_mode="Markdown")
        return ADMIN_ADD_USER

    user = db.get_user_by_id(uid)
    if not user:
        await update.message.reply_text("❌ *المستخدم غير موجود في قاعدة البيانات*", parse_mode="Markdown")
    else:
        db.add_allowed_user(uid, user.get("username") or "", user.get("name") or "", update.effective_user.id)
        db.ensure_user_platform(uid)
        await update.message.reply_text(f"✅ *تمت إضافة المستخدم* `{uid}`", parse_mode="Markdown")
        try:
            await context.bot.send_message(uid, "🎉 *تم تفعيل حسابك!*\nيمكنك الآن استخدام البوت.", parse_mode="Markdown")
        except Exception:
            pass

    await update.message.reply_text("العودة:", reply_markup=_back_kb())
    return ConversationHandler.END


# ==================== Remove user ====================

@_admin_required
async def admin_remove_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🗑️ *أدخل معرف المستخدم (ID)*", parse_mode="Markdown")
    return ADMIN_REMOVE_USER


@_admin_required
async def admin_remove_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *معرف غير صالح*", parse_mode="Markdown")
        return ADMIN_REMOVE_USER

    db.remove_allowed_user(uid)
    await update.message.reply_text(f"✅ *تم حذف المستخدم* `{uid}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(uid, "🚫 *تم إلغاء تفعيل حسابك*", parse_mode="Markdown")
    except Exception:
        pass
    await update.message.reply_text("العودة:", reply_markup=_back_kb())
    return ConversationHandler.END


# ==================== Ban / Unban ====================

@_admin_required
async def admin_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🚫 *أدخل معرف المستخدم (ID)*", parse_mode="Markdown")
    return ADMIN_BAN


@_admin_required
async def admin_ban_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *معرف غير صالح*", parse_mode="Markdown")
        return ADMIN_BAN

    db.ban_user(uid)
    await update.message.reply_text(f"✅ *تم حظر المستخدم* `{uid}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(uid, "🚫 *لقد تم حظرك من استخدام البوت*", parse_mode="Markdown")
    except Exception:
        pass
    await update.message.reply_text("العودة:", reply_markup=_back_kb())
    return ConversationHandler.END


@_admin_required
async def admin_unban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔓 *أدخل معرف المستخدم (ID)*", parse_mode="Markdown")
    return ADMIN_UNBAN


@_admin_required
async def admin_unban_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *معرف غير صالح*", parse_mode="Markdown")
        return ADMIN_UNBAN

    db.unban_user(uid)
    await update.message.reply_text(f"✅ *تم إلغاء حظر المستخدم* `{uid}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(uid, "✅ *تم إلغاء حظرك. يمكنك استخدام البوت.*", parse_mode="Markdown")
    except Exception:
        pass
    await update.message.reply_text("العودة:", reply_markup=_back_kb())
    return ConversationHandler.END


# ==================== Broadcast ====================

@_admin_required
async def admin_broadcast_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📢 *أدخل رسالتك*\n✨ يمكنك استخدام Markdown",
        parse_mode="Markdown",
    )
    return ADMIN_BROADCAST_MSG


@_admin_required
async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    users = db.get_all_users()
    sent = 0
    failed = 0
    for u in users:
        if u.get("banned"):
            continue
        try:
            await context.bot.send_message(u["user_id"], msg_text, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 *تم الإرسال!*\n✅ نجح: {sent}\n❌ فشل: {failed}",
        parse_mode="Markdown",
        reply_markup=_back_kb(),
    )
    return ConversationHandler.END


# ==================== Game management ====================

@_admin_required
async def admin_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("➕ إضافة لعبة", callback_data="admin_add_game")],
        [InlineKeyboardButton("🗑️ حذف لعبة", callback_data="admin_delete_game")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")],
    ]
    await query.edit_message_text("🎮 *إدارة الألعاب*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def admin_add_game_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="add_game_af")],
        [InlineKeyboardButton("📊 Adjust", callback_data="add_game_adj")],
        [InlineKeyboardButton("🌟 Singular", callback_data="add_game_singular")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_games")],
    ]
    await query.edit_message_text("🎮 *اختر نوع اللعبة*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ADD_GAME_TYPE


@_admin_required
async def add_game_af(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["add_game_type"] = "af"
    await query.edit_message_text("📱 *أدخل اسم اللعبة (name)*\nمثال: `my_game`", parse_mode="Markdown")
    return ADD_GAME_NAME


@_admin_required
async def add_game_adj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["add_game_type"] = "adj"
    await query.edit_message_text("📊 *أدخل اسم اللعبة (name)*\nمثال: `my_adj_game`", parse_mode="Markdown")
    return ADD_GAME_NAME


@_admin_required
async def add_game_singular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["add_game_type"] = "singular"
    await query.edit_message_text("🌟 *أدخل اسم اللعبة (name)*\nمثال: `my_singular_game`", parse_mode="Markdown")
    return ADD_GAME_NAME


@_admin_required
async def add_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game_name"] = update.message.text.strip()
    await update.message.reply_text("📝 *أدخل الاسم الظاهر*", parse_mode="Markdown")
    return ADD_GAME_DISPLAY


@_admin_required
async def add_game_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game_display"] = update.message.text.strip()
    gtype = context.user_data.get("add_game_type", "af")
    if gtype == "adj":
        await update.message.reply_text("🔑 *أدخل App Token*", parse_mode="Markdown")
        return ADD_GAME_KEY
    await update.message.reply_text("📦 *أدخل Package Name*", parse_mode="Markdown")
    return ADD_GAME_PACKAGE


@_admin_required
async def add_game_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game_package"] = update.message.text.strip()
    gtype = context.user_data.get("add_game_type", "af")
    if gtype == "af":
        await update.message.reply_text("🔑 *أدخل Dev Key*", parse_mode="Markdown")
    else:
        await update.message.reply_text("🔑 *أدخل App Key*", parse_mode="Markdown")
    return ADD_GAME_KEY


@_admin_required
async def add_game_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game_key"] = update.message.text.strip()
    await update.message.reply_text("🎨 *أدخل الإيموجي* (اختياري، أرسل - لتخطي)", parse_mode="Markdown")
    return ADD_GAME_EMOJI


@_admin_required
async def add_game_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emoji = update.message.text.strip()
    if emoji == "-":
        emoji = "🎮"
    context.user_data["add_game_emoji"] = emoji

    gtype = context.user_data.get("add_game_type", "af")
    name = context.user_data.get("add_game_name", "")
    display = context.user_data.get("add_game_display", "")
    package = context.user_data.get("add_game_package", "")
    key = context.user_data.get("add_game_key", "")

    try:
        if gtype == "af":
            db.add_game_af(name, display, package, key, emoji)
        elif gtype == "adj":
            db.add_game_adj(name, display, key, emoji)
        elif gtype == "singular":
            db.add_game_singular(name, display, package, key, emoji)
        await update.message.reply_text(f"✅ *تم إضافة اللعبة*\n🎮 {display}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ *خطأ:* `{e}`", parse_mode="Markdown")

    await update.message.reply_text("العودة:", reply_markup=_back_kb("admin_games"))
    return ConversationHandler.END


# ==================== Delete game ====================

@_admin_required
async def admin_delete_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="del_game_af")],
        [InlineKeyboardButton("📊 Adjust", callback_data="del_game_adj")],
        [InlineKeyboardButton("🌟 Singular", callback_data="del_game_singular")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_games")],
    ]
    await query.edit_message_text("🗑️ *اختر نوع اللعبة*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return DEL_GAME_TYPE


@_admin_required
async def del_game_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gtype = query.data.replace("del_game_", "")
    context.user_data["del_game_type"] = gtype

    if gtype == "af":
        games = db.get_all_games_af()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_game_confirm_{gtype}_{g['id']}")] for g in games]
    elif gtype == "adj":
        games = db.get_all_games_adj()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_game_confirm_{gtype}_{g['id']}")] for g in games]
    else:
        games = db.get_all_games_singular()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_game_confirm_{gtype}_{g['id']}")] for g in games]

    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_delete_game")])
    await query.edit_message_text("🗑️ *اختر اللعبة للحذف*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return DEL_GAME_SELECT


@_admin_required
async def del_game_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    gtype = parts[3]
    game_id = int(parts[4])

    if gtype == "af":
        db.delete_game_af(game_id)
    elif gtype == "adj":
        db.delete_game_adj(game_id)
    elif gtype == "singular":
        db.delete_game_singular(game_id)

    await query.edit_message_text("✅ *تم حذف اللعبة وأحداثها*", parse_mode="Markdown", reply_markup=_back_kb("admin_games"))
    return ConversationHandler.END


# ==================== Event management ====================

@_admin_required
async def admin_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("➕ إضافة حدث", callback_data="admin_add_event")],
        [InlineKeyboardButton("🗑️ حذف حدث", callback_data="admin_delete_event")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")],
    ]
    await query.edit_message_text("🎯 *إدارة الأحداث*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def admin_add_event_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="add_event_type_af")],
        [InlineKeyboardButton("📊 Adjust", callback_data="add_event_type_adj")],
        [InlineKeyboardButton("🌟 Singular", callback_data="add_event_type_singular")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_events")],
    ]
    await query.edit_message_text("🎯 *اختر نوع الحدث*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ADD_EVENT_TYPE


@_admin_required
async def add_event_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    etype = query.data.replace("add_event_type_", "")
    context.user_data["add_event_type"] = etype

    if etype == "af":
        games = db.get_all_games_af()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"add_event_game_{g['id']}")] for g in games]
    elif etype == "adj":
        games = db.get_all_games_adj()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"add_event_game_{g['id']}")] for g in games]
    else:
        games = db.get_all_games_singular()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"add_event_game_{g['id']}")] for g in games]

    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_add_event")])
    await query.edit_message_text("🎮 *اختر اللعبة*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ADD_EVENT_GAME


@_admin_required
async def add_event_game_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.replace("add_event_game_", ""))
    context.user_data["add_event_game_id"] = game_id
    await query.edit_message_text("📝 *أدخل اسم الحدث (event_name)*", parse_mode="Markdown")
    return ADD_EVENT_NAME


@_admin_required
async def add_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_event_name"] = update.message.text.strip()
    await update.message.reply_text("📝 *أدخل الاسم الظاهر*", parse_mode="Markdown")
    return ADD_EVENT_DISPLAY


@_admin_required
async def add_event_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_event_display"] = update.message.text.strip()
    etype = context.user_data.get("add_event_type", "af")
    if etype == "adj":
        await update.message.reply_text("🔑 *أدخل Event Token*", parse_mode="Markdown")
        return ADD_EVENT_TOKEN
    await _save_event(update, context)
    return ConversationHandler.END


@_admin_required
async def add_event_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_event_token"] = update.message.text.strip()
    await _save_event(update, context)
    return ConversationHandler.END


async def _save_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    etype = context.user_data.get("add_event_type", "af")
    game_id = context.user_data.get("add_event_game_id")
    event_name = context.user_data.get("add_event_name", "")
    display = context.user_data.get("add_event_display", "")
    token = context.user_data.get("add_event_token", "")

    try:
        if etype == "af":
            db.add_event_af(game_id, event_name, display)
        elif etype == "adj":
            db.add_event_adj(game_id, event_name, token, display)
        elif etype == "singular":
            db.add_event_singular(game_id, event_name, display)
        await update.message.reply_text(f"✅ *تم إضافة الحدث*\n📝 {display}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ *خطأ:* `{e}`", parse_mode="Markdown")

    await update.message.reply_text("العودة:", reply_markup=_back_kb("admin_events"))


# ==================== Delete event ====================

@_admin_required
async def admin_delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="del_event_af")],
        [InlineKeyboardButton("📊 Adjust", callback_data="del_event_adj")],
        [InlineKeyboardButton("🌟 Singular", callback_data="del_event_singular")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_events")],
    ]
    await query.edit_message_text("🗑️ *اختر نوع الحدث*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return DEL_EVENT_TYPE


@_admin_required
async def del_event_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    etype = query.data.replace("del_event_", "")
    context.user_data["del_event_type"] = etype

    if etype == "af":
        games = db.get_all_games_af()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_event_game_{g['id']}")] for g in games]
    elif etype == "adj":
        games = db.get_all_games_adj()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_event_game_{g['id']}")] for g in games]
    else:
        games = db.get_all_games_singular()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_event_game_{g['id']}")] for g in games]

    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_delete_event")])
    await query.edit_message_text("🎮 *اختر اللعبة*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return DEL_EVENT_GAME


@_admin_required
async def del_event_game_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.replace("del_event_game_", ""))
    context.user_data["del_event_game_id"] = game_id
    etype = context.user_data.get("del_event_type", "af")

    if etype == "af":
        events = db.get_af_events(game_id)
    elif etype == "adj":
        events = db.get_adj_events(game_id)
    else:
        events = db.get_singular_events(game_id)

    if not events:
        await query.edit_message_text("❌ *لا توجد أحداث*", parse_mode="Markdown", reply_markup=_back_kb("admin_events"))
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(ev["display_name"], callback_data=f"del_event_confirm_{ev['id']}")] for ev in events]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_delete_event")])
    await query.edit_message_text("🎯 *اختر الحدث*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return DEL_EVENT_SELECT


@_admin_required
async def del_event_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.replace("del_event_confirm_", ""))
    etype = context.user_data.get("del_event_type", "af")

    if etype == "af":
        db.delete_event_af(event_id)
    elif etype == "adj":
        db.delete_event_adj(event_id)
    else:
        db.delete_event_singular(event_id)

    await query.edit_message_text("✅ *تم حذف الحدث*", parse_mode="Markdown", reply_markup=_back_kb("admin_events"))
    return ConversationHandler.END


# ==================== Payment Settings Management ====================

@_admin_required
async def admin_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    settings = db.get_all_payment_settings()

    if not settings:
        # Initialize default payment settings if not exist
        db.set_payment_setting("usdt", "", "", "", "", "💎 USDT (TRC20)", True)
        db.set_payment_setting("sham_cash", "", "", "", "", "💰 شام كاش", True)
        db.set_payment_setting("syriatel_cash", "", "", "", "", "💰 سرياتيل كاش", True)
        settings = db.get_all_payment_settings()

    txt = "💳 *إعدادات طرق الدفع*\n\n"
    kb = []
    for s in settings:
        status = "✅" if s.get("is_active") else "❌"
        txt += f"{status} {s['display_name']}\n"
        kb.append([InlineKeyboardButton(f"{status} {s['display_name']}", callback_data=f"payment_edit_{s['method']}")])

    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def payment_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("payment_edit_", "")
    context.user_data["payment_method"] = method
    setting = db.get_payment_setting(method)

    if not setting:
        await query.edit_message_text("❌ طريقة الدفع غير موجودة", reply_markup=_back_kb("admin_payment"))
        return ConversationHandler.END

    is_active = setting.get("is_active")
    if isinstance(is_active, str):
        is_active = is_active.lower() == "true"

    txt = (
        f"💳 *{setting['display_name']}*\n"
        f"📍 العنوان: `{setting.get('address') or 'غير محدد'}`\n"
        f"📋 التعليمات: `{setting.get('instructions') or 'لا يوجد'}`\n"
        f"الحالة: {'✅ مفعلة' if is_active else '❌ معطلة'}"
    )
    if method == "usdt":
        txt += f"\n🔑 API Key: {'محدد ✓' if setting.get('binance_api_key') else 'غير محدد'}"
        txt += f"\n🔐 API Secret: {'محدد ✓' if setting.get('binance_api_secret') else 'غير محدد'}"

    kb = [
        [InlineKeyboardButton("📍 تعديل العنوان", callback_data=f"payment_set_address_{method}")],
        [InlineKeyboardButton("📋 تعديل التعليمات", callback_data=f"payment_set_instructions_{method}")],
    ]
    if method == "usdt":
        kb.append([InlineKeyboardButton("🔑 تعديل API Key", callback_data=f"payment_set_apikey_{method}")])
        kb.append([InlineKeyboardButton("🔐 تعديل API Secret", callback_data=f"payment_set_apisecret_{method}")])
    kb.append([InlineKeyboardButton("✅ تفعيل" if not is_active else "❌ تعطيل",
                                    callback_data=f"payment_toggle_{method}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_payment")])
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def payment_set_address_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("payment_set_address_", "")
    context.user_data["payment_method"] = method
    await query.edit_message_text("📍 *أدخل العنوان الجديد:*", parse_mode="Markdown")
    return PAYMENT_EDIT_ADDRESS


@_admin_required
async def payment_set_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = context.user_data.get("payment_method", "")
    if not method:
        await update.message.reply_text("❌ *خطأ: لم يتم تحديد طريقة الدفع*", parse_mode="Markdown")
        return ConversationHandler.END

    address = update.message.text.strip()
    db.update_payment_setting_field(method, "address", address)

    await update.message.reply_text(
        f"✅ *تم تحديث العنوان*\n📍 `{address}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data=f"payment_edit_{method}")]
        ])
    )
    return ConversationHandler.END


@_admin_required
async def payment_set_instructions_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("payment_set_instructions_", "")
    context.user_data["payment_method"] = method
    await query.edit_message_text("📋 *أدخل التعليمات الجديدة:*", parse_mode="Markdown")
    return PAYMENT_EDIT_INSTRUCTIONS


@_admin_required
async def payment_set_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = context.user_data.get("payment_method", "")
    if not method:
        await update.message.reply_text("❌ *خطأ: لم يتم تحديد طريقة الدفع*", parse_mode="Markdown")
        return ConversationHandler.END

    instructions = update.message.text.strip()
    db.update_payment_setting_field(method, "instructions", instructions)

    await update.message.reply_text(
        f"✅ *تم تحديث التعليمات*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data=f"payment_edit_{method}")]
        ])
    )
    return ConversationHandler.END


@_admin_required
async def payment_set_apikey_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("payment_set_apikey_", "")
    context.user_data["payment_method"] = method
    await query.edit_message_text("🔑 *أدخل API Key:*", parse_mode="Markdown")
    return PAYMENT_EDIT_API_KEY


@_admin_required
async def payment_set_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = context.user_data.get("payment_method", "")
    if not method:
        await update.message.reply_text("❌ *خطأ: لم يتم تحديد طريقة الدفع*", parse_mode="Markdown")
        return ConversationHandler.END

    api_key = update.message.text.strip()
    db.update_payment_setting_field(method, "binance_api_key", api_key)

    await update.message.reply_text(
        f"✅ *تم تحديث API Key*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data=f"payment_edit_{method}")]
        ])
    )
    return ConversationHandler.END


@_admin_required
async def payment_set_apisecret_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("payment_set_apisecret_", "")
    context.user_data["payment_method"] = method
    await query.edit_message_text("🔐 *أدخل API Secret:*", parse_mode="Markdown")
    return PAYMENT_EDIT_API_SECRET


@_admin_required
async def payment_set_apisecret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = context.user_data.get("payment_method", "")
    if not method:
        await update.message.reply_text("❌ *خطأ: لم يتم تحديد طريقة الدفع*", parse_mode="Markdown")
        return ConversationHandler.END

    api_secret = update.message.text.strip()
    db.update_payment_setting_field(method, "binance_api_secret", api_secret)

    await update.message.reply_text(
        f"✅ *تم تحديث API Secret*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data=f"payment_edit_{method}")]
        ])
    )
    return ConversationHandler.END


@_admin_required
async def payment_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("payment_toggle_", "")
    setting = db.get_payment_setting(method)

    if setting:
        current = setting.get("is_active")
        if isinstance(current, str):
            current = current.lower() == "true"
        new_status = not current
        db.update_payment_setting_field(method, "is_active", "true" if new_status else "false")
        await query.answer(f"{'تم التفعيل' if new_status else 'تم التعطيل'}", show_alert=True)

    context.user_data["payment_method"] = method
    await payment_edit_select(update, context)


# ==================== Plans Management ====================

@_admin_required
async def admin_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plans = db.get_all_plans()

    txt = "📦 *إدارة الباقات*\n\n"
    kb = []
    for p in plans:
        status = "✅" if p.get("is_active") else "❌"
        txt += f"{status} {p['name']} - {p['price']}$ | {p['daily_limit']} عملية | {p['duration_days']} يوم\n"
        kb.append([InlineKeyboardButton(f"{status} {p['name']} ({p['price']}$)", callback_data=f"plan_edit_{p['id']}")])

    kb.append([InlineKeyboardButton("➕ إضافة باقة", callback_data="plan_add")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def plan_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📦 *أدخل اسم الباقة:*", parse_mode="Markdown")
    return PLAN_ADD_NAME


@_admin_required
async def plan_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plan_name"] = update.message.text.strip()
    await update.message.reply_text("📅 *أدخل المدة بالأيام:*\nمثال: `30` لشهر", parse_mode="Markdown")
    return PLAN_ADD_DURATION


@_admin_required
async def plan_add_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["plan_duration"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return PLAN_ADD_DURATION
    await update.message.reply_text("💰 *أدخل السعر بالدولار:*\nمثال: `15`", parse_mode="Markdown")
    return PLAN_ADD_PRICE


@_admin_required
async def plan_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["plan_price"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return PLAN_ADD_PRICE
    await update.message.reply_text("📊 *أدخل الحد اليومي للعمليات:*\nمثال: `20`", parse_mode="Markdown")
    return PLAN_ADD_LIMIT


@_admin_required
async def plan_add_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        daily_limit = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return PLAN_ADD_LIMIT

    name = context.user_data.get("plan_name", "")
    duration = context.user_data.get("plan_duration", 30)
    price = context.user_data.get("plan_price", 0.0)

    try:
        db.add_plan(name, duration, price, daily_limit)
        await update.message.reply_text(
            f"✅ *تم إضافة الباقة*\n\n"
            f"📦 الاسم: {name}\n"
            f"📅 المدة: {duration} يوم\n"
            f"💰 السعر: {price}$\n"
            f"📊 الحد اليومي: {daily_limit} عملية",
            parse_mode="Markdown",
            reply_markup=_back_kb("admin_plans")
        )
    except Exception as e:
        await update.message.reply_text(f"❌ *خطأ:* `{e}`", parse_mode="Markdown", reply_markup=_back_kb("admin_plans"))

    return ConversationHandler.END


@_admin_required
async def plan_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_edit_", ""))
    plan = db.get_plan_by_id(plan_id)

    if not plan:
        await query.edit_message_text("❌ الباقة غير موجودة", reply_markup=_back_kb("admin_plans"))
        return ConversationHandler.END

    context.user_data["plan_id"] = plan_id

    is_active = plan.get("is_active")
    if isinstance(is_active, str):
        is_active = is_active.lower() == "true" or is_active == "t"

    txt = (
        f"📦 *{plan['name']}*\n\n"
        f"📅 المدة: {plan['duration_days']} يوم\n"
        f"💰 السعر: {plan['price']}$\n"
        f"📊 الحد اليومي: {plan['daily_limit']} عملية\n"
        f"الحالة: {'✅ مفعلة' if is_active else '❌ معطلة'}"
    )
    kb = [
        [InlineKeyboardButton("📝 تعديل الاسم", callback_data=f"plan_set_name_{plan_id}")],
        [InlineKeyboardButton("📅 تعديل المدة", callback_data=f"plan_set_duration_{plan_id}")],
        [InlineKeyboardButton("💰 تعديل السعر", callback_data=f"plan_set_price_{plan_id}")],
        [InlineKeyboardButton("📊 تعديل الحد اليومي", callback_data=f"plan_set_limit_{plan_id}")],
        [InlineKeyboardButton("✅ تفعيل" if not is_active else "❌ تعطيل",
                              callback_data=f"plan_toggle_{plan_id}")],
        [InlineKeyboardButton("🗑️ حذف الباقة", callback_data=f"plan_delete_{plan_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_plans")],
    ]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def plan_set_name_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_set_name_", ""))
    context.user_data["plan_id"] = plan_id
    await query.edit_message_text("📝 *أدخل الاسم الجديد:*", parse_mode="Markdown")
    return PLAN_EDIT_NAME


@_admin_required
async def plan_set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("plan_id", 0)
    plan = db.get_plan_by_id(plan_id)
    if plan:
        new_name = update.message.text.strip()
        db.update_plan(plan_id, new_name, plan["duration_days"], plan["price"], plan["daily_limit"])
        await update.message.reply_text(
            f"✅ *تم تحديث الاسم*\n📝 `{new_name}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع للباقة", callback_data=f"plan_edit_{plan_id}")]
            ])
        )
    return ConversationHandler.END


@_admin_required
async def plan_set_duration_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_set_duration_", ""))
    context.user_data["plan_id"] = plan_id
    await query.edit_message_text("📅 *أدخل المدة الجديدة بالأيام:*", parse_mode="Markdown")
    return PLAN_EDIT_DURATION


@_admin_required
async def plan_set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("plan_id", 0)
    plan = db.get_plan_by_id(plan_id)
    try:
        duration = int(update.message.text.strip())
        if plan:
            db.update_plan(plan_id, plan["name"], duration, plan["price"], plan["daily_limit"])
            await update.message.reply_text(
                f"✅ *تم تحديث المدة*\n📅 `{duration}` يوم",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع للباقة", callback_data=f"plan_edit_{plan_id}")]
                ])
            )
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return PLAN_EDIT_DURATION
    return ConversationHandler.END


@_admin_required
async def plan_set_price_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_set_price_", ""))
    context.user_data["plan_id"] = plan_id
    await query.edit_message_text("💰 *أدخل السعر الجديد:*", parse_mode="Markdown")
    return PLAN_EDIT_PRICE


@_admin_required
async def plan_set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("plan_id", 0)
    plan = db.get_plan_by_id(plan_id)
    try:
        price = float(update.message.text.strip())
        if plan:
            db.update_plan(plan_id, plan["name"], plan["duration_days"], price, plan["daily_limit"])
            await update.message.reply_text(
                f"✅ *تم تحديث السعر*\n💰 `{price}`$",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع للباقة", callback_data=f"plan_edit_{plan_id}")]
                ])
            )
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return PLAN_EDIT_PRICE
    return ConversationHandler.END


@_admin_required
async def plan_set_limit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_set_limit_", ""))
    context.user_data["plan_id"] = plan_id
    await query.edit_message_text("📊 *أدخل الحد اليومي الجديد:*", parse_mode="Markdown")
    return PLAN_EDIT_LIMIT


@_admin_required
async def plan_set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("plan_id", 0)
    plan = db.get_plan_by_id(plan_id)
    try:
        limit = int(update.message.text.strip())
        if plan:
            db.update_plan(plan_id, plan["name"], plan["duration_days"], plan["price"], limit)
            await update.message.reply_text(
                f"✅ *تم تحديث الحد اليومي*\n📊 `{limit}` عملية",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع للباقة", callback_data=f"plan_edit_{plan_id}")]
                ])
            )
    except ValueError:
        await update.message.reply_text("❌ *أدخل رقماً صحيحاً*", parse_mode="Markdown")
        return PLAN_EDIT_LIMIT
    return ConversationHandler.END


@_admin_required
async def plan_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_toggle_", ""))
    plan = db.get_plan_by_id(plan_id)
    if plan:
        current = plan.get("is_active")
        if isinstance(current, str):
            current = current.lower() == "true" or current == "t"
        new_status = not current
        db.toggle_plan(plan_id, new_status)
        await query.answer(f"{'تم التفعيل' if new_status else 'تم التعطيل'}", show_alert=True)
    context.user_data["plan_id"] = plan_id
    await plan_edit_select(update, context)


@_admin_required
async def plan_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_delete_", ""))
    db.delete_plan(plan_id)
    await query.edit_message_text("✅ *تم حذف الباقة*", parse_mode="Markdown", reply_markup=_back_kb("admin_plans"))


# ==================== Conversation Handler ====================

def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        states={
            ADMIN_ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_user_process)],
            ADMIN_REMOVE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_user_process)],
            ADMIN_BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_process)],
            ADMIN_UNBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_process)],
            ADMIN_BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
            ADD_GAME_TYPE: [
                CallbackQueryHandler(add_game_af, pattern="^add_game_af$"),
                CallbackQueryHandler(add_game_adj, pattern="^add_game_adj$"),
                CallbackQueryHandler(add_game_singular, pattern="^add_game_singular$"),
            ],
            ADD_GAME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_name)],
            ADD_GAME_DISPLAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_display)],
            ADD_GAME_PACKAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_package)],
            ADD_GAME_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_key)],
            ADD_GAME_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_emoji)],
            ADD_EVENT_TYPE: [
                CallbackQueryHandler(add_event_type_select, pattern=r"^add_event_type_"),
            ],
            ADD_EVENT_GAME: [CallbackQueryHandler(add_event_game_select, pattern=r"^add_event_game_\d+$")],
            ADD_EVENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_name)],
            ADD_EVENT_DISPLAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_display)],
            ADD_EVENT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_token)],
            DEL_GAME_TYPE: [
                CallbackQueryHandler(del_game_type_select, pattern=r"^del_game_(af|adj|singular)$"),
            ],
            DEL_GAME_SELECT: [CallbackQueryHandler(del_game_confirm, pattern=r"^del_game_confirm_")],
            DEL_EVENT_TYPE: [
                CallbackQueryHandler(del_event_type_select, pattern=r"^del_event_(af|adj|singular)$"),
            ],
            DEL_EVENT_GAME: [CallbackQueryHandler(del_event_game_select, pattern=r"^del_event_game_\d+$")],
            DEL_EVENT_SELECT: [CallbackQueryHandler(del_event_confirm, pattern=r"^del_event_confirm_\d+$")],
            PAYMENT_EDIT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_address)],
            PAYMENT_EDIT_INSTRUCTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_instructions)],
            PAYMENT_EDIT_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_apikey)],
            PAYMENT_EDIT_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_set_apisecret)],
            PLAN_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_name)],
            PLAN_ADD_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_duration)],
            PLAN_ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_price)],
            PLAN_ADD_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_limit)],
            PLAN_EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_set_name)],
            PLAN_EDIT_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_set_duration)],
            PLAN_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_set_price)],
            PLAN_EDIT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_set_limit)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_panel, pattern="^admin_panel$"),
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern="^main_menu$"),
        ],
        allow_reentry=True,
    )


def get_handlers():
    return [
        get_conversation_handler(),
        CallbackQueryHandler(admin_stats, pattern="^admin_stats$"),
        CallbackQueryHandler(admin_users, pattern="^admin_users$"),
        CallbackQueryHandler(admin_allowed_list, pattern="^admin_allowed_list$"),
        CallbackQueryHandler(admin_banned_list, pattern="^admin_banned_list$"),
        CallbackQueryHandler(admin_add_user_prompt, pattern="^admin_add_user$"),
        CallbackQueryHandler(admin_remove_user_prompt, pattern="^admin_remove_user$"),
        CallbackQueryHandler(admin_ban_prompt, pattern="^admin_ban$"),
        CallbackQueryHandler(admin_unban_prompt, pattern="^admin_unban$"),
        CallbackQueryHandler(admin_broadcast_prompt, pattern="^admin_broadcast$"),
        CallbackQueryHandler(admin_games, pattern="^admin_games$"),
        CallbackQueryHandler(admin_add_game_type, pattern="^admin_add_game$"),
        CallbackQueryHandler(admin_delete_game, pattern="^admin_delete_game$"),
        CallbackQueryHandler(admin_events, pattern="^admin_events$"),
        CallbackQueryHandler(admin_add_event_type, pattern="^admin_add_event$"),
        CallbackQueryHandler(admin_delete_event, pattern="^admin_delete_event$"),
        CallbackQueryHandler(admin_payment, pattern="^admin_payment$"),
        CallbackQueryHandler(payment_edit_select, pattern=r"^payment_edit_"),
        CallbackQueryHandler(payment_set_address_prompt, pattern=r"^payment_set_address_"),
        CallbackQueryHandler(payment_set_instructions_prompt, pattern=r"^payment_set_instructions_"),
        CallbackQueryHandler(payment_set_apikey_prompt, pattern=r"^payment_set_apikey_"),
        CallbackQueryHandler(payment_set_apisecret_prompt, pattern=r"^payment_set_apisecret_"),
        CallbackQueryHandler(payment_toggle, pattern=r"^payment_toggle_"),
        CallbackQueryHandler(admin_plans, pattern="^admin_plans$"),
        CallbackQueryHandler(plan_add_start, pattern="^plan_add$"),
        CallbackQueryHandler(plan_edit_select, pattern=r"^plan_edit_\d+$"),
        CallbackQueryHandler(plan_set_name_prompt, pattern=r"^plan_set_name_"),
        CallbackQueryHandler(plan_set_duration_prompt, pattern=r"^plan_set_duration_"),
        CallbackQueryHandler(plan_set_price_prompt, pattern=r"^plan_set_price_"),
        CallbackQueryHandler(plan_set_limit_prompt, pattern=r"^plan_set_limit_"),
        CallbackQueryHandler(plan_toggle, pattern=r"^plan_toggle_"),
        CallbackQueryHandler(plan_delete, pattern=r"^plan_delete_"),
    ]
