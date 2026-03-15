# handlers/agent.py — Agent Panel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import BC_TYPE, BC_MSG, UR_RATE, SUPER_ADMIN_ID, AGENT_PAY_AMOUNT
from keyboards import kb_agent, REMOVE
from db import (agent_by_tid, all_clients, all_apps, all_payments, all_agent_payments,
                client_by_code, set_agent_field, put_setting, get_setting,
                agent_status, agent_log, get_agent_balance, add_agent_payment,
                queue_pending, queue_all, queue_today_count)
from utils import user_data, now_ist, today_ist, safe_float, safe_int, gen_pay_id, divider


# ── My Queue ─────────────────────────────────────────────────
async def my_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return
    all_q   = queue_all()
    my_pend = [r for r in all_q
               if r.get("agent_id") == agent["agent_id"]
               and r.get("status","").upper() == "PENDING"]
    if not my_pend:
        await update.message.reply_text("✅ Koi pending application nahi!", reply_markup=kb_agent())
        return
    await update.message.reply_text(f"📥 *My Pending: {len(my_pend)}*", parse_mode=ParseMode.MARKDOWN)
    for ap in my_pend[:15]:
        await update.message.reply_text(
            f"⏳ `{ap.get('queue_id')}`\n"
            f"📄 {ap.get('app_no')} | 📅 {ap.get('dob')}\n"
            f"👤 {ap.get('client_name')}\n"
            f"🕐 {ap.get('submitted_at','')[:16]}",
            parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text(divider(), reply_markup=kb_agent())


# ── Today Summary ─────────────────────────────────────────────
async def today_summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return
    today = today_ist()
    all_q = queue_all()
    my_q  = [r for r in all_q
             if r.get("agent_id") == agent["agent_id"]
             and r.get("submitted_at","").startswith(today)]
    done    = sum(1 for r in my_q if r.get("status") == "DONE")
    pending = sum(1 for r in my_q if r.get("status") == "PENDING")
    bal     = get_agent_balance(agent["agent_id"])
    earnings = done * safe_float(agent.get("rate_per_app",0))
    await update.message.reply_text(
        f"📊 *Today — {today}*\n{divider()}\n"
        f"📋 Total: {len(my_q)}\n"
        f"✅ Done: {done}\n"
        f"⏳ Pending: {pending}\n"
        f"💰 Today Earnings: Rs{earnings}\n"
        f"🏦 My Balance: Rs{bal}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_agent())


# ── My Clients ────────────────────────────────────────────────
async def my_clients(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid     = update.effective_user.id
    agent   = agent_by_tid(tid)
    clients = all_clients(agent)
    if not clients:
        await update.message.reply_text("❌ Koi client nahi.", reply_markup=kb_agent())
        return
    await update.message.reply_text(f"👥 *My Clients ({len(clients)})*", parse_mode=ParseMode.MARKDOWN)
    for c in clients:
        icon = "✅" if c.get("status") == "active" else "🚫"
        kb   = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚫 Block",   callback_data=f"C_BLOCK|{c['client_code']}|{agent['agent_id']}"),
            InlineKeyboardButton("✅ Unblock", callback_data=f"C_UNBLK|{c['client_code']}|{agent['agent_id']}"),
        ]])
        try:
            await update.message.reply_text(
                f"{icon} *{c.get('full_name')}*\n"
                f"🆔 `{c.get('client_code')}`\n"
                f"📱 {c.get('phone')} | 💰 Rs{safe_float(c.get('balance',0))}\n"
                f"📋 Apps: {c.get('total_apps',0)}",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            pass
    try:
        bot_me   = await ctx.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=register_{agent['agent_id']}"
        await update.message.reply_text(f"🔗 Referral:\n`{ref_link}`", parse_mode=ParseMode.MARKDOWN, reply_markup=kb_agent())
    except Exception:
        await update.message.reply_text(divider(), reply_markup=kb_agent())


# ── My Stats ─────────────────────────────────────────────────
async def my_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid    = update.effective_user.id
    agent  = agent_by_tid(tid)
    if not agent: return
    all_q  = queue_all()
    my_q   = [r for r in all_q if r.get("agent_id") == agent["agent_id"]]
    done   = sum(1 for r in my_q if r.get("status") == "DONE")
    total_earn = done * safe_float(agent.get("rate_per_app",0))
    bal    = get_agent_balance(agent["agent_id"])
    await update.message.reply_text(
        f"📈 *My Stats*\n{divider()}\n"
        f"👤 Clients: {agent.get('total_clients',0)}\n"
        f"📋 Total Apps: {len(my_q)}\n"
        f"✅ Done: {done}\n"
        f"💰 Total Earnings: Rs{total_earn}\n"
        f"🏦 Balance: Rs{bal}\n"
        f"💳 Rate: Rs{agent.get('rate_per_app',0)}/app",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_agent())


# ── My Balance ────────────────────────────────────────────────
async def my_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return
    bal   = get_agent_balance(agent["agent_id"])
    await update.message.reply_text(
        f"💳 *My Balance*\n{divider()}\n🏦 Rs{bal}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_agent())


# ── Pay Admin ─────────────────────────────────────────────────
async def pay_admin_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return ConversationHandler.END
    # Get admin QR from settings (agent's sheet mein admin_qr_file_id)
    qr = get_setting(agent, "admin_qr_file_id")
    if qr:
        try:
            await ctx.bot.send_photo(tid, qr, caption="💳 Admin ko payment karo\nPhir amount type karo:")
        except Exception:
            await update.message.reply_text("💰 Admin ko payment karo.\nAmount type karo:", reply_markup=REMOVE)
    else:
        await update.message.reply_text("💰 Admin ko payment karo.\nAmount type karo (Rs mein):", reply_markup=REMOVE)
    user_data(tid)["agent_paying_admin"] = True
    user_data(tid)["pay_agent_obj"] = agent
    return AGENT_PAY_AMOUNT

async def pay_admin_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    d   = user_data(tid)
    try:
        amount = safe_float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valid amount daalo:")
        return AGENT_PAY_AMOUNT
    agent  = d.get("pay_agent_obj")
    pay_id = gen_pay_id()
    add_agent_payment(agent, {"pay_id":pay_id,"amount":amount})
    d.pop("agent_paying_admin", None)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"AGPAY_APP|{pay_id}|{agent['agent_id']}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"AGPAY_REJ|{pay_id}|{agent['agent_id']}"),
    ]])
    await update.message.reply_text(
        f"✅ Payment request bheja!\n💵 Rs{amount}\n⏳ Admin approve karega.",
        reply_markup=kb_agent())
    try:
        await ctx.bot.send_message(SUPER_ADMIN_ID,
            f"💰 *Agent Payment Request*\n\n"
            f"🧑‍💼 {agent.get('agent_name')} (`{agent.get('agent_id')}`)\n"
            f"💵 Rs{amount}\n🆔 `{pay_id}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass
    return ConversationHandler.END


# ── Settings ──────────────────────────────────────────────────
async def settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return
    rate = get_setting(agent, "rate_per_app") or agent.get("rate_per_app","N/A")
    qr   = get_setting(agent, "qr_file_id")
    kb   = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Update Rate", callback_data=f"SET_RATE|{agent['agent_id']}")],
        [InlineKeyboardButton("📷 Upload QR",   callback_data=f"SET_QR|{agent['agent_id']}")],
    ])
    await update.message.reply_text(
        f"⚙️ *Settings*\n{divider()}\n"
        f"💰 Rate: Rs{rate}/app\n"
        f"📷 QR: {'✅ Set' if qr else '❌ Not set'}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ── Broadcast ────────────────────────────────────────────────
async def broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📝 Text",  callback_data="BC_TEXT"),
        InlineKeyboardButton("🖼 Image", callback_data="BC_IMAGE"),
    ]])
    await update.message.reply_text("📢 Type chuniye:", reply_markup=kb)
    return BC_TYPE

async def bc_type_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    t = q.data.replace("BC_","").lower()
    user_data(q.from_user.id)["bc_type"] = t
    await q.edit_message_text(f"Type: {t}\n\nMessage bhejiye:")
    return BC_MSG

async def bc_content(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid     = update.effective_user.id
    agent   = agent_by_tid(tid)
    bc_type = user_data(tid).get("bc_type","text")
    clients = all_clients(agent)
    sent = failed = 0
    for c in clients:
        try:
            c_tid = int(c.get("telegram_id",0))
            if not c_tid: continue
            if bc_type == "text":
                await ctx.bot.send_message(c_tid, update.message.text)
            elif bc_type == "image" and update.message.photo:
                await ctx.bot.send_photo(c_tid, update.message.photo[-1].file_id, caption=update.message.caption or "")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent} | ❌ Failed: {failed}", reply_markup=kb_agent())
    return ConversationHandler.END


# ── QR Upload ─────────────────────────────────────────────────
async def qr_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return False
    d = user_data(tid)
    if d.get("awaiting_qr"):
        file_id = update.message.photo[-1].file_id
        put_setting(agent, "qr_file_id", file_id)
        set_agent_field(agent["agent_id"], "qr_file_id", file_id)
        d.pop("awaiting_qr", None)
        await update.message.reply_text("✅ QR save ho gaya!", reply_markup=kb_agent())
        return True
    return False

async def rate_start(update, ctx):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return ConversationHandler.END
    user_data(tid)["rate_agent"] = agent
    await update.message.reply_text("💰 Naya rate daalo (Rs mein):", reply_markup=REMOVE)
    return UR_RATE

async def rate_save(update, ctx):
    tid = update.effective_user.id
    try:
        rate = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Number daalo:")
        return UR_RATE
    agent = user_data(tid).get("rate_agent") or agent_by_tid(tid)
    set_agent_field(agent["agent_id"], "rate_per_app", rate)
    put_setting(agent, "rate_per_app", str(rate))
    await update.message.reply_text(f"✅ Rate updated: Rs{rate}/app", reply_markup=kb_agent())
    return ConversationHandler.END

async def work_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    agent = agent_by_tid(tid)
    if not agent: return
    all_q = queue_all()
    my_q  = [r for r in all_q if r.get("agent_id") == agent["agent_id"]]
    done_list = [r for r in my_q if r.get("status") == "DONE"][-10:]
    if not done_list:
        await update.message.reply_text("📜 Koi done app nahi.", reply_markup=kb_agent())
        return
    await update.message.reply_text(f"📜 *Work History (last {len(done_list)})*", parse_mode=ParseMode.MARKDOWN)
    for ap in reversed(done_list):
        await update.message.reply_text(
            f"✅ `{ap.get('queue_id')}` | {ap.get('app_no')}\n"
            f"👤 {ap.get('client_name')} | ✔️ {ap.get('done_at','')[:16]}",
            parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text(divider(), reply_markup=kb_agent())
