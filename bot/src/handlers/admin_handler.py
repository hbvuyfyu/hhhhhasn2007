import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
)

from src.config import ADMIN_IDS
from src.database import queries as db
from src.middlewares.auth import require_access

logger = logging.getLogger(__name__)

(
    ADMIN_ADD_USER, ADMIN_REMOVE_USER, ADMIN_BAN, ADMIN_UNBAN,
    ADMIN_BROADCAST_MSG,
    ADD_GAME_TYPE, ADD_GAME_NAME, ADD_GAME_DISPLAY, ADD_GAME_PACKAGE, ADD_GAME_KEY, ADD_GAME_EMOJI,
    ADD_EVENT_TYPE, ADD_EVENT_GAME, ADD_EVENT_NAME, ADD_EVENT_DISPLAY, ADD_EVENT_TOKEN,
    DEL_GAME_TYPE, DEL_GAME_SELECT,
    DEL_EVENT_TYPE, DEL_EVENT_GAME, DEL_EVENT_SELECT,
) = range(600, 621)

(
    PLAN_ADD_NAME, PLAN_ADD_DAYS, PLAN_ADD_PRICE, PLAN_ADD_LIMIT,
    PAY_SELECT_METHOD, PAY_SET_ADDR, PAY_SET_INSTR, PAY_BINANCE_KEY, PAY_BINANCE_SECRET,
    GRANT_SUB_USER, GRANT_SUB_PLAN,
) = range(650, 661)


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
        [InlineKeyboardButton("👥 المستخدمون",        callback_data="admin_users")],
        [InlineKeyboardButton("➕ إضافة مستخدم",      callback_data="admin_add_user")],
        [InlineKeyboardButton("🗑️ حذف مستخدم",       callback_data="admin_remove_user")],
        [InlineKeyboardButton("🚫 حظر مستخدم",        callback_data="admin_ban")],
        [InlineKeyboardButton("🔓 إلغاء حظر",         callback_data="admin_unban")],
        [InlineKeyboardButton("📋 المحظورين",          callback_data="admin_banned_list")],
        [InlineKeyboardButton("📊 الإحصائيات",         callback_data="admin_stats")],
        [InlineKeyboardButton("📢 إذاعة",              callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎮 إدارة الألعاب",      callback_data="admin_games")],
        [InlineKeyboardButton("🎯 إدارة الأحداث",      callback_data="admin_events")],
        [InlineKeyboardButton("📦 إدارة الباقات",      callback_data="admin_plans")],
        [InlineKeyboardButton("💳 إعدادات الدفع",      callback_data="admin_pay_settings")],
        [InlineKeyboardButton("📋 طلبات الاشتراك",     callback_data="admin_sub_requests")],
        [InlineKeyboardButton("🎁 منح اشتراك",         callback_data="admin_grant_sub")],
        [InlineKeyboardButton("🔙 رجوع",               callback_data="main_menu")],
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
        f"✅ المُفعَّلون يدوياً: `{stats['allowed']}`\n"
        f"📦 اشتراكات نشطة: `{stats['active_subs']}`\n"
        f"🚫 المحظورون: `{stats['banned']}`\n"
        f"📨 إجمالي الطلبات: `{stats['requests']}`\n"
        f"🌾 مزارع نشطة: `{stats['farms']}`\n"
        f"⏳ طلبات دفع معلقة: `{stats['pending_reqs']}`"
    )
    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=_back_kb())


@_admin_required
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = db.get_all_users()
    txt = "👥 *قائمة المستخدمين:*\n\n"
    for u in users[:30]:
        ban     = "🚫 " if u.get("banned") else ""
        allowed = "✅ " if u.get("allowed") else "⏳ "
        last    = (u.get("last_use") or "")[:10]
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
    await query.message.reply_text(txt[:4000] or "لا يوجد مستخدمون", parse_mode="Markdown", reply_markup=_back_kb())


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
    await query.edit_message_text("➕ *أدخل معرف المستخدم (ID)*\nمثال: `6075014046`", parse_mode="Markdown")
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
    await query.edit_message_text("📢 *أدخل رسالتك*\n✨ يمكنك استخدام Markdown", parse_mode="Markdown")
    return ADMIN_BROADCAST_MSG


@_admin_required
async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    users = db.get_all_users()
    sent = failed = 0
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
        [InlineKeyboardButton("➕ إضافة لعبة",  callback_data="admin_add_game")],
        [InlineKeyboardButton("🗑️ حذف لعبة",   callback_data="admin_delete_game")],
        [InlineKeyboardButton("🔙 رجوع",        callback_data="admin_panel")],
    ]
    await query.edit_message_text("🎮 *إدارة الألعاب*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def admin_add_game_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="add_game_af")],
        [InlineKeyboardButton("📊 Adjust",    callback_data="add_game_adj")],
        [InlineKeyboardButton("🌟 Singular",  callback_data="add_game_singular")],
        [InlineKeyboardButton("🔙 رجوع",      callback_data="admin_games")],
    ]
    await query.edit_message_text("🎮 *اختر نوع اللعبة*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ADD_GAME_TYPE


@_admin_required
async def add_game_af(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["add_game_type"] = "af"
    await query.edit_message_text("📱 *اسم اللعبة (بدون مسافات، مثال: dice_dream)*", parse_mode="Markdown")
    return ADD_GAME_NAME


@_admin_required
async def add_game_adj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["add_game_type"] = "adj"
    await query.edit_message_text("📊 *اسم اللعبة (بدون مسافات)*", parse_mode="Markdown")
    return ADD_GAME_NAME


@_admin_required
async def add_game_singular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["add_game_type"] = "singular"
    await query.edit_message_text("🌟 *اسم اللعبة (بدون مسافات)*", parse_mode="Markdown")
    return ADD_GAME_NAME


@_admin_required
async def add_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_game_name"] = update.message.text.strip()
    await update.message.reply_text("📝 *الاسم الظاهر للعبة (مثال: 🎲 Dice Dreams)*", parse_mode="Markdown")
    return ADD_GAME_DISPLAY


@_admin_required
async def add_game_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_game_display"] = update.message.text.strip()
    gtype = context.user_data.get("add_game_type")
    if gtype == "adj":
        await update.message.reply_text("🔑 *App Token (مثال: 367kicwptj5s)*", parse_mode="Markdown")
        return ADD_GAME_KEY
    await update.message.reply_text("📦 *اسم الحزمة (Package Name)*", parse_mode="Markdown")
    return ADD_GAME_PACKAGE


@_admin_required
async def add_game_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_game_package"] = update.message.text.strip()
    gtype = context.user_data.get("add_game_type")
    if gtype == "af":
        await update.message.reply_text("🔑 *Dev Key*", parse_mode="Markdown")
    else:
        await update.message.reply_text("🔑 *App Key*", parse_mode="Markdown")
    return ADD_GAME_KEY


@_admin_required
async def add_game_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_game_key"] = update.message.text.strip()
    await update.message.reply_text("😀 *إيموجي اللعبة (مثال: 🎲)*", parse_mode="Markdown")
    return ADD_GAME_EMOJI


@_admin_required
async def add_game_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emoji   = update.message.text.strip()
    gtype   = context.user_data.get("add_game_type")
    name    = context.user_data.get("new_game_name", "")
    display = context.user_data.get("new_game_display", "")
    package = context.user_data.get("new_game_package", "")
    key     = context.user_data.get("new_game_key", "")

    try:
        if gtype == "af":
            db.add_game_af(name, display, package, key, emoji)
        elif gtype == "adj":
            db.add_game_adj(name, display, key, emoji)
        else:
            db.add_game_singular(name, display, package, key, emoji)
        await update.message.reply_text(f"✅ *تمت إضافة اللعبة:* {display}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ *خطأ:* `{e}`", parse_mode="Markdown")

    await update.message.reply_text("العودة:", reply_markup=_back_kb("admin_games"))
    return ConversationHandler.END


# ── Delete game ──────────────────────────────────────────

@_admin_required
async def admin_delete_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="del_game_af")],
        [InlineKeyboardButton("📊 Adjust",    callback_data="del_game_adj")],
        [InlineKeyboardButton("🌟 Singular",  callback_data="del_game_singular")],
        [InlineKeyboardButton("🔙 رجوع",      callback_data="admin_games")],
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
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_game_confirm_{g['id']}")] for g in games]
    elif gtype == "adj":
        games = db.get_all_games_adj()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_game_confirm_{g['id']}")] for g in games]
    else:
        games = db.get_all_games_singular()
        kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"del_game_confirm_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_delete_game")])
    await query.edit_message_text("🗑️ *اختر اللعبة*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return DEL_GAME_SELECT


@_admin_required
async def del_game_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.replace("del_game_confirm_", ""))
    gtype   = context.user_data.get("del_game_type", "af")
    if gtype == "af":
        db.delete_game_af(game_id)
    elif gtype == "adj":
        db.delete_game_adj(game_id)
    else:
        db.delete_game_singular(game_id)
    await query.edit_message_text("✅ *تم حذف اللعبة*", parse_mode="Markdown", reply_markup=_back_kb("admin_games"))
    return ConversationHandler.END


# ==================== Event management ====================

@_admin_required
async def admin_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("➕ إضافة حدث",  callback_data="admin_add_event")],
        [InlineKeyboardButton("🗑️ حذف حدث",   callback_data="admin_delete_event")],
        [InlineKeyboardButton("🔙 رجوع",        callback_data="admin_panel")],
    ]
    await query.edit_message_text("🎯 *إدارة الأحداث*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def admin_add_event_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="add_event_type_af")],
        [InlineKeyboardButton("📊 Adjust",    callback_data="add_event_type_adj")],
        [InlineKeyboardButton("🌟 Singular",  callback_data="add_event_type_singular")],
        [InlineKeyboardButton("🔙 رجوع",      callback_data="admin_events")],
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
    elif etype == "adj":
        games = db.get_all_games_adj()
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
    context.user_data["add_event_game_id"] = int(query.data.replace("add_event_game_", ""))
    await query.edit_message_text("📝 *اسم الحدث الفعلي (مثال: af_kingdom_3_restored)*", parse_mode="Markdown")
    return ADD_EVENT_NAME


@_admin_required
async def add_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_event_name"] = update.message.text.strip()
    await update.message.reply_text("📋 *الاسم الظاهر للحدث*", parse_mode="Markdown")
    return ADD_EVENT_DISPLAY


@_admin_required
async def add_event_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_event_display"] = update.message.text.strip()
    etype = context.user_data.get("add_event_type")
    if etype in ("adj",):
        await update.message.reply_text("🔑 *Event Token*", parse_mode="Markdown")
        return ADD_EVENT_TOKEN
    game_id = context.user_data.get("add_event_game_id")
    ev_name = context.user_data.get("add_event_name")
    ev_disp = context.user_data.get("add_event_display")
    try:
        if etype == "af":
            db.add_event_af(game_id, ev_name, ev_disp)
        else:
            db.add_event_singular(game_id, ev_name, ev_disp)
        await update.message.reply_text(f"✅ *تمت إضافة الحدث:* {ev_disp}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ *خطأ:* `{e}`", parse_mode="Markdown")
    await update.message.reply_text("العودة:", reply_markup=_back_kb("admin_events"))
    return ConversationHandler.END


@_admin_required
async def add_event_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token   = update.message.text.strip()
    game_id = context.user_data.get("add_event_game_id")
    ev_name = context.user_data.get("add_event_name")
    ev_disp = context.user_data.get("add_event_display")
    etype   = context.user_data.get("add_event_type")
    try:
        if etype == "adj":
            db.add_event_adj(game_id, ev_name, token, ev_disp)
        await update.message.reply_text(f"✅ *تمت إضافة الحدث:* {ev_disp}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ *خطأ:* `{e}`", parse_mode="Markdown")
    await update.message.reply_text("العودة:", reply_markup=_back_kb("admin_events"))
    return ConversationHandler.END


@_admin_required
async def admin_delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("📱 AppsFlyer", callback_data="del_event_af")],
        [InlineKeyboardButton("📊 Adjust",    callback_data="del_event_adj")],
        [InlineKeyboardButton("🌟 Singular",  callback_data="del_event_singular")],
        [InlineKeyboardButton("🔙 رجوع",      callback_data="admin_events")],
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


# ==================== Subscription Plans Management ====================

@_admin_required
async def admin_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plans = db.get_all_plans()
    text  = "📦 *إدارة الباقات*\n\n"
    for p in plans:
        status = "✅" if p.get("is_active") else "❌"
        text += f"{status} *{p['name']}* — {p['price']}$ | {p['daily_limit']} عملية/يوم | {p['duration_days']} يوم\n"

    kb = [
        [InlineKeyboardButton("➕ إضافة باقة",       callback_data="admin_plan_add")],
        [InlineKeyboardButton("🗑️ حذف باقة",        callback_data="admin_plan_delete")],
        [InlineKeyboardButton("🔄 تفعيل/تعطيل",     callback_data="admin_plan_toggle")],
        [InlineKeyboardButton("🔙 رجوع",              callback_data="admin_panel")],
    ]
    await query.edit_message_text(text or "لا توجد باقات", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def admin_plan_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📦 *اسم الباقة الجديدة:*\nمثال: باقة يومية", parse_mode="Markdown")
    return PLAN_ADD_NAME


@_admin_required
async def plan_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_plan_name"] = update.message.text.strip()
    await update.message.reply_text("⏳ *المدة بالأيام:*\nمثال: 7", parse_mode="Markdown")
    return PLAN_ADD_DAYS


@_admin_required
async def plan_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["new_plan_days"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return PLAN_ADD_DAYS
    await update.message.reply_text("💰 *السعر بالدولار:*\nمثال: 5.00", parse_mode="Markdown")
    return PLAN_ADD_PRICE


@_admin_required
async def plan_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["new_plan_price"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return PLAN_ADD_PRICE
    await update.message.reply_text("📊 *الحد اليومي للعمليات:*\nمثال: 15", parse_mode="Markdown")
    return PLAN_ADD_LIMIT


@_admin_required
async def plan_add_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return PLAN_ADD_LIMIT
    name  = context.user_data.get("new_plan_name")
    days  = context.user_data.get("new_plan_days")
    price = context.user_data.get("new_plan_price")
    db.add_plan(name, days, price, limit)
    await update.message.reply_text(
        f"✅ *تمت إضافة الباقة!*\n\n"
        f"📦 *{name}*\n"
        f"💰 {price}$ | 📊 {limit} عملية/يوم | ⏳ {days} يوم",
        parse_mode="Markdown",
        reply_markup=_back_kb("admin_plans"),
    )
    return ConversationHandler.END


@_admin_required
async def admin_plan_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plans = db.get_all_plans()
    kb = [[InlineKeyboardButton(p["name"], callback_data=f"plan_del_confirm_{p['id']}")] for p in plans]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_plans")])
    await query.edit_message_text("🗑️ *اختر الباقة للحذف:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def plan_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_del_confirm_", ""))
    db.delete_plan(plan_id)
    await query.edit_message_text("✅ *تم حذف الباقة*", parse_mode="Markdown", reply_markup=_back_kb("admin_plans"))


@_admin_required
async def admin_plan_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plans = db.get_all_plans()
    kb = []
    for p in plans:
        status = "✅ نشطة" if p.get("is_active") else "❌ معطلة"
        kb.append([InlineKeyboardButton(f"{p['name']} ({status})", callback_data=f"plan_toggle_{p['id']}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_plans")])
    await query.edit_message_text("🔄 *اختر باقة لتفعيل/تعطيل:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def plan_toggle_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("plan_toggle_", ""))
    plan = db.get_plan_by_id(plan_id)
    if plan:
        db.toggle_plan(plan_id, not plan.get("is_active", True))
        new_status = "معطلة" if plan.get("is_active") else "نشطة"
        await query.edit_message_text(
            f"✅ تم تغيير الحالة → *{new_status}*",
            parse_mode="Markdown",
            reply_markup=_back_kb("admin_plans"),
        )


# ==================== Payment Settings Management ====================

@_admin_required
async def admin_pay_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    settings = db.get_all_payment_settings()
    text = "💳 *إعدادات طرق الدفع*\n\n"
    for s in settings:
        addr  = s.get("address") or "⚠️ لم يُعيَّن"
        text += f"• *{s['display_name']}* (`{s['method']}`)\n  📬 {addr[:40]}...\n\n" if len(str(addr)) > 40 else f"• *{s['display_name']}* (`{s['method']}`)\n  📬 {addr}\n\n"

    methods = [s["method"] for s in settings]
    kb = [[InlineKeyboardButton(s["display_name"], callback_data=f"pay_edit_{s['method']}")] for s in settings]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def pay_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_edit_", "")
    s = db.get_payment_setting(method)
    if not s:
        await query.edit_message_text("❌ طريقة الدفع غير موجودة", reply_markup=_back_kb("admin_pay_settings"))
        return
    context.user_data["pay_method"] = method
    addr  = s.get("address") or "غير محدد"
    instr = s.get("instructions") or "غير محدد"
    has_binance = method == "usdt"

    text = (
        f"💳 *{s['display_name']}*\n\n"
        f"📬 العنوان: `{addr}`\n"
        f"📝 التعليمات: {instr[:100]}\n"
    )
    if has_binance:
        key = s.get("binance_api_key") or "غير محدد"
        text += f"🔑 Binance API Key: `{key[:10]}...`\n" if key != "غير محدد" else "🔑 Binance API Key: غير محدد\n"

    kb = [
        [InlineKeyboardButton("📬 تغيير العنوان",      callback_data=f"pay_set_addr_{method}")],
        [InlineKeyboardButton("📝 تغيير التعليمات",    callback_data=f"pay_set_instr_{method}")],
    ]
    if has_binance:
        kb.append([InlineKeyboardButton("🔑 Binance API Key",    callback_data=f"pay_set_bkey_{method}")])
        kb.append([InlineKeyboardButton("🔒 Binance API Secret", callback_data=f"pay_set_bsecret_{method}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_pay_settings")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@_admin_required
async def pay_set_addr_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_set_addr_", "")
    context.user_data["pay_method"] = method
    context.user_data["pay_edit_field"] = "address"
    await query.edit_message_text(f"📬 *أدخل العنوان الجديد لـ {method}:*", parse_mode="Markdown")
    return PAY_SET_ADDR


@_admin_required
async def pay_set_instr_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_set_instr_", "")
    context.user_data["pay_method"] = method
    context.user_data["pay_edit_field"] = "instructions"
    await query.edit_message_text(f"📝 *أدخل التعليمات الجديدة لـ {method}:*", parse_mode="Markdown")
    return PAY_SET_INSTR


@_admin_required
async def pay_set_bkey_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_set_bkey_", "")
    context.user_data["pay_method"] = method
    context.user_data["pay_edit_field"] = "binance_api_key"
    await query.edit_message_text("🔑 *أدخل Binance API Key:*", parse_mode="Markdown")
    return PAY_BINANCE_KEY


@_admin_required
async def pay_set_bsecret_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_set_bsecret_", "")
    context.user_data["pay_method"] = method
    context.user_data["pay_edit_field"] = "binance_api_secret"
    await query.edit_message_text("🔒 *أدخل Binance API Secret:*", parse_mode="Markdown")
    return PAY_BINANCE_SECRET


async def _pay_save_field(update, context):
    value  = update.message.text.strip()
    method = context.user_data.get("pay_method")
    field  = context.user_data.get("pay_edit_field")
    db.update_payment_setting_field(method, field, value)
    await update.message.reply_text(
        f"✅ *تم الحفظ!*",
        parse_mode="Markdown",
        reply_markup=_back_kb("admin_pay_settings"),
    )
    return ConversationHandler.END


pay_set_addr_save    = _admin_required(lambda u, c: _pay_save_field(u, c))
pay_set_instr_save   = _admin_required(lambda u, c: _pay_save_field(u, c))
pay_set_bkey_save    = _admin_required(lambda u, c: _pay_save_field(u, c))
pay_set_bsecret_save = _admin_required(lambda u, c: _pay_save_field(u, c))


# ==================== Pending Subscription Requests ====================

@_admin_required
async def admin_sub_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reqs = db.get_pending_requests()
    if not reqs:
        await query.edit_message_text(
            "📋 *لا توجد طلبات معلقة*",
            parse_mode="Markdown",
            reply_markup=_back_kb(),
        )
        return
    text = f"📋 *الطلبات المعلقة ({len(reqs)}):*\n\n"
    kb   = []
    for r in reqs[:15]:
        text += f"• #{r['id']} | {r['user_name']} | {r['plan_name']} | {r['method']}\n"
        kb.append([
            InlineKeyboardButton(f"✅ #{r['id']}", callback_data=f"sub_approve_{r['id']}"),
            InlineKeyboardButton(f"❌ #{r['id']}", callback_data=f"sub_reject_{r['id']}"),
        ])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    await query.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ==================== Grant Subscription ====================

@_admin_required
async def admin_grant_sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎁 *منح اشتراك*\n\nأدخل ID المستخدم:",
        parse_mode="Markdown",
    )
    return GRANT_SUB_USER


@_admin_required
async def grant_sub_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ معرف غير صالح")
        return GRANT_SUB_USER

    user = db.get_user_by_id(uid)
    if not user:
        await update.message.reply_text(
            "❌ المستخدم غير موجود في قاعدة البيانات\n"
            "يجب أن يكون المستخدم قد أرسل /start أولاً."
        )
        return GRANT_SUB_USER

    context.user_data["grant_uid"] = uid
    plans = db.get_all_plans()
    kb = [[InlineKeyboardButton(f"{p['name']} ({p['duration_days']} يوم)", callback_data=f"grant_plan_{p['id']}")] for p in plans]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    await update.message.reply_text(
        f"👤 المستخدم: `{uid}`\n\n📦 *اختر الباقة:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return GRANT_SUB_PLAN


@_admin_required
async def grant_sub_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.replace("grant_plan_", ""))
    plan    = db.get_plan_by_id(plan_id)
    uid     = context.user_data.get("grant_uid")

    if not plan or not uid:
        await query.edit_message_text("❌ خطأ في البيانات", reply_markup=_back_kb())
        return ConversationHandler.END

    db.create_subscription(uid, plan["id"], plan["name"], plan["duration_days"], plan["daily_limit"])
    await query.edit_message_text(
        f"✅ *تم منح الاشتراك!*\n\n"
        f"👤 المستخدم: `{uid}`\n"
        f"📦 الباقة: *{plan['name']}*\n"
        f"⏳ المدة: {plan['duration_days']} يوم",
        parse_mode="Markdown",
        reply_markup=_back_kb(),
    )

    try:
        await context.bot.send_message(
            uid,
            f"🎉 *تم تفعيل اشتراكك!*\n\n"
            f"📦 الباقة: *{plan['name']}*\n"
            f"📊 الحد اليومي: `{plan['daily_limit']}` عملية\n"
            f"⏳ مدة الباقة: `{plan['duration_days']}` يوم",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    return ConversationHandler.END


# ==================== Conversation handler ====================

def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        states={
            ADMIN_ADD_USER:     [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_user_process)],
            ADMIN_REMOVE_USER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_user_process)],
            ADMIN_BAN:          [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_process)],
            ADMIN_UNBAN:        [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_process)],
            ADMIN_BROADCAST_MSG:[MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
            ADD_GAME_TYPE: [
                CallbackQueryHandler(add_game_af,       pattern="^add_game_af$"),
                CallbackQueryHandler(add_game_adj,      pattern="^add_game_adj$"),
                CallbackQueryHandler(add_game_singular, pattern="^add_game_singular$"),
            ],
            ADD_GAME_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_name)],
            ADD_GAME_DISPLAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_display)],
            ADD_GAME_PACKAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_package)],
            ADD_GAME_KEY:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_key)],
            ADD_GAME_EMOJI:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_emoji)],
            ADD_EVENT_TYPE:   [CallbackQueryHandler(add_event_type_select, pattern=r"^add_event_type_")],
            ADD_EVENT_GAME:   [CallbackQueryHandler(add_event_game_select, pattern=r"^add_event_game_\d+$")],
            ADD_EVENT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_name)],
            ADD_EVENT_DISPLAY:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_display)],
            ADD_EVENT_TOKEN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_token)],
            DEL_GAME_TYPE:    [CallbackQueryHandler(del_game_type_select, pattern=r"^del_game_(af|adj|singular)$")],
            DEL_GAME_SELECT:  [CallbackQueryHandler(del_game_confirm, pattern=r"^del_game_confirm_")],
            DEL_EVENT_TYPE:   [CallbackQueryHandler(del_event_type_select, pattern=r"^del_event_(af|adj|singular)$")],
            DEL_EVENT_GAME:   [CallbackQueryHandler(del_event_game_select, pattern=r"^del_event_game_\d+$")],
            DEL_EVENT_SELECT: [CallbackQueryHandler(del_event_confirm, pattern=r"^del_event_confirm_\d+$")],
            # Subscription plan states
            PLAN_ADD_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_name)],
            PLAN_ADD_DAYS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_days)],
            PLAN_ADD_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_price)],
            PLAN_ADD_LIMIT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_add_limit)],
            # Payment settings states
            PAY_SET_ADDR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_set_addr_save)],
            PAY_SET_INSTR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_set_instr_save)],
            PAY_BINANCE_KEY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_set_bkey_save)],
            PAY_BINANCE_SECRET:[MessageHandler(filters.TEXT & ~filters.COMMAND, pay_set_bsecret_save)],
            # Grant sub states
            GRANT_SUB_USER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, grant_sub_user)],
            GRANT_SUB_PLAN:   [CallbackQueryHandler(grant_sub_plan, pattern=r"^grant_plan_\d+$")],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        allow_reentry=True,
    )


def get_handlers():
    return [
        get_conversation_handler(),
        CallbackQueryHandler(admin_stats,          pattern="^admin_stats$"),
        CallbackQueryHandler(admin_users,          pattern="^admin_users$"),
        CallbackQueryHandler(admin_allowed_list,   pattern="^admin_allowed_list$"),
        CallbackQueryHandler(admin_banned_list,    pattern="^admin_banned_list$"),
        CallbackQueryHandler(admin_add_user_prompt,  pattern="^admin_add_user$"),
        CallbackQueryHandler(admin_remove_user_prompt, pattern="^admin_remove_user$"),
        CallbackQueryHandler(admin_ban_prompt,     pattern="^admin_ban$"),
        CallbackQueryHandler(admin_unban_prompt,   pattern="^admin_unban$"),
        CallbackQueryHandler(admin_broadcast_prompt, pattern="^admin_broadcast$"),
        CallbackQueryHandler(admin_games,          pattern="^admin_games$"),
        CallbackQueryHandler(admin_add_game_type,  pattern="^admin_add_game$"),
        CallbackQueryHandler(admin_delete_game,    pattern="^admin_delete_game$"),
        CallbackQueryHandler(admin_events,         pattern="^admin_events$"),
        CallbackQueryHandler(admin_add_event_type, pattern="^admin_add_event$"),
        CallbackQueryHandler(admin_delete_event,   pattern="^admin_delete_event$"),
        # Plans
        CallbackQueryHandler(admin_plans,          pattern="^admin_plans$"),
        CallbackQueryHandler(admin_plan_add_start, pattern="^admin_plan_add$"),
        CallbackQueryHandler(admin_plan_delete,    pattern="^admin_plan_delete$"),
        CallbackQueryHandler(plan_del_confirm,     pattern=r"^plan_del_confirm_\d+$"),
        CallbackQueryHandler(admin_plan_toggle,    pattern="^admin_plan_toggle$"),
        CallbackQueryHandler(plan_toggle_exec,     pattern=r"^plan_toggle_\d+$"),
        # Payment settings
        CallbackQueryHandler(admin_pay_settings,   pattern="^admin_pay_settings$"),
        CallbackQueryHandler(pay_edit_select,      pattern=r"^pay_edit_"),
        CallbackQueryHandler(pay_set_addr_prompt,  pattern=r"^pay_set_addr_"),
        CallbackQueryHandler(pay_set_instr_prompt, pattern=r"^pay_set_instr_"),
        CallbackQueryHandler(pay_set_bkey_prompt,  pattern=r"^pay_set_bkey_"),
        CallbackQueryHandler(pay_set_bsecret_prompt, pattern=r"^pay_set_bsecret_"),
        # Subscription requests & grant
        CallbackQueryHandler(admin_sub_requests,   pattern="^admin_sub_requests$"),
        CallbackQueryHandler(admin_grant_sub_start, pattern="^admin_grant_sub$"),
    ]
