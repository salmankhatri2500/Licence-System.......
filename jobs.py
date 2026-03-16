
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from zoneinfo import ZoneInfo



logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")





async def agent_balance_reminder(bot):

    try:

        from db import all_agents, get_agent_balance, get_admin_rate, agent_active

        rate = get_admin_rate()

        if rate <= 0: return

        threshold = rate * 5

        for ag in all_agents():

            if not agent_active(ag): continue

            bal   = get_agent_balance(ag["agent_id"])

            at    = int(ag.get("telegram_id", 0))

            if not at: continue

            if bal < threshold:

                apps_left = int(bal // rate)

                try:

                    await bot.send_message(

                        at,

                        f"Balance Low Reminder!\n\n"

                        f"Balance: Rs{bal}\n"

                        f"Apps remaining: ~{apps_left}\n\n"

                        f"Pay Admin karke balance top-up karo.")

                except: pass

    except Exception as e:

        logger.error(f"agent_balance_reminder: {e}")





async def client_balance_reminder(bot):

    try:

        from db import all_agents, all_clients, get_balance, agent_active

        from utils import safe_float

        for ag in all_agents():

            if not agent_active(ag): continue

            rate = safe_float(ag.get("rate_per_app", 0))

            if rate <= 0: continue

            threshold = rate * 5

            for c in all_clients(ag):

                if c.get("status") == "blocked": continue

                bal = get_balance(ag, c["client_code"])

                ct  = int(c.get("telegram_id", 0))

                if not ct: continue

                if bal < threshold:

                    apps_left = int(bal // rate)

                    try:

                        await bot.send_message(

                            ct,

                            f"Balance Low!\n\n"

                            f"Balance: Rs{bal}\n"

                            f"Apps possible: ~{apps_left}\n\n"

                            f"Pay Agent button se recharge karo.")

                    except: pass

    except Exception as e:

        logger.error(f"client_balance_reminder: {e}")





def register_jobs(app):

    try:

        s = AsyncIOScheduler(timezone=IST)

        s.add_job(agent_balance_reminder,  "interval", minutes=150,

                  args=[app.bot], id="agent_bal",  replace_existing=True)

        s.add_job(client_balance_reminder, "interval", minutes=150,

                  args=[app.bot], id="client_bal", replace_existing=True)

        s.start()

        logger.info("Jobs started: balance reminders every 2.5 hours")

    except Exception as e:

        logger.warning(f"Jobs error: {e}")



