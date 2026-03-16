from telegram import Update

from telegram.ext import ContextTypes, ConversationHandler

from config import REG_NAME, REG_PHONE

from keyboards import kb_admin, kb_agent, kb_client, REMOVE

from db import agent_by_id, agent_by_tid, find_client, add_client, detect_role, agent_active

from utils import user_data, gen_client_code, valid_phone

import logging

logger = logging.getLogger(__name__)





async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid  = update.effective_user.id

    args = ctx.args

    if args and args[0].startswith("register_"):

        agent_id = args[0].replace("register_", "")

        agent    = agent_by_id(agent_id)

        if not agent or not agent_active(agent):

            await update.message.reply_text("Link valid nahi ya agent active nahi.")

            return ConversationHandler.END

        c, _ = find_client(tid)

        if c:

            await update.message.reply_text(

                f"Already registered!\nID: {c.get('client_code')}",

                reply_markup=kb_client())

            return ConversationHandler.END

        user_data(tid)["reg_agent_id"] = agent_id

        await update.message.reply_text(

            f"Faiz Online Service\n\nAgent: {agent.get('agent_name')}\n\nApna Poora Naam likhiye:",

            reply_markup=REMOVE)

        return REG_NAME

    role = detect_role(tid)

    if role == "admin":

        await update.message.reply_text("Admin Panel", reply_markup=kb_admin())

    elif role == "agent":

        ag = agent_by_tid(tid)

        if not agent_active(ag):

            await update.message.reply_text("Account block hai. Admin se contact karo.")

        else:

            await update.message.reply_text(

                f"Welcome {ag.get('agent_name')}!", reply_markup=kb_agent())

    elif role == "client":

        c, _ = find_client(tid)

        await update.message.reply_text(

            f"Welcome {c.get('full_name')}!\nID: {c.get('client_code')}",

            reply_markup=kb_client())

    else:

        await update.message.reply_text(

            "Faiz Online Service\n\nAgent se referral link maango register karne ke liye.")

    return ConversationHandler.END





async def reg_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid  = update.effective_user.id

    name = update.message.text.strip()

    if len(name) < 2:

        await update.message.reply_text("Sahi naam likhiye:")

        return REG_NAME

    user_data(tid)["full_name"] = name

    await update.message.reply_text(f"Naam: {name}\n\n10 digit Phone Number:")

    return REG_PHONE





async def reg_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid   = update.effective_user.id

    phone = update.message.text.strip()

    if not valid_phone(phone):

        await update.message.reply_text("10 digit phone number likhiye:")

        return REG_PHONE

    d     = user_data(tid)

    agent = agent_by_id(d.get("reg_agent_id", ""))

    if not agent:

        await update.message.reply_text("Agent nahi mila. Dobara link use karo.")

        return ConversationHandler.END

    code = gen_client_code(agent["agent_id"])

    ok   = add_client(agent, {

        "client_code": code,

        "full_name":   d["full_name"],

        "phone":       phone,

        "telegram_id": str(tid),

    })

    logger.info(f"add_client: ok={ok} tid={tid} agent={agent['agent_id']}")

    if not ok:

        await update.message.reply_text("Registration fail hua. Dobara try karo.")

        return ConversationHandler.END

    await update.message.reply_text(

        f"Registration Successful!\n\n"

        f"Client ID: {code}\n"

        f"Naam: {d['full_name']}\n"

        f"Phone: {phone}\n"

        f"Agent: {agent.get('agent_name')}\n"

        f"Rate: Rs{agent.get('rate_per_app')}/app",

        reply_markup=kb_client())

    try:

        await ctx.bot.send_message(

            int(agent["telegram_id"]),

            f"New Client Registered!\n\n"

            f"ID: {code}\n"

            f"Naam: {d['full_name']}\n"

            f"Phone: {phone}")

    except: pass

    return ConversationHandler.END





async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    tid  = update.effective_user.id

    role = detect_role(tid)

    kb   = (kb_admin() if role == "admin" else

            kb_agent() if role == "agent" else

            kb_client() if role == "client" else None)

    await update.message.reply_text("Cancelled.", reply_markup=kb)

    return ConversationHandler.END



