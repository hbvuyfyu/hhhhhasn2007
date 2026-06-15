import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.config import ADMIN_IDS
from src.database import queries as db
from src.services.binance import verify_usdt_deposit

logger = logging.getLogger(__name__)

SUB_SELECT_METHOD, SUB_USDT_TX, SUB_CASH_PROOF = range(700, 703)


# ── helpers ───────────────────────────────────────────────

def _back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]])

def _back_sub() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sub_menu")]])


# ── عرض الباقات ───────────────────────────────────────────

async def sub_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = update.effective_user.id
    db.upsert_user(uid, update.effective_user.username or "", update.effective_user.full_name or "")

    sub = db.get_active_subscription(uid)
    sub_text = ""
    if sub and uid not in ADMIN_IDS:
        used  = sub.get("daily_used", 0)
        limit = sub.get("daily_limit", 0)
        sub_text = f"\n\n✅ *اشتراكك الحالي:* {sub.get('plan_name','')}\n📊 الاستخدام اليوم: `{used}/{limit}`"

    plans = db.get_active_plans()
    if not plans:
        await query.edit_message_text(
            "📦 *الاشتراك*\n\nلا توجد باقات متاحة حالياً.",
            parse_mode="Markdown",
            reply_markup=_back_main(),
        )
        return ConversationHandler.END

    kb = []
    for p in plans:
        label = f"{p['name']} — {p['price']}$ | {p['daily_limit']} عملية/يوم | {p['duration_days']} يوم"
        kb.append([InlineKeyboardButton(label, callback_data=f"sub_plan_{p['id']}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])

    text = f"📦 *اختر الباقة المناسبة:*{sub_text}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return SUB_SELECT_METHOD


# ── اختيار الباقة → طرق الدفع ────────────────────────────

async def sub_select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.replace("sub_plan_", ""))
    plan = db.get_plan_by_id(plan_id)
    if not plan:
        await query.edit_message_text("❌ الباقة غير موجودة", reply_markup=_back_sub())
        return ConversationHandler.END

    context.user_data["sub_plan"] = plan

    methods = db.get_active_payment_settings()
    if not methods:
        await query.edit_message_text(
            "❌ لا توجد طرق دفع متاحة حالياً\nيرجى التواصل مع الإدارة.",
            parse_mode="Markdown",
            reply_markup=_back_sub(),
        )
        return ConversationHandler.END

    kb = []
    for m in methods:
        kb.append([InlineKeyboardButton(m["display_name"], callback_data=f"sub_method_{m['method']}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="sub_menu")])

    text = (
        f"💳 *اختر طريقة الدفع*\n\n"
        f"📦 الباقة: *{plan['name']}*\n"
        f"💰 السعر: `{plan['price']}$`\n"
        f"📊 الحد اليومي: `{plan['daily_limit']}` عملية\n"
        f"⏳ المدة: `{plan['duration_days']}` يوم"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return SUB_SELECT_METHOD


# ── USDT ──────────────────────────────────────────────────

async def sub_method_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan    = context.user_data.get("sub_plan", {})
    setting = db.get_payment_setting("usdt")
    if not setting or not setting.get("address"):
        await query.edit_message_text(
            "❌ لم يتم إعداد عنوان USDT بعد\nيرجى التواصل مع الإدارة.",
            parse_mode="Markdown",
            reply_markup=_back_sub(),
        )
        return ConversationHandler.END

    context.user_data["sub_method"] = "usdt"
    context.user_data["sub_setting"] = dict(setting)

    instr = setting.get("instructions") or ""
    text = (
        f"💎 *الدفع عبر USDT (TRC20)*\n\n"
        f"📦 الباقة: *{plan.get('name','')}*\n"
        f"💰 المبلغ: `{plan.get('price',0)}$` USDT\n\n"
        f"📬 *عنوان المحفظة:*\n`{setting['address']}`\n\n"
        f"{instr}\n\n"
        f"✅ بعد الإرسال، أدخل *رقم عملية التحويل (TxID)*:"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_back_sub())
    return SUB_USDT_TX


async def sub_usdt_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_id = update.message.text.strip()
    user  = update.effective_user
    plan  = context.user_data.get("sub_plan", {})
    setting = context.user_data.get("sub_setting", {})

    await update.message.reply_text("⏳ *جاري التحقق من العملية...*", parse_mode="Markdown")

    api_key    = setting.get("binance_api_key", "")
    api_secret = setting.get("binance_api_secret", "")
    expected   = float(plan.get("price", 0))

    verified, msg = verify_usdt_deposit(api_key, api_secret, tx_id, expected)

    if verified:
        db.create_subscription(
            user_id=user.id,
            plan_id=plan["id"],
            plan_name=plan["name"],
            duration_days=plan["duration_days"],
            daily_limit=plan["daily_limit"],
        )
        db.process_payment_request_auto(
            user_id=user.id,
            user_name=user.full_name or "",
            user_username=user.username or "",
            plan_id=plan["id"],
            plan_name=plan["name"],
            method="usdt",
            amount=expected,
            transaction_id=tx_id,
        )
        await update.message.reply_text(
            f"🎉 *تم تفعيل اشتراكك!*\n\n"
            f"📦 الباقة: *{plan['name']}*\n"
            f"📊 الحد اليومي: `{plan['daily_limit']}` عملية\n"
            f"⏳ مدة الباقة: `{plan['duration_days']}` يوم\n\n"
            f"{msg}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
            ]]),
        )
    else:
        await update.message.reply_text(
            f"❌ *فشل التحقق*\n\n{msg}\n\nتأكد من رقم العملية وأعد المحاولة أو تواصل مع الإدارة.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="sub_menu")
            ]]),
        )

    return ConversationHandler.END


# ── شام كاش / سرياتيل كاش ────────────────────────────────

async def sub_method_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()

    method  = query.data.replace("sub_method_", "")
    plan    = context.user_data.get("sub_plan", {})
    setting = db.get_payment_setting(method)

    if not setting or not setting.get("address"):
        await query.edit_message_text(
            f"❌ لم يتم إعداد عنوان {method} بعد\nيرجى التواصل مع الإدارة.",
            parse_mode="Markdown",
            reply_markup=_back_sub(),
        )
        return ConversationHandler.END

    context.user_data["sub_method"]  = method
    context.user_data["sub_setting"] = dict(setting)

    instr = setting.get("instructions") or ""
    text = (
        f"💳 *الدفع عبر {setting['display_name']}*\n\n"
        f"📦 الباقة: *{plan.get('name','')}*\n"
        f"💰 المبلغ: `{plan.get('price',0)}$`\n\n"
        f"📬 *الرقم / الحساب:*\n`{setting['address']}`\n\n"
        f"{instr}\n\n"
        f"📷 بعد الإرسال، أرسل *صورة إثبات الدفع:*"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sub_menu")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return SUB_CASH_PROOF


async def sub_cash_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "❌ *يرجى إرسال صورة إثبات الدفع*",
            parse_mode="Markdown",
        )
        return SUB_CASH_PROOF

    user    = update.effective_user
    plan    = context.user_data.get("sub_plan", {})
    method  = context.user_data.get("sub_method", "")
    setting = context.user_data.get("sub_setting", {})
    photo   = update.message.photo[-1].file_id

    req_id = db.create_payment_request(
        user_id=user.id,
        user_name=user.full_name or "",
        user_username=user.username or "",
        plan_id=plan.get("id", 0),
        plan_name=plan.get("name", ""),
        method=method,
        amount=float(plan.get("price", 0)),
        proof_file_id=photo,
    )

    await update.message.reply_text(
        "✅ *تم استلام طلبك!*\n\n"
        "📋 جاري معالجة طلبك — يرجى الانتظار بضع دقائق.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
        ]]),
    )

    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ قبول", callback_data=f"sub_approve_{req_id}"),
                    InlineKeyboardButton("❌ رفض",  callback_data=f"sub_reject_{req_id}"),
                ]
            ])
            caption = (
                f"💳 *طلب اشتراك جديد* #{req_id}\n\n"
                f"👤 المستخدم: {user.full_name} (`{user.id}`)\n"
                f"🔖 يوزر: @{user.username or '-'}\n"
                f"📦 الباقة: *{plan.get('name','')}*\n"
                f"💰 المبلغ: `{plan.get('price',0)}$`\n"
                f"💳 طريقة الدفع: {setting.get('display_name', method)}"
            )
            await update.get_bot().send_photo(
                chat_id=admin_id,
                photo=photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=kb,
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    return ConversationHandler.END


# ── أدمن: قبول / رفض ─────────────────────────────────────

async def sub_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await query.answer("❌ غير مصرح", show_alert=True)
        return

    req_id = int(query.data.replace("sub_approve_", ""))
    req    = db.get_payment_request(req_id)
    if not req:
        await query.edit_message_caption("❌ الطلب غير موجود")
        return
    if req.get("status") != "pending":
        await query.answer("⚠️ تم معالجة هذا الطلب مسبقاً", show_alert=True)
        return

    plan = db.get_plan_by_id(req["plan_id"])
    if plan:
        db.create_subscription(
            user_id=req["user_id"],
            plan_id=plan["id"],
            plan_name=plan["name"],
            duration_days=plan["duration_days"],
            daily_limit=plan["daily_limit"],
        )
    db.process_payment_request(req_id, "approved", admin_id)

    try:
        await query.edit_message_caption(
            query.message.caption + "\n\n✅ *تم القبول*",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    try:
        await context.bot.send_message(
            req["user_id"],
            f"🎉 *تم تفعيل اشتراكك!*\n\n"
            f"📦 الباقة: *{req['plan_name']}*\n"
            f"📊 الحد اليومي: `{plan['daily_limit'] if plan else '?'}` عملية\n"
            f"⏳ مدة الباقة: `{plan['duration_days'] if plan else '?'}` يوم",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
            ]]),
        )
    except Exception:
        pass


async def sub_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await query.answer("❌ غير مصرح", show_alert=True)
        return

    req_id = int(query.data.replace("sub_reject_", ""))
    req    = db.get_payment_request(req_id)
    if not req:
        await query.edit_message_caption("❌ الطلب غير موجود")
        return
    if req.get("status") != "pending":
        await query.answer("⚠️ تم معالجة هذا الطلب مسبقاً", show_alert=True)
        return

    db.process_payment_request(req_id, "rejected", admin_id)

    try:
        await query.edit_message_caption(
            query.message.caption + "\n\n❌ *تم الرفض*",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    try:
        await context.bot.send_message(
            req["user_id"],
            "❌ *تم رفض طلب اشتراكك*\n\nيرجى التواصل مع الإدارة للمزيد من المعلومات.",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ── تسجيل الـ handlers ────────────────────────────────────

def get_handlers():
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(sub_menu, pattern="^sub_menu$")],
        states={
            SUB_SELECT_METHOD: [
                CallbackQueryHandler(sub_select_plan,  pattern=r"^sub_plan_\d+$"),
                CallbackQueryHandler(sub_method_usdt,  pattern="^sub_method_usdt$"),
                CallbackQueryHandler(sub_method_cash,  pattern=r"^sub_method_(sham_cash|syriatel_cash)$"),
            ],
            SUB_USDT_TX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sub_usdt_tx),
            ],
            SUB_CASH_PROOF: [
                MessageHandler(filters.PHOTO, sub_cash_proof),
            ],
        },
        fallbacks=[CallbackQueryHandler(sub_menu, pattern="^sub_menu$")],
        allow_reentry=True,
        name="subscription_conv",
        persistent=False,
    )
    return [
        conv,
        CallbackQueryHandler(sub_approve, pattern=r"^sub_approve_\d+$"),
        CallbackQueryHandler(sub_reject,  pattern=r"^sub_reject_\d+$"),
    ]
