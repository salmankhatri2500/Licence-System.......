# handlers/message_router.py
from telegram import Update
from telegram.ext import ContextTypes
from db import detect_role, agent_by_tid, find_client, agent_status
from keyboards import kb_admin, kb_agent, kb_client
from utils import user_data, safe_float

from handlers.admin import (dashboard, all_agents_cmd, all_apps_cmd,
                             all_payments_cmd, logs_cmd, monthly_report,
                             show_queue, show_done_apps, agent_payments_cmd)
from handlers.agent import (my_queue, today_summary as agent_today, work_history,
                             my_clients, my_stats, my_balance, pay_admin_start, settings)
from handlers.client import (today_summary as client_today, my_history, my_apps,
                              my_balance as client_balance, my_profile,
                              contact_agent, handle_pay_amount_input)


async def photo_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.agent import qr_receive
    await qr_receive(update, ctx)


async def message_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    tid  = update.effective_user.id
    text = update.message.text.strip()
    d    = user_data(tid)

    # ── Awaiting payment amount (client) ──────────────────────
    if d.get("awaiting_pay_amount"):
        await handle_pay_amount_input(update, ctx)
        return

    # ── Awaiting agent balance add (admin) ────────────────────
    if d.get("awaiting_agent_bal"):
        try:
            amount   = safe_float(text)
            agent_id = d.get("adding_agent_bal_id","")
            if amount > 0 and agent_id:
                from db import add_agent_balance, agent_by_id
                add_agent_balance(agent_id, amount)
                ag = agent_by_id(agent_id)
                await update.message.reply_text(
                    f"✅ Rs{amount} added to {ag.get('agent_name') if ag else agent_id}",
                    reply_markup=kb_admin())
                # Notify agent
                if ag:
                    try:
                        await ctx.bot.send_message(int(ag["telegram_id"]),
                            f"✅ Admin ne Rs{amount} balance add kiya!", )
                    except Exception:
                        pass
            else:
                await update.message.reply_text("❌ Valid amount daalo:", reply_markup=kb_admin())
        except Exception:
            await update.message.reply_text("❌ Valid amount daalo:", reply_markup=kb_admin())
        d.pop("awaiting_agent_bal", None)
        d.pop("adding_agent_bal_id", None)
        return

    # ── Awaiting rate update ───────────────────────────────────
    if d.get("awaiting_rate"):
        try:
            rate     = float(text)
            agent_id = d.get("rate_agent_id","")
            if rate > 0 and agent_id:
                from db import set_agent_field, put_setting, agent_by_id
                ag = agent_by_id(agent_id) or agent_by_tid(tid)
                if ag:
                    set_agent_field(ag["agent_id"], "rate_per_app", rate)
                    put_setting(ag, "rate_per_app", str(rate))
                await update.message.reply_text(f"✅ Rate: Rs{rate}/app", reply_markup=kb_agent())
            else:
                await update.message.reply_text("❌ Valid number daalo:")
        except ValueError:
            await update.message.reply_text("❌ Valid number daalo:")
        d.pop("awaiting_rate", None)
        d.pop("rate_agent_id", None)
        return

    role = detect_role(tid)

    # ── ADMIN ─────────────────────────────────────────────────
    if role == "admin":
        routes = {
            "📊 Dashboard":       dashboard,
            "👥 All Agents":      all_agents_cmd,
            "📋 Queue":           show_queue,
            "✅ Done Apps":       show_done_apps,
            "💰 Agent Payments":  agent_payments_cmd,
            "📋 All Apps":        all_apps_cmd,
            "💰 All Payments":    all_payments_cmd,
            "🗂️ Logs":           logs_cmd,
            "📈 Monthly Report":  monthly_report,
        }
        fn = routes.get(text)
        if fn:
            await fn(update, ctx)
        else:
            await update.message.reply_text("Button use karein:", reply_markup=kb_admin())

    # ── AGENT ─────────────────────────────────────────────────
    elif role == "agent":
        agent = agent_by_tid(tid)
        st    = agent_status(agent)
        if st in ("blocked","deleted"):
            await update.message.reply_text("🚫 Account block. Admin se contact karo.")
            return
        if st == "expired":
            await update.message.reply_text("⏳ Trial khatam. Admin se contact karo.")
            return
        if text == "🔄 Refresh":
            from handlers.registration import cmd_start
            await cmd_start(update, ctx)
            return
        routes = {
            "📥 My Queue":       my_queue,
            "📊 Today Summary":  agent_today,
            "📜 Work History":   work_history,
            "👥 My Clients":     my_clients,
            "📈 My Stats":       my_stats,
            "💳 My Balance":     my_balance,
            "💰 Pay Admin":      pay_admin_start,
            "⚙️ Settings":      settings,
        }
        fn = routes.get(text)
        if fn:
            await fn(update, ctx)
        else:
            await update.message.reply_text("Button use karein:", reply_markup=kb_agent())

    # ── CLIENT ────────────────────────────────────────────────
    elif role == "client":
        c, ag = find_client(tid)
        if c and c.get("status") == "blocked":
            await update.message.reply_text("🚫 Account block. Agent se contact karo.")
            return
        routes = {
            "📊 My Apps":       my_apps,
            "📊 Today Summary": client_today,
            "📜 My History":    my_history,
            "💰 My Balance":    client_balance,
            "ℹ️ My Profile":   my_profile,
            "📞 Contact Agent": contact_agent,
        }
        fn = routes.get(text)
        if fn:
            await fn(update, ctx)
        else:
            await update.message.reply_text("Apna panel:", reply_markup=kb_client())

    else:
        await update.message.reply_text("Registered nahi hain.\nAgent se referral link maango.")
