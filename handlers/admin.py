from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import ContextTypes, ConversationHandler

from config import (SUPER_ADMIN_ID, AA_NAME, AA_PHONE, AA_TID,

                    AA_RATE, AA_SHEET, ABC_TYPE, ABC_MSG)

from keyboards import kb_admin, REMOVE

from db import (all_agents, agent_by_id, add_agent, set_agent_field, remove_agent,

                master_log, all_payments, all_agent_payments, setup_manual_sheet,

                agent_by_tid, agent_active, queue_pending, queue_all,

                queue_today_count, add_agent_balance, approve_agent_payment,

                reject_agent_payment, get_agent_balance, get_agent_payment_amount,

                get_admin_qr, get_admin_rate, set_admin_setting, queue_release_held)

from utils import (user_data, now_ist, today_ist, month_ist,

                   safe_float, safe_int, gen_agent_id, valid_phone, div)



def is_admin(tid): return tid == SUPER_ADMIN_ID





async def dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    agents = all_agents()

    active = sum(1 for a in agents if agent_active(a))

    q      = queue_today_count()

    rate   = get_admin_rate()

    t_cl   = sum(safe_int(a.get("total_clients",0)) for a in agents)

    await update.message.reply_text(

        f"Dashboard - {today_ist()}\n{div()}\n"

        f"Agents: {len(agents)} ({active} active)\n"

        f"Clients: {t_cl}\n"

        f"Admin Rate: Rs{rate}/app\n\n"

        f"Today Queue\n"

        f"Total: {q['total']} | Done: {q['done']} | Pending: {q['pending']} | Held: {q['held']}",

        reply_markup=kb_admin())





async def show_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    pending = queue_pending()

    if not pending:

        await update.message.reply_text("Queue khali hai! Koi pending app nahi.", reply_markup=kb_admin())

        return

    await update.message.reply_text(f"Pending Queue: {len(pending)}")

    for ap in pending[:25]:

        kb = InlineKeyboardMarkup([[

            InlineKeyboardButton(

                "DONE",

                callback_data=f"QDONE|{ap['queue_id']}|{ap['client_code']}|{ap['agent_id']}|{ap.get('agent_tid',0)}|{ap.get('client_tid',0)}")

        ]])

        try:

            await update.message.reply_text(

                f"ID: {ap.get('queue_id')}\n"

                f"App No: {ap.get('app_no')}\n"

                f"DOB: {ap.get('dob')}\n"

                f"Password: {ap.get('password')}\n"

                f"Client: {ap.get('client_name')} | {ap.get('client_code')}\n"

                f"Agent: {ap.get('agent_name')}\n"

                f"Time: {ap.get('submitted_at','')[:16]}",

                reply_markup=kb)

        except: pass

    if len(pending) > 25:

        await update.message.reply_text(f"...and {len(pending)-25} more pending", reply_markup=kb_admin())

    else:

        await update.message.reply_text(div(), reply_markup=kb_admin())





async def show_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    all_q  = queue_all()

    done   = [r for r in all_q if r.get("status","").upper() == "DONE"]

    today  = [r for r in done if r.get("done_at","").startswith(today_ist())]

    await update.message.reply_text(

        f"Done Apps\n{div()}\nToday: {len(today)}\nTotal: {len(done)}",

        reply_markup=kb_admin())





async def all_agents_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    agents = all_agents()

    if not agents:

        await update.message.reply_text("Koi agent nahi.", reply_markup=kb_admin())

        return

    await update.message.reply_text(f"All Agents ({len(agents)})")

    for a in agents:

        bal = safe_float(a.get("balance", 0))

        st  = "Active" if agent_active(a) else "Blocked"

        kb  = InlineKeyboardMarkup([[

            InlineKeyboardButton("Remove", callback_data=f"REMOVE_AGENT|{a['agent_id']}"),

            InlineKeyboardButton("Add Balance", callback_data=f"AGENT_BAL|{a['agent_id']}"),

        ]])

        try:

            await update.message.reply_text(

                f"{a.get('agent_name')} | {st}\n"

                f"ID: {a.get('agent_id')}\n"

                f"Phone: {a.get('phone')}\n"

                f"Rate: Rs{a.get('rate_per_app')}/app | Balance: Rs{bal}\n"

                f"Apps: {a.get('total_apps',0)} | Clients: {a.get('total_clients',0)}\n"

                f"Sheet: {a.get('sheet_name')}",

                reply_markup=kb)

        except: pass

    await update.message.reply_text(div(), reply_markup=kb_admin())





async def agent_payments_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    pending = []

    for ag in all_agents():

        for p in all_agent_payments(ag):

            if p.get("status","").upper() == "PENDING":

                p["_ag"] = ag

                pending.append(p)

    if not pending:

        await update.message.reply_text("Koi pending agent payment nahi.", reply_markup=kb_admin())

        return

    await update.message.reply_text(f"Agent Payments ({len(pending)} pending)")

    for p in pending:

        ag = p["_ag"]

        kb = InlineKeyboardMarkup([[

            InlineKeyboardButton("Approve", callback_data=f"AGPAY_APP|{p['payment_id']}|{ag['agent_id']}"),

            InlineKeyboardButton("Reject",  callback_data=f"AGPAY_REJ|{p['payment_id']}|{ag['agent_id']}"),

        ]])

        await update.message.reply_text(

            f"Agent: {ag.get('agent_name')}\n"

            f"Amount: Rs{p.get('amount')}\n"

            f"Date: {p.get('date')} {p.get('time')}",

            reply_markup=kb)

    await update.message.reply_text(div(), reply_markup=kb_admin())





async def admin_settings_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    rate = get_admin_rate()

    qr   = get_admin_qr()

    kb   = InlineKeyboardMarkup([

        [InlineKeyboardButton("Upload/Update QR", callback_data="ADMIN_SET_QR")],

        [InlineKeyboardButton("Update App Rate",  callback_data="ADMIN_SET_RATE")],

    ])

    await update.message.reply_text(

        f"Admin Settings\n{div()}\n"

        f"App Rate (charged to agents): Rs{rate}/app\n"

        f"QR: {'Set' if qr else 'Not set'}\n\n"

        f"Kya update karna hai?",

        reply_markup=kb)





async def admin_qr_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:

    tid = update.effective_user.id

    if not is_admin(tid): return False

    d   = user_data(tid)

    if not d.get("awaiting_admin_qr"): return False

    if not update.message.photo:

        await update.message.reply_text("Photo bhejiye.", reply_markup=kb_admin())

        return True

    from db import set_admin_setting

    file_id = update.message.photo[-1].file_id

    set_admin_setting("qr_file_id", file_id)

    d.pop("awaiting_admin_qr", None)

    await update.message.reply_text("Admin QR save ho gaya!", reply_markup=kb_admin())

    return True





async def add_agent_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return ConversationHandler.END

    await update.message.reply_text(

        "New Agent\n\nStep 1/5 - Agent ka Naam:", reply_markup=REMOVE)

    return AA_NAME



async def aa_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    user_data(tid)["aa_name"] = update.message.text.strip()

    await update.message.reply_text(

        f"Naam: {user_data(tid)['aa_name']}\n\nStep 2/5 - Phone (10 digit):")

    return AA_PHONE



async def aa_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    phone = update.message.text.strip()

    if not valid_phone(phone):

        await update.message.reply_text("10 digit phone daalo:")

        return AA_PHONE

    user_data(tid)["aa_phone"] = phone

    await update.message.reply_text(f"Phone: {phone}\n\nStep 3/5 - Telegram ID:")

    return AA_TID



async def aa_tid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    raw = update.message.text.strip()

    if not raw.lstrip("-").isdigit():

        await update.message.reply_text("Sirf number daalo:")

        return AA_TID

    user_data(tid)["aa_tid"] = raw

    await update.message.reply_text(

        f"TID: {raw}\n\nStep 4/5 - Rate per App (Rs) - agent client se kitna charge karega:")

    return AA_RATE



async def aa_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid = update.effective_user.id

    try:

        rate = float(update.message.text.strip())

    except ValueError:

        await update.message.reply_text("Number daalo (e.g. 30):")

        return AA_RATE

    user_data(tid)["aa_rate"] = rate

    await update.message.reply_text(

        f"Rate: Rs{rate}/app\n\n"

        f"Step 5/5 - Google Sheet ka exact naam daalo:\n"

        f"(Jo sheet manually banai hai uska naam)")

    return AA_SHEET



async def aa_sheet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid        = update.effective_user.id

    sheet_name = update.message.text.strip()

    d          = user_data(tid)

    rate       = d.get("aa_rate", 0)

    agent_name = d.get("aa_name", "")

    agent_id   = gen_agent_id()



    await update.message.reply_text("Setting up... please wait.")



    # Setup sheet

    try:

        ok_sheet = setup_manual_sheet(sheet_name, agent_id, agent_name, rate)

    except Exception as e:

        import logging

        logging.getLogger(__name__).error(f"setup_manual_sheet: {e}")

        ok_sheet = False



    if not ok_sheet:

        await update.message.reply_text(

            f"Sheet '{sheet_name}' nahi mili!\n\n"

            f"Check karo:\n"

            f"1. Sheet naam exactly same ho\n"

            f"2. Service account ko Editor access ho\n\n"

            f"Sahi naam daalo:",

            reply_markup=kb_admin())

        return AA_SHEET



    # Save agent

    try:

        ok = add_agent({

            "agent_id":    agent_id,

            "agent_name":  agent_name,

            "phone":       d.get("aa_phone", ""),

            "telegram_id": int(d.get("aa_tid", 0)),

            "sheet_name":  sheet_name,

            "rate":        rate,

        })

    except Exception as e:

        import logging

        logging.getLogger(__name__).error(f"add_agent: {e}")

        ok = False



    if not ok:

        await update.message.reply_text(

            "FOS_Master mein save nahi hua.\n"

            "FOS_Master sheet service account se share hai?",

            reply_markup=kb_admin())

        return ConversationHandler.END



    try:

        bot_me   = await ctx.bot.get_me()

        ref_link = f"https://t.me/{bot_me.username}?start=register_{agent_id}"

    except:

        ref_link = "N/A"



    await update.message.reply_text(

        f"Agent Added Successfully!\n\n"

        f"ID: {agent_id}\n"

        f"Naam: {agent_name}\n"

        f"Phone: {d.get('aa_phone', '')}\n"

        f"Sheet: {sheet_name}\n"

        f"Rate: Rs{rate}/app\n\n"

        f"Referral Link:\n{ref_link}",

        reply_markup=kb_admin())



    try:

        await ctx.bot.send_message(

            int(d.get("aa_tid", 0)),

            f"Aapko FOS Agent banaya gaya!\n\n"

            f"Agent ID: {agent_id}\n"

            f"Rate: Rs{rate}/app\n\n"

            f"/start bhejiye shuru karne ke liye.")

    except: pass



    return ConversationHandler.END





async def find_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    args = ctx.args

    if not args:

        await update.message.reply_text("Usage: /find_agent <naam ya ID>", reply_markup=kb_admin())

        return

    q = " ".join(args).lower()

    res = [a for a in all_agents()

           if q in a.get("agent_name","").lower() or q in a.get("agent_id","").lower()]

    if not res:

        await update.message.reply_text("Nahi mila.", reply_markup=kb_admin())

        return

    for a in res:

        await update.message.reply_text(

            f"{a['agent_name']}\n{a['agent_id']}\n{a['sheet_name']}",

            reply_markup=kb_admin())





async def monthly_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return

    mon   = month_ist()

    all_q = queue_all()

    mq    = [r for r in all_q if r.get("submitted_at","").startswith(mon)]

    done  = sum(1 for r in mq if r.get("status") == "DONE")

    await update.message.reply_text(

        f"Monthly Report - {mon}\n{div()}\n"

        f"Apps: {len(mq)} | Done: {done}",

        reply_markup=kb_admin())





async def admin_bc_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id): return ConversationHandler.END

    kb = InlineKeyboardMarkup([[

        InlineKeyboardButton("Text",  callback_data="ABC_TEXT"),

        InlineKeyboardButton("Image", callback_data="ABC_IMAGE"),

        InlineKeyboardButton("Voice", callback_data="ABC_VOICE"),

    ]])

    await update.message.reply_text("Broadcast type chuniye:", reply_markup=kb)

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

    agents  = [a for a in all_agents() if agent_active(a)]

    sent = failed = 0

    for ag in agents:

        try:

            at = int(ag.get("telegram_id",0))

            if not at: continue

            if bc_type == "text":

                await ctx.bot.send_message(at, update.message.text)

            elif bc_type == "image" and update.message.photo:

                await ctx.bot.send_photo(at, update.message.photo[-1].file_id,

                                         caption=update.message.caption or "")

            elif bc_type == "voice" and update.message.voice:

                await ctx.bot.send_voice(at, update.message.voice.file_id)

            sent += 1

        except: failed += 1

    await update.message.reply_text(

        f"Broadcast done!\nSent: {sent} | Failed: {failed}", reply_markup=kb_admin())

    return ConversationHandler.END



