from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import ContextTypes, ConversationHandler

from config import BC_TYPE, BC_MSG, UR_RATE, SUPER_ADMIN_ID, AGENT_PAY_AMOUNT

from keyboards import kb_agent, REMOVE

from db import (agent_by_tid, all_clients, all_agent_payments,

                set_agent_field, put_setting, get_setting, agent_active,

                get_agent_balance, add_agent_payment, queue_all,

                queue_today_count, queue_held_by_agent, get_admin_qr)

from utils import user_data, today_ist, safe_float, safe_int, gen_pay_id, div





async def my_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    pend = [r for r in queue_all()

            if r.get("agent_id") == agent["agent_id"]

            and r.get("status","").upper() == "PENDING"]

    held = [r for r in queue_all()

            if r.get("agent_id") == agent["agent_id"]

            and r.get("status","").upper() == "HELD"]

    if not pend and not held:

        await update.message.reply_text("Koi pending application nahi!", reply_markup=kb_agent())

        return

    if pend:

        await update.message.reply_text(f"Pending: {len(pend)}")

        for ap in pend[:10]:

            await update.message.reply_text(

                f"{ap.get('queue_id')}\n"

                f"App No: {ap.get('app_no')} | DOB: {ap.get('dob')}\n"

                f"Client: {ap.get('client_name')}\n"

                f"Time: {ap.get('submitted_at','')[:16]}")

    if held:

        await update.message.reply_text(

            f"HELD ({len(held)}) - Balance low hone ke karan.\n"

            f"Pay Admin karke release karo.")

    await update.message.reply_text(div(), reply_markup=kb_agent())





async def today_summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    today = today_ist()

    my_q  = [r for r in queue_all()

             if r.get("agent_id") == agent["agent_id"]

             and r.get("submitted_at","").startswith(today)]

    done    = sum(1 for r in my_q if r.get("status") == "DONE")

    pending = sum(1 for r in my_q if r.get("status") == "PENDING")

    held    = sum(1 for r in my_q if r.get("status") == "HELD")

    rate    = safe_float(agent.get("rate_per_app",0))

    bal     = get_agent_balance(agent["agent_id"])

    await update.message.reply_text(

        f"Today Summary - {today}\n{div()}\n"

        f"Total: {len(my_q)}\n"

        f"Done: {done} | Pending: {pending} | Held: {held}\n"

        f"Today Earnings: Rs{done * rate}\n"

        f"My Balance: Rs{bal}",

        reply_markup=kb_agent())





async def my_clients(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid     = update.effective_user.id

    agent   = agent_by_tid(tid)

    clients = all_clients(agent)

    if not clients:

        await update.message.reply_text("Koi client nahi.", reply_markup=kb_agent())

        return

    await update.message.reply_text(f"My Clients ({len(clients)})")

    for c in clients:

        st = c.get("status","active")

        kb = InlineKeyboardMarkup([[

            InlineKeyboardButton("Block",   callback_data=f"C_BLOCK|{c['client_code']}|{agent['agent_id']}"),

            InlineKeyboardButton("Unblock", callback_data=f"C_UNBLK|{c['client_code']}|{agent['agent_id']}"),

        ]])

        try:

            await update.message.reply_text(

                f"{c.get('full_name')} | {st}\n"

                f"ID: {c.get('client_code')}\n"

                f"Phone: {c.get('phone')} | Balance: Rs{safe_float(c.get('balance',0))}\n"

                f"Apps: {c.get('total_apps',0)}",

                reply_markup=kb)

        except: pass

    try:

        bot_me   = await ctx.bot.get_me()

        ref_link = f"https://t.me/{bot_me.username}?start=register_{agent['agent_id']}"

        await update.message.reply_text(f"Referral Link:\n{ref_link}", reply_markup=kb_agent())

    except:

        await update.message.reply_text(div(), reply_markup=kb_agent())





async def my_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    my_q  = [r for r in queue_all() if r.get("agent_id") == agent["agent_id"]]

    done  = sum(1 for r in my_q if r.get("status") == "DONE")

    rate  = safe_float(agent.get("rate_per_app",0))

    bal   = get_agent_balance(agent["agent_id"])

    await update.message.reply_text(

        f"My Stats\n{div()}\n"

        f"Clients: {agent.get('total_clients',0)}\n"

        f"Total Apps: {len(my_q)} | Done: {done}\n"

        f"Total Earnings: Rs{done * rate}\n"

        f"Balance: Rs{bal}\n"

        f"Rate: Rs{rate}/app",

        reply_markup=kb_agent())





async def my_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    bal  = get_agent_balance(agent["agent_id"])

    held = queue_held_by_agent(agent["agent_id"])

    await update.message.reply_text(

        f"My Balance\n{div()}\n"

        f"Balance: Rs{bal}\n"

        f"Held apps: {len(held)}",

        reply_markup=kb_agent())





async def referral_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    try:

        bot_me   = await ctx.bot.get_me()

        ref_link = f"https://t.me/{bot_me.username}?start=register_{agent['agent_id']}"

        await update.message.reply_text(

            f"Aapka Referral Link:\n\n{ref_link}\n\n"

            f"Is link se clients register karein.",

            reply_markup=kb_agent())

    except:

        await update.message.reply_text("Link generate nahi hua.", reply_markup=kb_agent())





async def pay_admin_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return ConversationHandler.END

    bal   = get_agent_balance(agent["agent_id"])

    held  = queue_held_by_agent(agent["agent_id"])

    held_info = f"\n{len(held)} apps held (will release after payment)" if held else ""

    admin_qr  = get_admin_qr()

    caption   = (f"Pay Admin\n\nYour balance: Rs{bal}{held_info}\n\n"

                 f"UPI se payment karo phir amount type karo:")

    if admin_qr:

        try:

            await ctx.bot.send_photo(tid, admin_qr, caption=caption)

        except:

            await update.message.reply_text(caption, reply_markup=REMOVE)

    else:

        await update.message.reply_text(caption, reply_markup=REMOVE)

    user_data(tid)["agent_paying_admin"] = True

    user_data(tid)["pay_agent_obj"]      = agent

    return AGENT_PAY_AMOUNT



async def pay_admin_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    d   = user_data(tid)

    try:

        amount = safe_float(update.message.text.strip())

        if amount <= 0: raise ValueError

    except:

        await update.message.reply_text("Valid amount daalo:")

        return AGENT_PAY_AMOUNT

    agent  = d.get("pay_agent_obj")

    pay_id = gen_pay_id()

    add_agent_payment(agent, {"pay_id":pay_id,"amount":amount})

    d.pop("agent_paying_admin", None)

    kb = InlineKeyboardMarkup([[

        InlineKeyboardButton("Approve", callback_data=f"AGPAY_APP|{pay_id}|{agent['agent_id']}"),

        InlineKeyboardButton("Reject",  callback_data=f"AGPAY_REJ|{pay_id}|{agent['agent_id']}"),

    ]])

    await update.message.reply_text(

        f"Payment request bheja!\nAmount: Rs{amount}\nAdmin approve karega.",

        reply_markup=kb_agent())

    try:

        await ctx.bot.send_message(

            SUPER_ADMIN_ID,

            f"Agent Payment Request\n\n"

            f"Agent: {agent.get('agent_name')} ({agent.get('agent_id')})\n"

            f"Amount: Rs{amount}\n"

            f"Pay ID: {pay_id}",

            reply_markup=kb)

    except: pass

    return ConversationHandler.END





async def settings_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    rate = get_setting(agent, "rate_per_app") or agent.get("rate_per_app","N/A")

    qr   = get_setting(agent, "qr_file_id")

    kb   = InlineKeyboardMarkup([

        [InlineKeyboardButton("Update Rate", callback_data=f"SET_RATE|{agent['agent_id']}")],

        [InlineKeyboardButton("Upload QR",   callback_data=f"SET_QR|{agent['agent_id']}")],

    ])

    await update.message.reply_text(

        f"Settings\n{div()}\n"

        f"Rate: Rs{rate}/app\n"

        f"QR: {'Set' if qr else 'Not set'}",

        reply_markup=kb)





async def broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    kb = InlineKeyboardMarkup([[

        InlineKeyboardButton("Text",  callback_data="BC_TEXT"),

        InlineKeyboardButton("Image", callback_data="BC_IMAGE"),

    ]])

    await update.message.reply_text("Broadcast type chuniye:", reply_markup=kb)

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

    from db import all_clients

    clients = all_clients(agent)

    sent = failed = 0

    for c in clients:

        try:

            ct = int(c.get("telegram_id",0))

            if not ct: continue

            if bc_type == "text":

                await ctx.bot.send_message(ct, update.message.text)

            elif bc_type == "image" and update.message.photo:

                await ctx.bot.send_photo(ct, update.message.photo[-1].file_id,

                                         caption=update.message.caption or "")

            sent += 1

        except: failed += 1

    await update.message.reply_text(

        f"Broadcast done!\nSent: {sent} | Failed: {failed}", reply_markup=kb_agent())

    return ConversationHandler.END





async def qr_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return False

    d = user_data(tid)

    if not d.get("awaiting_qr"): return False

    file_id = update.message.photo[-1].file_id

    put_setting(agent, "qr_file_id", file_id)

    set_agent_field(agent["agent_id"], "qr_file_id", file_id)

    d.pop("awaiting_qr", None)

    await update.message.reply_text("QR save ho gaya!", reply_markup=kb_agent())

    return True



async def rate_start(update, ctx):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return ConversationHandler.END

    user_data(tid)["rate_agent"] = agent

    await update.message.reply_text("Naya rate daalo (Rs):", reply_markup=REMOVE)

    return UR_RATE



async def rate_save(update, ctx):

    tid = update.effective_user.id

    try:

        rate = float(update.message.text.strip())

    except:

        await update.message.reply_text("Number daalo:")

        return UR_RATE

    agent = user_data(tid).get("rate_agent") or agent_by_tid(tid)

    set_agent_field(agent["agent_id"], "rate_per_app", rate)

    put_setting(agent, "rate_per_app", str(rate))

    await update.message.reply_text(f"Rate updated: Rs{rate}/app", reply_markup=kb_agent())

    return ConversationHandler.END



async def work_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    agent = agent_by_tid(tid)

    if not agent: return

    my_q  = [r for r in queue_all() if r.get("agent_id") == agent["agent_id"]]

    done  = [r for r in my_q if r.get("status") == "DONE"][-10:]

    if not done:

        await update.message.reply_text("Koi done app nahi.", reply_markup=kb_agent())

        return

    await update.message.reply_text(f"Work History (last {len(done)})")

    for ap in reversed(done):

        await update.message.reply_text(

            f"Done | {ap.get('queue_id')}\n"

            f"App No: {ap.get('app_no')}\n"

            f"Client: {ap.get('client_name')}\n"

            f"Done at: {ap.get('done_at','')[:16]}")

    await update.message.reply_text(div(), reply_markup=kb_agent())



