# handlers/callbacks.py — All Inline Button Callbacks
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import SUPER_ADMIN_ID
from keyboards import kb_admin, kb_agent, kb_client
from db import (agent_by_id, agent_by_tid, find_client, client_by_code,
                set_client_field, set_agent_field, remove_agent, master_log,
                get_setting, put_setting, agent_status,
                approve_payment, reject_payment, add_balance,
                approve_agent_payment, reject_agent_payment, add_agent_balance,
                queue_mark_done, queue_get, mark_app_done)
from utils import user_data, safe_float, divider


async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    tid  = q.from_user.id

    # ── Queue DONE (Admin marks done) ────────────────────────
    if data.startswith("QDONE|"):
        parts      = data.split("|")
        queue_id   = parts[1]
        client_code= parts[2]
        agent_id   = parts[3]
        agent_tid  = int(parts[4]) if parts[4] != "0" else 0
        client_tid = int(parts[5]) if parts[5] != "0" else 0

        if tid != SUPER_ADMIN_ID:
            await q.answer("Only admin!", show_alert=True)
            return

        queue_mark_done(queue_id)

        # Mark in agent's applications sheet too
        agent = agent_by_id(agent_id)
        if agent:
            mark_app_done(agent, queue_id)

        await q.edit_message_text(
            q.message.text + f"\n\n✅ *DONE* by Admin",
            parse_mode=ParseMode.MARKDOWN)

        # Notify Agent
        if agent_tid:
            try:
                await ctx.bot.send_message(agent_tid,
                    f"✅ *Application Done!*\n🆔 `{queue_id}`\n📄 {queue_get(queue_id).get('app_no','')}",
                    parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

        # Notify Client
        if client_tid:
            try:
                qitem = queue_get(queue_id)
                await ctx.bot.send_message(client_tid,
                    f"🎉 *Application Successful!*\n\n"
                    f"🆔 `{queue_id}`\n"
                    f"📄 App No: {qitem.get('app_no','')}\n"
                    f"✅ Aapki application process ho gayi!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=kb_client())
            except Exception:
                pass

    # ── Client Payment Approve ────────────────────────────────
    elif data.startswith("PAY_APP|"):
        _, pay_id, client_code, agent_id, client_tid = data.split("|")
        agent = agent_by_id(agent_id)
        if not agent:
            await q.edit_message_text("Agent nahi mila.")
            return
        # Get amount from payment record
        from db import all_payments
        amount = 0.0
        for p in all_payments(agent):
            if p.get("payment_id") == pay_id:
                amount = safe_float(p.get("amount_paid", 0))
                break
        approve_payment(agent, pay_id, q.from_user.first_name)
        add_balance(agent, client_code, amount)
        await q.edit_message_text(f"✅ Payment approved! Rs{amount} added to {client_code}")
        try:
            await ctx.bot.send_message(int(client_tid),
                f"✅ *Payment Approved!*\nRs{amount} balance add ho gaya!",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())
        except Exception:
            pass

    elif data.startswith("PAY_REJ|"):
        _, pay_id, client_code, agent_id, client_tid = data.split("|")
        agent = agent_by_id(agent_id)
        if agent:
            reject_payment(agent, pay_id)
        await q.edit_message_text(f"❌ Payment rejected: {pay_id}")
        try:
            await ctx.bot.send_message(int(client_tid),
                "❌ *Payment Rejected.*\nAgent se contact karo.",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb_client())
        except Exception:
            pass

    # ── Agent Payment Approve (Admin approves agent payment) ──
    elif data.startswith("AGPAY_APP|"):
        _, pay_id, agent_id = data.split("|")
        if tid != SUPER_ADMIN_ID:
            await q.answer("Only admin!", show_alert=True)
            return
        agent = agent_by_id(agent_id)
        if not agent:
            await q.edit_message_text("Agent nahi mila.")
            return
        from db import all_agent_payments
        amount = 0.0
        for p in all_agent_payments(agent):
            if p.get("payment_id") == pay_id:
                amount = safe_float(p.get("amount_paid", 0))
                break
        approve_agent_payment(agent, pay_id)
        add_agent_balance(agent_id, amount)
        await q.edit_message_text(f"✅ Agent payment approved! Rs{amount} added to {agent.get('agent_name')}")
        try:
            await ctx.bot.send_message(int(agent["telegram_id"]),
                f"✅ *Payment Approved!*\nRs{amount} balance add ho gaya!",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb_agent())
        except Exception:
            pass

    elif data.startswith("AGPAY_REJ|"):
        _, pay_id, agent_id = data.split("|")
        if tid != SUPER_ADMIN_ID:
            await q.answer("Only admin!", show_alert=True)
            return
        agent = agent_by_id(agent_id)
        if agent:
            reject_agent_payment(agent, pay_id)
        await q.edit_message_text(f"❌ Agent payment rejected.")
        try:
            await ctx.bot.send_message(int(agent["telegram_id"]),
                "❌ *Payment Rejected.*\nAdmin se contact karo.",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb_agent())
        except Exception:
            pass

    # ── Remove Agent ──────────────────────────────────────────
    elif data.startswith("REMOVE_AGENT|"):
        if tid != SUPER_ADMIN_ID:
            await q.answer("Only admin!", show_alert=True)
            return
        agent_id = data.split("|")[1]
        remove_agent(agent_id)
        await q.edit_message_text(f"🗑 Agent {agent_id} removed.")

    # ── Add Agent Balance (Admin) ──────────────────────────────
    elif data.startswith("AGENT_BAL|"):
        if tid != SUPER_ADMIN_ID:
            await q.answer("Only admin!", show_alert=True)
            return
        agent_id = data.split("|")[1]
        user_data(tid)["adding_agent_bal_id"] = agent_id
        user_data(tid)["awaiting_agent_bal"]  = True
        await q.edit_message_text(f"💰 Agent {agent_id} ko kitna balance add karna hai? (Amount type karo in bot)")

    # ── Block/Unblock Client ──────────────────────────────────
    elif data.startswith("C_BLOCK|"):
        _, client_code, agent_id = data.split("|")
        agent = agent_by_id(agent_id)
        if agent:
            set_client_field(agent, client_code, "status", "blocked")
        await q.edit_message_text(f"🚫 Client {client_code} blocked.")

    elif data.startswith("C_UNBLK|"):
        _, client_code, agent_id = data.split("|")
        agent = agent_by_id(agent_id)
        if agent:
            set_client_field(agent, client_code, "status", "active")
        await q.edit_message_text(f"✅ Client {client_code} unblocked.")

    # ── Set Rate ──────────────────────────────────────────────
    elif data.startswith("SET_RATE|"):
        agent_id = data.split("|")[1]
        user_data(tid)["awaiting_rate"]    = True
        user_data(tid)["rate_agent_id"]    = agent_id
        await q.edit_message_text("💰 Naya rate type karo (Rs mein):")

    # ── Set QR ────────────────────────────────────────────────
    elif data.startswith("SET_QR|"):
        user_data(tid)["awaiting_qr"] = True
        await q.edit_message_text("📷 QR photo bhejiye:")
