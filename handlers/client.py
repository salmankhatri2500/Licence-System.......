from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import ContextTypes, ConversationHandler

from config import APP_NO, APP_DOB, APP_PASS, SUPER_ADMIN_ID

from keyboards import kb_client, REMOVE

from db import (find_client, get_setting, get_balance, deduct_balance,

                add_app, add_payment, inc_client_apps, queue_add, queue_mark_held,

                get_agent_balance, get_admin_rate, agent_by_id, set_client_field)

from utils import user_data, now_ist, today_ist, gen_app_id, gen_pay_id, valid_dob, safe_float, div

import logging

logger = logging.getLogger(__name__)





async def new_app_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    c, ag = find_client(tid)

    if not c:

        await update.message.reply_text("Registered nahi hain.", reply_markup=kb_client())

        return ConversationHandler.END

    if c.get("status") == "blocked":

        await update.message.reply_text("Account block hai.", reply_markup=kb_client())

        return ConversationHandler.END

    rate = safe_float(ag.get("rate_per_app", 0))

    bal  = get_balance(ag, c["client_code"])

    if bal < rate:

        await update.message.reply_text(

            f"Balance kam hai!\nBalance: Rs{bal}\nRequired: Rs{rate}\n\nPehle balance add karo.",

            reply_markup=kb_client())

        await _show_qr(update, ctx, c, ag)

        return ConversationHandler.END

    user_data(tid)["app_ag"] = ag

    user_data(tid)["app_c"]  = c

    await update.message.reply_text(

        f"New Application\n\nBalance: Rs{bal} | Rate: Rs{rate}\n\nStep 1/3 - Application Number:",

        reply_markup=REMOVE)

    return APP_NO



async def app_no(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    no  = update.message.text.strip()

    if len(no) < 3:

        await update.message.reply_text("Valid application number daalo:")

        return APP_NO

    user_data(tid)["app_no"] = no

    await update.message.reply_text("Step 2/3 - Date of Birth (DD/MM/YYYY):")

    return APP_DOB



async def app_dob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    dob = update.message.text.strip()

    if not valid_dob(dob):

        await update.message.reply_text("Valid DOB daalo (DD/MM/YYYY):")

        return APP_DOB

    user_data(tid)["app_dob"] = dob

    await update.message.reply_text("Step 3/3 - Password:")

    return APP_PASS



async def app_pass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid  = update.effective_user.id

    pwd  = update.message.text.strip()

    d    = user_data(tid)

    ag   = d.get("app_ag")

    c    = d.get("app_c")

    if not ag or not c:

        await update.message.reply_text("Session expire. Dobara try karo.", reply_markup=kb_client())

        return ConversationHandler.END



    rate   = safe_float(ag.get("rate_per_app", 0))

    app_id = gen_app_id()



    deduct_balance(ag, c["client_code"], rate)

    inc_client_apps(ag, c["client_code"])



    add_app(ag, {"app_id":app_id,"app_no":d["app_no"],"dob":d["app_dob"],

                 "password":pwd,"client_code":c["client_code"]})



    queue_add({

        "queue_id":    app_id,

        "app_no":      d["app_no"],

        "dob":         d["app_dob"],

        "password":    pwd,

        "client_code": c["client_code"],

        "client_name": c.get("full_name",""),

        "client_tid":  str(tid),

        "agent_id":    ag.get("agent_id",""),

        "agent_name":  ag.get("agent_name",""),

        "agent_tid":   ag.get("telegram_id",""),

        "priority":    "normal",

    })



    bal_left  = get_balance(ag, c["client_code"])

    agent_bal = get_agent_balance(ag.get("agent_id",""))

    admin_rate = get_admin_rate()

    low_warn  = ""

    if rate > 0 and bal_left < (rate * 5):

        apps_left = int(bal_left // rate)

        low_warn  = f"\n\nBalance Low Warning: ~{apps_left} apps remaining. Recharge karo!"



    # Check agent balance

    if admin_rate > 0 and agent_bal < admin_rate:

        queue_mark_held(app_id)

        try:

            await ctx.bot.send_message(

                int(ag["telegram_id"]),

                f"Application HELD - Low Balance!\n\n"

                f"Your balance: Rs{agent_bal}\n"

                f"Required per app: Rs{admin_rate}\n\n"

                f"Client: {c.get('full_name')}\n"

                f"App No: {d['app_no']}\n\n"

                f"Pay Admin to release held applications.")

        except: pass

        await update.message.reply_text(

            f"Application Submitted!\n\n"

            f"App ID: {app_id}\n"

            f"App No: {d['app_no']}\n"

            f"Balance remaining: Rs{bal_left}"

            f"{low_warn}\n\n"

            f"Note: Agent balance low hai. App processing hold mein hai.",

            reply_markup=kb_client())

        return ConversationHandler.END



    # Agent balance warn

    agent_warn = ""

    if admin_rate > 0 and agent_bal < (admin_rate * 5):

        apps_left_ag = int(agent_bal // admin_rate)

        agent_warn = (f"\n\nAgent Balance Low: Rs{agent_bal} (~{apps_left_ag} apps). "

                      f"Top-up karo!")



    await update.message.reply_text(

        f"Application Submitted!\n\n"

        f"App ID: {app_id}\n"

        f"App No: {d['app_no']}\n"

        f"Balance remaining: Rs{bal_left}"

        f"{low_warn}\n\n"

        f"Processing queue mein hai. Done hone par notify karenge!",

        reply_markup=kb_client())



    # Notify agent

    try:

        await ctx.bot.send_message(

            int(ag["telegram_id"]),

            f"New Application in Queue!\n\n"

            f"Client: {c.get('full_name')} ({c['client_code']})\n"

            f"App No: {d['app_no']}\n"

            f"Queue ID: {app_id}"

            f"{agent_warn}")

    except: pass



    # Notify admin

    try:

        done_kb = InlineKeyboardMarkup([[

            InlineKeyboardButton(

                "DONE",

                callback_data=f"QDONE|{app_id}|{c['client_code']}|{ag['agent_id']}|{ag.get('telegram_id',0)}|{tid}")

        ]])

        await ctx.bot.send_message(

            SUPER_ADMIN_ID,

            f"New Application\n{div()}\n"

            f"Queue ID: {app_id}\n"

            f"App No: {d['app_no']}\n"

            f"DOB: {d['app_dob']}\n"

            f"Password: {pwd}\n"

            f"{div()}\n"

            f"Client: {c.get('full_name')} | {c['client_code']}\n"

            f"Agent: {ag.get('agent_name')} | {ag.get('agent_id')}",

            reply_markup=done_kb)

    except Exception as e:

        logger.error(f"admin notify: {e}")



    return ConversationHandler.END





async def _show_qr(update, ctx, c, ag):

    qr = get_setting(ag, "qr_file_id")

    tid = update.effective_user.id

    if qr:

        try:

            await ctx.bot.send_photo(

                tid, qr,

                caption=f"QR se payment karo\nRate: Rs{ag.get('rate_per_app')}/app\nPhir amount type karo:")

            user_data(tid)["awaiting_pay_amount"] = True

            user_data(tid)["pay_agent"]  = ag

            user_data(tid)["pay_client"] = c

            return

        except: pass

    await update.message.reply_text("Agent se payment karo aur unhe batao.", reply_markup=kb_client())



async def pay_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    c, ag = find_client(tid)

    if not c:

        await update.message.reply_text("Registered nahi hain.", reply_markup=kb_client())

        return

    await _show_qr(update, ctx, c, ag)



async def handle_pay_amount_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    d   = user_data(tid)

    try:

        amount = safe_float(update.message.text.strip())

        if amount <= 0: raise ValueError

    except:

        await update.message.reply_text("Valid amount daalo:")

        return

    ag = d.get("pay_agent")

    c  = d.get("pay_client")

    if not ag or not c:

        await update.message.reply_text("Session expire. Dobara try karo.", reply_markup=kb_client())

        d.pop("awaiting_pay_amount", None)

        return

    pay_id = gen_pay_id()

    add_payment(ag, {"pay_id":pay_id,"client_code":c["client_code"],"amount":amount})

    d.pop("awaiting_pay_amount", None)

    kb = InlineKeyboardMarkup([[

        InlineKeyboardButton("Approve", callback_data=f"PAY_APP|{pay_id}|{c['client_code']}|{ag['agent_id']}|{tid}"),

        InlineKeyboardButton("Reject",  callback_data=f"PAY_REJ|{pay_id}|{c['client_code']}|{ag['agent_id']}|{tid}"),

    ]])

    await update.message.reply_text(

        f"Payment request bheja!\nAmount: Rs{amount}\nAgent approve karega.",

        reply_markup=kb_client())

    try:

        await ctx.bot.send_message(

            int(ag["telegram_id"]),

            f"Payment Request\n\n"

            f"Client: {c.get('full_name')} ({c['client_code']})\n"

            f"Amount: Rs{amount}",

            reply_markup=kb)

    except: pass





async def my_apps(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    c, ag = find_client(tid)

    if not c:

        await update.message.reply_text("Registered nahi hain.", reply_markup=kb_client())

        return

    from db import queue_all

    my = [r for r in queue_all() if r.get("client_code") == c.get("client_code")]

    if not my:

        await update.message.reply_text("Koi application nahi.", reply_markup=kb_client())

        return

    await update.message.reply_text(f"My Applications ({len(my)})")

    for ap in my[-10:]:

        st = ap.get("status","")

        icon = "Done" if st == "DONE" else "Held" if st == "HELD" else "Pending"

        await update.message.reply_text(

            f"{icon} | {ap.get('queue_id')}\n"

            f"App No: {ap.get('app_no')} | DOB: {ap.get('dob')}\n"

            f"Time: {ap.get('submitted_at','')[:16]}")

    await update.message.reply_text(div(), reply_markup=kb_client())



async def my_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    c, ag = find_client(tid)

    if not c:

        await update.message.reply_text("Registered nahi hain.", reply_markup=kb_client())

        return

    bal  = get_balance(ag, c["client_code"])

    rate = safe_float(ag.get("rate_per_app", 0))

    await update.message.reply_text(

        f"My Balance\n{div()}\n"

        f"Balance: Rs{bal}\n"

        f"Rate: Rs{rate}/app\n"

        f"Apps possible: {int(bal//rate) if rate else 0}",

        reply_markup=kb_client())



async def my_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    c, ag = find_client(tid)

    if not c:

        await update.message.reply_text("Registered nahi hain.", reply_markup=kb_client())

        return

    await update.message.reply_text(

        f"My Profile\n{div()}\n"

        f"ID: {c.get('client_code')}\n"

        f"Naam: {c.get('full_name')}\n"

        f"Phone: {c.get('phone')}\n"

        f"Agent: {ag.get('agent_name')}\n"

        f"Joined: {c.get('joined_at','')[:10]}\n"

        f"Total Apps: {c.get('total_apps',0)}",

        reply_markup=kb_client())



async def contact_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    c, ag = find_client(tid)

    if not c:

        await update.message.reply_text("Registered nahi hain.", reply_markup=kb_client())

        return

    await update.message.reply_text(

        f"Agent Contact\n{div()}\n"

        f"Naam: {ag.get('agent_name')}\n"

        f"Phone: {ag.get('phone')}",

        reply_markup=kb_client())



