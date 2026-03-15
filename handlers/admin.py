# handlers/admin.py — Admin Panel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import SUPER_ADMIN_ID, AA_NAME, AA_PHONE, AA_TID, AA_RATE, AA_SHEET, ABC_TYPE, ABC_MSG
from keyboards import kb_admin, REMOVE
from db import (all_agents, agent_by_id, add_agent, set_agent_field, remove_agent,
                master_log, all_clients, all_apps, all_payments, all_agent_payments,
                setup_manual_sheet, agent_by_tid, agent_status, trial_end_date,
                queue_pending, queue_all, queue_today_count, queue_mark_done, queue_get,
                add_agent_balance, approve_agent_payment, reject_agent_payment,
                get_agent_balance, db, MASTER_SHEET)
from utils import (user_data, now_ist, today_ist, month_ist, safe_float,
                   safe_int, gen_agent_id, valid_phone, divider)

def is_admin(tid): return tid == SUPER_ADMIN_ID


# ── Dashboard ─────────────────────────────────────────────────
async def dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    agents  = all_agents()
    active  = sum(1 for a in agents if agent_status(a) in ("active","trial"))
    q       = queue_today_count()
    t_clts  = sum(safe_int(a.get("total_clients",0)) for a in agents)
    await update.message.reply_text(
        f"📊 *Dashboard — {today_ist()}*\n{divider()}\n"
        f"👥 Agents: {len(agents)} ({active} active)\n"
        f"👤 Total Clients: {t_clts}\n\n"
        f"📋 *Today Queue*\n"
        f"  Total: {q['total']} | ✅ Done: {q['done']} | ⏳ Pending: {q['pending']}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())


# ── Queue ─────────────────────────────────────────────────────
async def show_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    pending = queue_pending()
    if not pending:
        await update.message.reply_text("✅ Queue khali hai! Koi pending application nahi.", reply_markup=kb_admin())
        return
    await update.message.reply_text(
        f"📋 *Pending Queue: {len(pending)}*", parse_mode=ParseMode.MARKDOWN)
    for ap in pending[:20]:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ DONE",
                callback_data=f"QDONE|{ap['queue_id']}|{ap['client_code']}|{ap['agent_id']}|0|0")
        ]])
        pri  = "🔴 HIGH" if ap.get("priority") == "high" else "🟡 Normal"
        await update.message.reply_text(
            f"{pri}\n"
            f"🆔 `{ap.get('queue_id')}`\n"
            f"📄 App No: `{ap.get('app_no')}`\n"
            f"📅 DOB: `{ap.get('dob')}`\n"
            f"🔒 Password: `{ap.get('password')}`\n"
            f"👤 {ap.get('client_name')} | `{ap.get('client_code')}`\n"
            f"🧑‍💼 {ap.get('agent_name')}\n"
            f"🕐 {ap.get('submitted_at','')[:16]}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    if len(pending) > 20:
        await update.message.reply_text(f"... aur {len(pending)-20} pending hain", reply_markup=kb_admin())
    else:
        await update.message.reply_text(divider(), reply_markup=kb_admin())


async def show_done_apps(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    all_q = queue_all()
    done  = [r for r in all_q if r.get("status","").upper() == "DONE"]
    today = today_ist()
    today_done = [r for r in done if r.get("done_at","").startswith(today)]
    await update.message.reply_text(
        f"✅ *Done Apps*\n{divider()}\n"
        f"Today: {len(today_done)}\nTotal: {len(done)}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())


# ── All Agents ────────────────────────────────────────────────
async def all_agents_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    agents = all_agents()
    if not agents:
        await update.message.reply_text("❌ Koi agent nahi.", reply_markup=kb_admin())
        return
    await update.message.reply_text(f"👥 *All Agents ({len(agents)})*", parse_mode=ParseMode.MARKDOWN)
    for a in agents:
        st   = agent_status(a)
        icon = "✅" if st in ("active","trial") else "🚫"
        bal  = safe_float(a.get("balance",0))
        kb   = InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑 Remove", callback_data=f"REMOVE_AGENT|{a['agent_id']}"),
            InlineKeyboardButton("💰 Add Bal", callback_data=f"AGENT_BAL|{a['agent_id']}"),
        ]])
        try:
            await update.message.reply_text(
                f"{icon} *{a.get('agent_name')}*\n"
                f"🆔 `{a.get('agent_id')}`\n"
                f"📱 {a.get('phone')} | TID: `{a.get('telegram_id')}`\n"
                f"💰 Rate: Rs{a.get('rate_per_app')}/app | Balance: Rs{bal}\n"
                f"📊 Apps: {a.get('total_apps',0)} | Clients: {a.get('total_clients',0)}\n"
                f"⏳ {st} | Trial: {a.get('trial_end','')}",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            pass
    await update.message.reply_text(divider(), reply_markup=kb_admin())


# ── Agent Payments (Agent → Admin) ────────────────────────────
async def agent_payments_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    agents  = all_agents()
    pending = []
    for ag in agents:
        for p in all_agent_payments(ag):
            if p.get("status","").upper() == "PENDING":
                p["_agent"]      = ag
                p["_agent_name"] = ag.get("agent_name","")
                pending.append(p)
    if not pending:
        await update.message.reply_text("✅ Koi pending agent payment nahi.", reply_markup=kb_admin())
        return
    await update.message.reply_text(f"💰 *Agent Payments ({len(pending)} pending)*", parse_mode=ParseMode.MARKDOWN)
    for p in pending:
        ag  = p["_agent"]
        kb  = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"AGPAY_APP|{p['payment_id']}|{ag['agent_id']}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"AGPAY_REJ|{p['payment_id']}|{ag['agent_id']}"),
        ]])
        await update.message.reply_text(
            f"💰 *{p['_agent_name']}*\n"
            f"💵 Rs{p.get('amount_paid')}\n"
            f"📅 {p.get('payment_date')} {p.get('payment_time')}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    await update.message.reply_text(divider(), reply_markup=kb_admin())


# ── Add Agent (5 steps) ───────────────────────────────────────
async def add_agent_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    await update.message.reply_text("➕ *New Agent*\n\nStep 1/5 — Agent ka Naam:", parse_mode=ParseMode.MARKDOWN, reply_markup=REMOVE)
    return AA_NAME

async def aa_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    user_data(tid)["aa_name"] = update.message.text.strip()
    await update.message.reply_text(f"Naam: {user_data(tid)['aa_name']}\n\nStep 2/5 — Phone (10 digit):")
    return AA_PHONE

async def aa_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid   = update.effective_user.id
    phone = update.message.text.strip()
    if not valid_phone(phone):
        await update.message.reply_text("❌ 10 digit phone daalo:")
        return AA_PHONE
    user_data(tid)["aa_phone"] = phone
    await update.message.reply_text(f"Phone: {phone}\n\nStep 3/5 — Telegram ID:")
    return AA_TID

async def aa_tid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    raw = update.message.text.strip()
    if not raw.lstrip("-").isdigit():
        await update.message.reply_text("❌ Sirf number daalo:")
        return AA_TID
    user_data(tid)["aa_tid"] = raw
    await update.message.reply_text(f"TID: {raw}\n\nStep 4/5 — Rate per App (Rs):")
    return AA_RATE

async def aa_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    try:
        rate = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Number daalo:")
        return AA_RATE
    user_data(tid)["aa_rate"] = rate
    await update.message.reply_text(
        f"Rate: Rs{rate}/app\n\nStep 5/5 — Google Sheet ka naam daalo:\n*(Manually banai sheet ka exact naam)*",
        parse_mode=ParseMode.MARKDOWN)
    return AA_SHEET

async def aa_sheet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid        = update.effective_user.id
    sheet_name = update.message.text.strip()
    d          = user_data(tid)
    rate       = d["aa_rate"]
    agent_name = d["aa_name"]
    agent_id   = gen_agent_id()
    await update.message.reply_text("⏳ Setting up...")
    ok_sheet = setup_manual_sheet(sheet_name, agent_id, agent_name, rate)
    if not ok_sheet:
        await update.message.reply_text(
            f"❌ Sheet *'{sheet_name}'* nahi mili!\n\n"
            f"1. Sheet ka naam exactly same ho\n"
            f"2. Service account ko Editor access ho\n\nDobara naam daalo:",
            parse_mode=ParseMode.MARKDOWN)
        return AA_SHEET
    ok = add_agent({"agent_id":agent_id,"agent_name":agent_name,
                    "phone":d["aa_phone"],"telegram_id":int(d["aa_tid"]),
                    "sheet_name":sheet_name,"rate":rate})
    if not ok:
        await update.message.reply_text("❌ Agent save nahi hua.", reply_markup=kb_admin())
        return ConversationHandler.END
    te = trial_end_date()
    try:
        bot_me   = await ctx.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=register_{agent_id}"
    except Exception:
        ref_link = "N/A"
    await update.message.reply_text(
        f"✅ *Agent Added!*\n\n🆔 `{agent_id}`\n👤 {agent_name}\n"
        f"📋 Sheet: `{sheet_name}`\n💰 Rate: Rs{rate}/app\n⏳ Trial: {te} tak\n\n🔗 {ref_link}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())
    try:
        await ctx.bot.send_message(int(d["aa_tid"]),
            f"🎉 *Agent bana diya!*\n🆔 `{agent_id}`\n💰 Rs{rate}/app\n\n/start bhejo",
            parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass
    return ConversationHandler.END


# ── Find Agent ────────────────────────────────────────────────
async def find_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /find_agent <naam ya ID>", reply_markup=kb_admin())
        return
    q = " ".join(args).lower()
    results = [a for a in all_agents() if q in a.get("agent_name","").lower() or q in a.get("agent_id","").lower()]
    if not results:
        await update.message.reply_text("❌ Nahi mila.", reply_markup=kb_admin())
        return
    for a in results:
        await update.message.reply_text(
            f"✅ *{a['agent_name']}*\n🆔 {a['agent_id']}\n📋 {a['sheet_name']}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())


# ── Stats / Reports ───────────────────────────────────────────
async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await dashboard(update, ctx)

async def all_apps_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    q = queue_today_count()
    all_q = queue_all()
    await update.message.reply_text(
        f"📋 *All Applications*\n{divider()}\n"
        f"Total: {len(all_q)}\nToday: {q['total']}\n✅ Done: {q['done']}\n⏳ Pending: {q['pending']}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())

async def all_payments_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    agents = all_agents()
    total  = pending = paid = 0
    for ag in agents:
        for p in all_payments(ag):
            total += 1
            st = p.get("status","").upper()
            if st == "PENDING": pending += 1
            elif st == "PAID":  paid    += 1
    await update.message.reply_text(
        f"💰 *Client Payments*\n{divider()}\nTotal: {total}\n⏳ Pending: {pending}\n✅ Paid: {paid}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())

async def logs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("📜 Logs FOS_Master sheet ke 'logs' tab mein hain.", reply_markup=kb_admin())

async def monthly_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    agents = all_agents()
    mon    = month_ist()
    all_q  = queue_all()
    mon_q  = [r for r in all_q if r.get("submitted_at","").startswith(mon)]
    done   = sum(1 for r in mon_q if r.get("status") == "DONE")
    await update.message.reply_text(
        f"📈 *Monthly Report — {mon}*\n{divider()}\n"
        f"👥 Agents: {len(agents)}\n"
        f"📋 Apps this month: {len(mon_q)}\n"
        f"✅ Done: {done}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin())


# ── Admin Broadcast ───────────────────────────────────────────
async def admin_bc_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📝 Text",  callback_data="ABC_TEXT"),
        InlineKeyboardButton("🖼 Image", callback_data="ABC_IMAGE"),
        InlineKeyboardButton("🎤 Voice", callback_data="ABC_VOICE"),
    ]])
    await update.message.reply_text("📢 Broadcast type:", reply_markup=kb)
    return ABC_TYPE

async def admin_bc_type_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    t = q.data.replace("ABC_","").lower()
    user_data(q.from_user.id)["abc_type"] = t
    await q.edit_message_text(f"Type: {t}\n\nMessage bhejiye:")
    return ABC_MSG

async def admin_bc_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tid     = update.effective_user.id
    bc_type = user_data(tid).get("abc_type","text")
    agents  = [a for a in all_agents() if agent_status(a) in ("active","trial")]
    sent = failed = 0
    for ag in agents:
        try:
            ag_tid = int(ag.get("telegram_id",0))
            if not ag_tid: continue
            if bc_type == "text":
                await ctx.bot.send_message(ag_tid, update.message.text)
            elif bc_type == "image" and update.message.photo:
                await ctx.bot.send_photo(ag_tid, update.message.photo[-1].file_id, caption=update.message.caption or "")
            elif bc_type == "voice" and update.message.voice:
                await ctx.bot.send_voice(ag_tid, update.message.voice.file_id)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"📢 Done!\n✅ {sent} | ❌ {failed}", reply_markup=kb_admin())
    return ConversationHandler.END
