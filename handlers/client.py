# handlers/client.py — Client Panel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import APP_NO, APP_DOB, APP_PASS, PAY_AMOUNT, SUPER_ADMIN_ID
from keyboards import kb_client, REMOVE
from db import (find_client, get_setting, get_balance, deduct_balance,
                add_app, add_payment, inc_client_apps, queue_add,
                agent_by_id, set_client_field)
from utils import user_data, now_ist, today_ist, gen_app_id, gen_pay_id, valid_dob, safe_float, divider
import logging
logger = logging.getLogger(__name__)


# ── New Application ───────────────────────────────────────────
async def new_app_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid    = update.effective_user.id
    c, ag  = find_client(tid)
    if not c or not ag:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return ConversationHandler.END
    if c.get("status") == "blocked":
        await update.message.reply_text("🚫 Account block hai.", reply_markup=kb_client())
        return ConversationHandler.END
    rate = safe_float(ag.get("rate_per_app", 0))
    bal  = get_balance(ag, c["client_code"])
    if bal < rate:
        await update.message.reply_text(
            f"⚠️ Balance kam hai!\n💰 Balance: Rs{bal}\n💳 Required: Rs{rate}\n\nPehle balance add karo:",
            reply_markup=kb_client())
        await _show_qr(update, ctx, c, ag)
        return ConversationHandler.END
    user_data(tid)["app_agent"]  = ag
    user_data(tid)["app_client"] = c
    await update.message.reply_text(
        f"📋 *New Application*\n\n💰 Balance: Rs{bal} | Rate: Rs{rate}\n\nStep 1/3 — Application Number:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=REMOVE)
    return APP_NO

async def app_no(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    no  = update.message.text.strip()
    if len(no) < 3:
        await update.message.reply_text("❌ Valid application number daalo:")
        return APP_NO
    user_data(tid)["app_no"] = no
    await update.message.reply_text("Step 2/3 — Date of Birth (DD/MM/YYYY):")
    return APP_DOB

async def app_dob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    dob = update.message.text.strip()
    if not valid_dob(dob):
        await update.message.reply_text("❌ Valid DOB daalo (DD/MM/YYYY):")
        return APP_DOB
    user_data(tid)["app_dob"] = dob
    await update.message.reply_text("Step 3/3 — Password:")
    return APP_PASS

async def app_pass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid  = update.effective_user.id
    pwd  = update.message.text.strip()
    d    = user_data(tid)
    ag   = d.get("app_agent")
    c    = d.get("app_client")
    if not ag or not c:
        await update.message.reply_text("❌ Session expire. Dobara try karo.", reply_markup=kb_client())
        return ConversationHandler.END

    rate   = safe_float(ag.get("rate_per_app", 0))
    app_id = gen_app_id()

    # Deduct balance
    deduct_balance(ag, c["client_code"], rate)
    inc_client_apps(ag, c["client_code"])

    # Save to agent's applications sheet
    add_app(ag, {"app_id":app_id,"app_no":d["app_no"],"dob":d["app_dob"],
                 "password":pwd,"client_code":c["client_code"]})

    # Add to GLOBAL QUEUE → Admin directly process karega
    queue_add({
        "queue_id":    app_id,
        "app_no":      d["app_no"],
        "dob":         d["app_dob"],
        "password":    pwd,
        "client_code": c["client_code"],
        "client_name": c.get("full_name",""),
        "agent_id":    ag.get("agent_id",""),
        "agent_name":  ag.get("agent_name",""),
        "priority":    "normal",
    })

    bal_left = get_balance(ag, c["client_code"])
    await update.message.reply_text(
        f"✅ *Application Submitted!*\n\n"
        f"🆔 App ID: `{app_id}`\n"
        f"📄 App No: {d['app_no']}\n"
        f"📅 DOB: {d['app_dob']}\n"
        f"💰 Balance remaining: Rs{bal_left}\n\n"
        f"⏳ Processing queue mein hai. Done hone par notify karenge!",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())

    # Notify AGENT
    try:
        await ctx.bot.send_message(
            int(ag["telegram_id"]),
            f"🔔 *Naya Application Queue mein!*\n\n"
            f"👤 Client: {c.get('full_name')} (`{c['client_code']}`)\n"
            f"📄 App No: {d['app_no']}\n"
            f"📅 DOB: {d['app_dob']}\n"
            f"🆔 Queue ID: `{app_id}`",
            parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass

    # Notify ADMIN
    try:
        done_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ DONE", callback_data=f"QDONE|{app_id}|{c['client_code']}|{ag['agent_id']}|{ag['telegram_id']}|{tid}")
        ]])
        await ctx.bot.send_message(
            SUPER_ADMIN_ID,
            f"📥 *New Application*\n{divider()}\n"
            f"🆔 Queue ID: `{app_id}`\n"
            f"📄 App No: `{d['app_no']}`\n"
            f"📅 DOB: `{d['app_dob']}`\n"
            f"🔒 Password: `{pwd}`\n"
            f"{divider()}\n"
            f"👤 Client: {c.get('full_name')} | `{c['client_code']}`\n"
            f"🧑‍💼 Agent: {ag.get('agent_name')} | `{ag.get('agent_id')}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=done_kb)
    except Exception as e:
        logger.error(f"admin notify: {e}")

    return ConversationHandler.END


# ── QR / Pay ─────────────────────────────────────────────────
async def _show_qr(update, ctx, c, ag):
    qr = get_setting(ag, "qr_file_id")
    if qr:
        try:
            await ctx.bot.send_photo(update.effective_user.id, qr,
                caption=f"💳 QR se payment karo\nRate: Rs{ag.get('rate_per_app')}/app\nPhir amount type karo:")
            user_data(update.effective_user.id)["awaiting_pay_amount"] = True
            user_data(update.effective_user.id)["pay_agent"]  = ag
            user_data(update.effective_user.id)["pay_client"] = c
        except Exception:
            await update.message.reply_text("QR set nahi hai. Agent se contact karo.", reply_markup=kb_client())
    else:
        await update.message.reply_text("💳 Agent se payment karo aur unhe batao.", reply_markup=kb_client())

async def pay_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    c, ag = find_client(tid)
    if not c or not ag:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return
    await _show_qr(update, ctx, c, ag)

async def handle_pay_amount_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    d   = user_data(tid)
    try:
        amount = safe_float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("❌ Valid amount daalo:")
        return
    ag = d.get("pay_agent")
    c  = d.get("pay_client")
    if not ag or not c:
        await update.message.reply_text("❌ Session expire. Dobara try karo.", reply_markup=kb_client())
        d.pop("awaiting_pay_amount", None)
        return
    pay_id = gen_pay_id()
    add_payment(ag, {"pay_id":pay_id,"client_code":c["client_code"],"amount":amount})
    d.pop("awaiting_pay_amount", None)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"PAY_APP|{pay_id}|{c['client_code']}|{ag['agent_id']}|{tid}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"PAY_REJ|{pay_id}|{c['client_code']}|{ag['agent_id']}|{tid}"),
    ]])
    await update.message.reply_text(
        f"⏳ Payment request bheja:\nAmount: Rs{amount}\nAgent approve karega.", reply_markup=kb_client())
    try:
        await ctx.bot.send_message(int(ag["telegram_id"]),
            f"💰 *Payment Request*\n👤 {c.get('full_name')} (`{c['client_code']}`)\n💵 Rs{amount}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


# ── Other client functions ────────────────────────────────────
async def my_apps(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    c, ag = find_client(tid)
    if not c:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return
    from db import queue_all
    all_q   = queue_all()
    my_apps = [r for r in all_q if r.get("client_code") == c.get("client_code")]
    if not my_apps:
        await update.message.reply_text("📋 Koi application nahi.", reply_markup=kb_client())
        return
    await update.message.reply_text(f"📋 *My Applications ({len(my_apps)})*", parse_mode=ParseMode.MARKDOWN)
    for ap in my_apps[-10:]:
        st   = ap.get("status","")
        icon = "✅" if st == "DONE" else "⏳"
        await update.message.reply_text(
            f"{icon} `{ap.get('queue_id')}`\n📄 {ap.get('app_no')} | 📅 {ap.get('dob')}\n🕐 {ap.get('submitted_at','')[:16]}",
            parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("─", reply_markup=kb_client())

async def my_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await my_apps(update, ctx)

async def my_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    c, ag = find_client(tid)
    if not c:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return
    bal  = get_balance(ag, c["client_code"])
    rate = safe_float(ag.get("rate_per_app", 0))
    await update.message.reply_text(
        f"💰 *My Balance*\n{divider()}\n"
        f"💵 Balance: Rs{bal}\n"
        f"📋 Rate: Rs{rate}/app\n"
        f"📊 Apps possible: {int(bal//rate) if rate else 0}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())

async def my_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    c, ag = find_client(tid)
    if not c:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return
    await update.message.reply_text(
        f"ℹ️ *My Profile*\n{divider()}\n"
        f"🆔 {c.get('client_code')}\n"
        f"👤 {c.get('full_name')}\n"
        f"📱 {c.get('phone')}\n"
        f"🧑‍💼 Agent: {ag.get('agent_name')}\n"
        f"📅 Joined: {c.get('joined_at','')[:10]}\n"
        f"📋 Total Apps: {c.get('total_apps',0)}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())

async def contact_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    c, ag = find_client(tid)
    if not c:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return
    await update.message.reply_text(
        f"📞 *Agent Contact*\n{divider()}\n"
        f"👤 {ag.get('agent_name')}\n"
        f"📱 {ag.get('phone')}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())

async def today_summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    c, ag = find_client(tid)
    if not c:
        await update.message.reply_text("❌ Registered nahi hain.", reply_markup=kb_client())
        return
    today = today_ist()
    from db import queue_all
    all_q    = queue_all()
    today_my = [r for r in all_q
                if r.get("client_code") == c["client_code"]
                and r.get("submitted_at","").startswith(today)]
    done    = sum(1 for r in today_my if r.get("status") == "DONE")
    pending = sum(1 for r in today_my if r.get("status") == "PENDING")
    await update.message.reply_text(
        f"📊 *Today Summary*\n{divider()}\n"
        f"📋 Submitted: {len(today_my)}\n"
        f"✅ Done: {done}\n"
        f"⏳ Pending: {pending}\n"
        f"💰 Balance: Rs{get_balance(ag, c['client_code'])}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())
