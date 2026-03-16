from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import ContextTypes

from config import SUPER_ADMIN_ID

from keyboards import kb_admin, kb_agent, kb_client

from db import (agent_by_id, set_client_field, remove_agent,

                get_setting, put_setting,

                approve_payment, reject_payment, add_balance, get_payment_amount,

                approve_agent_payment, reject_agent_payment,

                add_agent_balance, get_agent_payment_amount,

                queue_mark_done, queue_get, mark_app_done,

                queue_release_held, get_admin_rate, deduct_agent_balance,

                set_admin_setting)

from utils import user_data, safe_float, div





async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    q    = update.callback_query

    await q.answer()

    data = q.data

    tid  = q.from_user.id



    # ── QDONE ─────────────────────────────────────────────────

    if data.startswith("QDONE|"):

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        parts       = data.split("|")

        queue_id    = parts[1]

        client_code = parts[2]

        agent_id    = parts[3]

        agent_tid   = int(parts[4]) if parts[4] not in ("0","") else 0

        client_tid  = int(parts[5]) if parts[5] not in ("0","") else 0



        queue_mark_done(queue_id)



        admin_rate = get_admin_rate()

        if admin_rate > 0:

            deduct_agent_balance(agent_id, admin_rate)



        agent = agent_by_id(agent_id)

        if agent:

            mark_app_done(agent, queue_id)



        qitem = queue_get(queue_id)



        try:

            await q.edit_message_text(

                q.message.text + "\n\n--- DONE by Admin ---")

        except: pass



        # Notify agent

        if agent_tid:

            try:

                await ctx.bot.send_message(

                    agent_tid,

                    f"Application Done!\n\n"

                    f"ID: {queue_id}\n"

                    f"App No: {qitem.get('app_no','')}\n"

                    f"Client: {qitem.get('client_name','')}\n\n"

                    f"Rs{admin_rate} deducted from your balance.",

                    reply_markup=kb_agent())

            except: pass



        # Notify client

        if client_tid:

            try:

                await ctx.bot.send_message(

                    client_tid,

                    f"Application Successful!\n\n"

                    f"ID: {queue_id}\n"

                    f"App No: {qitem.get('app_no','')}\n\n"

                    f"Aapki application process ho gayi!",

                    reply_markup=kb_client())

            except: pass

        elif client_code and agent:

            try:

                from db import client_by_code

                c = client_by_code(agent, client_code)

                if c and c.get("telegram_id"):

                    await ctx.bot.send_message(

                        int(c["telegram_id"]),

                        f"Application Successful!\n\n"

                        f"ID: {queue_id}\n"

                        f"App No: {qitem.get('app_no','')}\n\n"

                        f"Aapki application process ho gayi!",

                        reply_markup=kb_client())

            except: pass



    # ── Client Payment ─────────────────────────────────────────

    elif data.startswith("PAY_APP|"):

        _, pay_id, client_code, agent_id, client_tid = data.split("|")

        agent  = agent_by_id(agent_id)

        if not agent:

            await q.edit_message_text("Agent nahi mila.")

            return

        amount = get_payment_amount(agent, pay_id)

        approve_payment(agent, pay_id, q.from_user.first_name)

        add_balance(agent, client_code, amount)

        try:

            await q.edit_message_text(f"Payment approved! Rs{amount} added to {client_code}")

        except: pass

        try:

            await ctx.bot.send_message(

                int(client_tid),

                f"Payment Approved!\nRs{amount} balance add ho gaya!",

                reply_markup=kb_client())

        except: pass



    elif data.startswith("PAY_REJ|"):

        _, pay_id, client_code, agent_id, client_tid = data.split("|")

        agent = agent_by_id(agent_id)

        if agent: reject_payment(agent, pay_id)

        try:

            await q.edit_message_text(f"Payment rejected: {pay_id}")

        except: pass

        try:

            await ctx.bot.send_message(

                int(client_tid),

                "Payment Rejected. Agent se contact karo.",

                reply_markup=kb_client())

        except: pass



    # ── Agent Payment ──────────────────────────────────────────

    elif data.startswith("AGPAY_APP|"):

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        _, pay_id, agent_id = data.split("|")

        agent  = agent_by_id(agent_id)

        if not agent:

            await q.edit_message_text("Agent nahi mila.")

            return

        amount = get_agent_payment_amount(agent, pay_id)

        approve_agent_payment(agent, pay_id)

        add_agent_balance(agent_id, amount)



        released = queue_release_held(agent_id)



        try:

            await q.edit_message_text(

                f"Agent payment approved!\nRs{amount} added to {agent.get('agent_name')}")

        except: pass



        msg = f"Payment Approved!\nRs{amount} balance added.\n\n"

        if released:

            msg += (f"{len(released)} held application(s) forwarded to admin!\n\n"

                    f"Balance ke vajah se atki hui applications admin ko send kar di gayi hain.")

        try:

            await ctx.bot.send_message(

                int(agent["telegram_id"]), msg, reply_markup=kb_agent())

        except: pass



        for item in released:

            try:

                done_kb = InlineKeyboardMarkup([[

                    InlineKeyboardButton(

                        "DONE",

                        callback_data=f"QDONE|{item['queue_id']}|{item['client_code']}|{agent_id}|{agent.get('telegram_id',0)}|{item.get('client_tid',0)}")

                ]])

                await ctx.bot.send_message(

                    SUPER_ADMIN_ID,

                    f"Released Application\n{div()}\n"

                    f"ID: {item['queue_id']}\n"

                    f"App No: {item['app_no']}\n"

                    f"DOB: {item['dob']}\n"

                    f"Password: {item['password']}\n"

                    f"{div()}\n"

                    f"Client: {item.get('client_name')} | {item['client_code']}\n"

                    f"Agent: {agent.get('agent_name')}",

                    reply_markup=done_kb)

            except: pass



    elif data.startswith("AGPAY_REJ|"):

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        _, pay_id, agent_id = data.split("|")

        agent = agent_by_id(agent_id)

        if agent:

            reject_agent_payment(agent, pay_id)

        try:

            await q.edit_message_text("Agent payment rejected.")

        except: pass

        try:

            await ctx.bot.send_message(

                int(agent["telegram_id"]),

                "Payment Rejected. Admin se contact karo.",

                reply_markup=kb_agent())

        except: pass



    # ── Remove Agent ──────────────────────────────────────────

    elif data.startswith("REMOVE_AGENT|"):

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        agent_id = data.split("|")[1]

        remove_agent(agent_id)

        try:

            await q.edit_message_text(f"Agent {agent_id} removed.")

        except: pass



    # ── Add Agent Balance ─────────────────────────────────────

    elif data.startswith("AGENT_BAL|"):

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        agent_id = data.split("|")[1]

        user_data(tid)["adding_agent_bal_id"] = agent_id

        user_data(tid)["awaiting_agent_bal"]  = True

        try:

            await q.edit_message_text(f"Agent {agent_id} ko kitna balance add karna hai?\n(Amount type karo)")

        except: pass



    # ── Block/Unblock Client ──────────────────────────────────

    elif data.startswith("C_BLOCK|"):

        _, code, agent_id = data.split("|")

        agent = agent_by_id(agent_id)

        if agent: set_client_field(agent, code, "status", "blocked")

        try: await q.edit_message_text(f"Client {code} blocked.")

        except: pass



    elif data.startswith("C_UNBLK|"):

        _, code, agent_id = data.split("|")

        agent = agent_by_id(agent_id)

        if agent: set_client_field(agent, code, "status", "active")

        try: await q.edit_message_text(f"Client {code} unblocked.")

        except: pass



    # ── Admin Settings ────────────────────────────────────────

    elif data == "ADMIN_SET_QR":

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        user_data(tid)["awaiting_admin_qr"] = True

        try: await q.edit_message_text("QR photo bhejiye:")

        except: pass



    elif data == "ADMIN_SET_RATE":

        if tid != SUPER_ADMIN_ID:

            await q.answer("Only admin!", show_alert=True)

            return

        user_data(tid)["awaiting_admin_rate"] = True

        try: await q.edit_message_text("Naya rate daalo (Rs) - agent se per app charge:")

        except: pass



    # ── Agent Settings ────────────────────────────────────────

    elif data.startswith("SET_RATE|"):

        agent_id = data.split("|")[1]

        user_data(tid)["awaiting_rate"]  = True

        user_data(tid)["rate_agent_id"]  = agent_id

        try: await q.edit_message_text("Naya rate type karo (Rs):")

        except: pass



    elif data.startswith("SET_QR|"):

        user_data(tid)["awaiting_qr"] = True

        try: await q.edit_message_text("QR photo bhejiye:")

        except: pass



    # ── Broadcast callbacks ───────────────────────────────────

    elif data.startswith("BC_"):

        from handlers.agent import bc_type_cb

        await bc_type_cb(update, ctx)



    elif data.startswith("ABC_"):

        from handlers.admin import admin_bc_type_cb

        await admin_bc_type_cb(update, ctx)




