import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.config import ADMIN_IDS, CHANNEL_ID, CHANNEL_LINK
from src.database import queries as db
from src.middlewares.auth import require_access, allow_free_access
from src.utils.navigation import nav_clear

logger = logging.getLogger(__name__)


async def check_channel_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is subscribed to the required channel."""
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking channel subscription: {e}")
        return False


@allow_free_access
async def channel_subscribe_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show subscription prompt with buttons."""
    uid = update.effective_user.id

    # Check if already subscribed
    is_subscribed = await check_channel_subscription(uid, context)
    if is_subscribed:
        db.set_channel_subscribed(uid, True)
        await start(update, context)
        return

    text = (
        "🔔 *اشترك بالقناة اولاً حتى تتمكن من المتابعة*\n\n"
        f"📌 القناة: {CHANNEL_LINK}\n\n"
        "👉 اضغط على زر الاشتراك ثم تحقق"
    )
    kb = [
        [InlineKeyboardButton("📢 اشترك بالقناة", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ تحقق", callback_data="check_subscription")]
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@allow_free_access
async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify user subscription to channel."""
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    is_subscribed = await check_channel_subscription(uid, context)
    if is_subscribed:
        db.set_channel_subscribed(uid, True)
        await query.answer("✅ تم التحقق بنجاح!", show_alert=True)
        await start(update, context)
    else:
        await query.answer("❌ لم يتم الاشتراك بعد", show_alert=True)


def _build_main_keyboard(uid: int) -> InlineKeyboardMarkup:
    platform = db.get_user_platform(uid)
    platform_emoji = "🤖" if platform == "android" else "🍎"
    sub = db.get_active_subscription(uid)

    kb = []
    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])

    # Show subscription status
    if sub and uid not in ADMIN_IDS:
        used = sub.get("daily_used", 0)
        limit = sub.get("daily_limit", 0)
        sub_btn = InlineKeyboardButton(f"📦 اشتراكك ({used}/{limit})", callback_data="sub_menu")
    else:
        sub_btn = InlineKeyboardButton("📦 اشتراك", callback_data="sub_menu")

    kb.append([sub_btn])
    kb.append([InlineKeyboardButton("📱 AppsFlyer", callback_data="af_menu")])
    kb.append([InlineKeyboardButton("📊 Adjust", callback_data="adj_menu")])
    kb.append([InlineKeyboardButton("🌟 Singular", callback_data="singular_menu")])
    kb.append([InlineKeyboardButton("🌾 مزرعة الجمبرة", callback_data="jumper_farm")])
    kb.append([InlineKeyboardButton("🗓 جدولة عمليات", callback_data="sched_menu")])
    kb.append([InlineKeyboardButton("🔧 إعدادات البروكسي", callback_data="proxy_settings")])
    kb.append([InlineKeyboardButton(f"{platform_emoji} نظام التشغيل", callback_data="select_platform")])
    return InlineKeyboardMarkup(kb)


@allow_free_access
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # Skip channel check for admins
    if uid not in ADMIN_IDS:
        # Check channel subscription
        sub_record = db.get_channel_subscription(uid)
        if sub_record and sub_record.get("subscribed"):
            # Already verified before
            pass
        else:
            # Check if subscribed
            is_subscribed = await check_channel_subscription(uid, context)
            if not is_subscribed:
                await channel_subscribe_prompt(update, context)
                return

    platform = db.get_user_platform(uid)
    platform_name = "Android 🤖" if platform == "android" else "iOS 🍎"

    sub = db.get_active_subscription(uid)
    sub_text = ""
    if sub and uid not in ADMIN_IDS:
        used = sub.get("daily_used", 0)
        limit = sub.get("daily_limit", 0)
        remaining = limit - used
        sub_text = f"\n📦 *اشتراكك:* {sub.get('plan_name', '')} | متبقي: `{remaining}/{limit}` عملية"

    text = (
        "🔥 *AK Jumper Bot* 🔥\n\n"
        "✨ *اختر الخدمة* ✨\n\n"
        "┃ 📱 AppsFlyer\n"
        "┃ 📊 Adjust\n"
        "┃ 🌟 Singular\n"
        "┃ 🌾 مزرعة الجمبرة\n"
        "┃ 🗓 جدولة عمليات\n"
        "┃ 🔧 بروكسي\n\n"
        f"📱 النظام الحالي: {platform_name}"
        f"{sub_text}"
    )

    kb = _build_main_keyboard(uid)

    # Clear navigation stack when reaching main menu
    nav_clear(context)

    if update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


@allow_free_access
async def clean_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.set_user_platform(uid, "android")
    await update.message.reply_text(
        "✅ *تم التنظيف الشامل*\n\nالمنصة: Android\nاستخدم /start للبدء.",
        parse_mode="Markdown",
    )


@allow_free_access
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the persistent back button - navigate to previous screen."""
    from src.utils.navigation import nav_pop, nav_peek
    prev = nav_pop(context)
    if not prev:
        prev = "main_menu"

    # Replay the callback_data as if user pressed that button
    query = update.callback_query
    if query:
        await query.answer()
    # Create a fake callback by dispatching the callback_data
    # We'll handle it by directly calling the target handler
    await _dispatch_back(update, context, prev)


async def _dispatch_back(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Dispatch back navigation to the appropriate handler."""
    query = update.callback_query

    if target == "main_menu":
        await start(update, context)
        return

    # For sub-menus, we need to re-enter the appropriate menu
    handler_map = {
        "af_menu": _back_af_menu,
        "adj_menu": _back_adj_menu,
        "singular_menu": _back_singular_menu,
        "jumper_farm": _back_farm_menu,
        "proxy_settings": _back_proxy_menu,
        "sub_menu": _back_sub_menu,
        "select_platform": _back_platform_menu,
        "sched_menu": _back_sched_menu,
        "admin_panel": _back_admin_panel,
        "admin_games": _back_admin_games,
        "admin_events": _back_admin_events,
        "admin_payment": _back_admin_payment,
        "admin_plans": _back_admin_plans,
    }

    handler = handler_map.get(target)
    if handler:
        await handler(update, context)
    else:
        # Fallback to main menu
        await start(update, context)


async def _back_af_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.af_handler import af_menu
    await af_menu(update, context)


async def _back_adj_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.adj_handler import adj_menu
    await adj_menu(update, context)


async def _back_singular_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.singular_handler import singular_menu
    await singular_menu(update, context)


async def _back_farm_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.farm_handler import jumper_farm_menu
    await jumper_farm_menu(update, context)


async def _back_sched_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.schedule_handler import sched_menu
    await sched_menu(update, context)


async def _back_proxy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.proxy_handler import proxy_settings
    await proxy_settings(update, context)


async def _back_sub_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Re-enter subscription conversation
    from src.handlers.subscription_handler import sub_menu
    await sub_menu(update, context)


async def _back_platform_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.platform_handler import select_platform
    await select_platform(update, context)


async def _back_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.admin_handler import admin_panel
    await admin_panel(update, context)


async def _back_admin_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.admin_handler import admin_games
    await admin_games(update, context)


async def _back_admin_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.admin_handler import admin_events
    await admin_events(update, context)


async def _back_admin_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.admin_handler import admin_payment
    await admin_payment(update, context)


async def _back_admin_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.handlers.admin_handler import admin_plans
    await admin_plans(update, context)


def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("clean", clean_start),
        CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"),
    ]
