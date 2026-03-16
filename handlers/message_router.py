from telegram import Update

from telegram.ext import ContextTypes

from db import detect_role, agent_by_tid, find_client, agent_active

from keyboards import kb_admin, kb_agent, kb_client

from utils import user_data, safe_float



from handlers.admin import (dashboard, all_agents_cmd, agent_payments_cmd,

                             admin_settings_cmd, show_queue, show_done,

                             monthly_report, admin_qr_receive)

from handlers.agent import (my_queue, today_summary, work_history, my_clients,

                             my_stats, my_balance, referral_link,

                             settings_cmd, pay_admin_start)

from handlers.client import (my_apps, my_balance as client_balance, my_profile,

                              contact_agent, pay_start, handle_pay_amount_input)





async def photo_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    # Admin QR first

    if await admin_qr_receive(update, ctx):

        return

    # Agent QR

    from handlers.agent import qr_receive

    await qr_receive(update, ctx)





async def message_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:

        return

    tid  = update.effective_user.id

    text = update.message.text.strip()

    d    = user_data(tid)



    # Awaiting payment amount (client)

    if d.get("awaiting_pay_amount"):

        await handle_pay_amount_input(update, ctx)

        return



    # Awaiting admin rate

    if d.get("awaiting_admin_rate"):

        try:

            rate = safe_float(text)

            if rate > 0:

                from db import set_admin_setting

                set_admin_setting("rate_per_app", str(rate))

                await update.message.reply_text(

                    f"Admin rate updated: Rs{rate}/app", reply_markup=kb_admin())

            else:

                await update.message.reply_text("Valid amount daalo:", reply_markup=kb_admin())

        except:

            await update.message.reply_text("Valid amount daalo:", reply_markup=kb_admin())

        d.pop("awaiting_admin_rate", None)

        return



    # Awaiting agent balance (admin adding)

    if d.get("awaiting_agent_bal"):

        try:

            amount   = safe_float(text)

            agent_id = d.get("adding_agent_bal_id","")

            if amount > 0 and agent_id:

                from db import add_agent_balance, agent_by_id

                add_agent_balance(agent_id, amount)

                ag = agent_by_id(agent_id)

                name = ag.get("agent_name","") if ag else agent_id

                await update.message.reply_text(

                    f"Rs{amount} added to {name}", reply_markup=kb_admin())

                if ag:

                    try:

                        await ctx.bot.send_message(

                            int(ag["telegram_id"]),

                            f"Admin ne Rs{amount} balance add kiya!")

                    except: pass

            else:

                await update.message.reply_text("Valid amount daalo:", reply_markup=kb_admin())

        except:

            await update.message.reply_text("Valid amount daalo:", reply_markup=kb_admin())

        d.pop("awaiting_agent_bal", None)

        d.pop("adding_agent_bal_id", None)

        return



    # Awaiting rate update (agent)

    if d.get("awaiting_rate"):

        try:

            rate     = float(text)

            agent_id = d.get("rate_agent_id","")

            if rate > 0:

                from db import set_agent_field, put_setting, agent_by_id

                ag = agent_by_id(agent_id) if agent_id else agent_by_tid(tid)

                if ag:

                    set_agent_field(ag["agent_id"], "rate_per_app", rate)

                    put_setting(ag, "rate_per_app", str(rate))

                await update.message.reply_text(

                    f"Rate updated: Rs{rate}/app", reply_markup=kb_agent())

            else:

                await update.message.reply_text("Valid number daalo:")

        except:

            await update.message.reply_text("Valid number daalo:")

        d.pop("awaiting_rate", None)

        d.pop("rate_agent_id", None)

        return



    role = detect_role(tid)



    if role == "admin":

        routes = {

            "Dashboard":       dashboard,

            "All Agents":      all_agents_cmd,

            "Queue":           show_queue,

            "Done Apps":       show_done,

            "Agent Payments":  agent_payments_cmd,

            "Settings":        admin_settings_cmd,

            "Monthly Report":  monthly_report,

        }

        fn = routes.get(text)

        if fn:

            await fn(update, ctx)

        else:

            await update.message.reply_text("Button use karein:", reply_markup=kb_admin())



    elif role == "agent":

        agent = agent_by_tid(tid)

        if not agent_active(agent):

            await update.message.reply_text("Account block hai. Admin se contact karo.")

            return

        if text == "Refresh":

            from handlers.registration import cmd_start

            await cmd_start(update, ctx)

            return

        routes = {

            "My Queue":      my_queue,

            "Today Summary": today_summary,

            "Work History":  work_history,

            "My Clients":    my_clients,

            "My Stats":      my_stats,

            "My Balance":    my_balance,

            "Pay Admin":     pay_admin_start,

            "Referral Link": referral_link,

            "Settings":      settings_cmd,

        }

        fn = routes.get(text)

        if fn:

            await fn(update, ctx)

        else:

            await update.message.reply_text("Button use karein:", reply_markup=kb_agent())



    elif role == "client":

        c, ag = find_client(tid)

        if c and c.get("status") == "blocked":

            await update.message.reply_text("Account block hai. Agent se contact karo.")

            return

        routes = {

            "My Apps":       my_apps,

            "My Balance":    client_balance,

            "Pay Agent":     pay_start,

            "My Profile":    my_profile,

            "Contact Agent": contact_agent,

        }

        fn = routes.get(text)

        if fn:

            await fn(update, ctx)

        else:

            await update.message.reply_text("Apna panel:", reply_markup=kb_client())



    else:

        await update.message.reply_text(

            "Registered nahi hain.\nAgent se referral link maango.")



          
