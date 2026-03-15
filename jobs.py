from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
logger = logging.getLogger(__name__)

def register_jobs(app):
    try:
        scheduler = AsyncIOScheduler()
        scheduler.start()
        logger.info("Jobs scheduler started")
    except Exception as e:
        logger.warning(f"Jobs: {e}")
