import asyncio
import discord
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import db
from db.dbmanager import client as dbclient
from config import SCHEDULER_MISFIRE_GRACE_TIME, SCHEDULER_MAX_INSTANCES, RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)

# Global bot reference (set by main bot)
_bot_instance = None

def set_bot_instance(bot):
    """Set the bot instance for scheduler functions to use"""
    global _bot_instance
    _bot_instance = bot

async def execute_task(user_id, reminder_title, reminder_description):
    """Send a reminder message to a user via DM"""
    if not _bot_instance:
        logger.error("Bot instance not set for scheduler task")
        return
        
    reminder_embed = discord.Embed(
        title="⏰ Reminder",
        description=f"""
# {reminder_title}

### Description:
{reminder_description}
        """,
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    reminder_embed.set_footer(text="Reminder sent by Theseus Bot")
    
    try:
        user = await _bot_instance.fetch_user(user_id)
        
        if user:
            await user.send(embed=reminder_embed)
            logger.info(f"Reminder sent to user: {user.global_name} (ID: {user_id})")
        else:
            logger.warning(f"User not found: {user_id}")
    except Exception as e:
        logger.error(f"Error executing reminder task for user {user_id}: {e}")

def run_reminder_job(user_id: int, title: str, description: str):
    """Synchronous wrapper for APScheduler to execute reminder task"""
    try:
        if not _bot_instance:
            logger.error("Bot instance not set for scheduler job")
            return
            
        future = asyncio.run_coroutine_threadsafe(
            execute_task(user_id, title, description), _bot_instance.loop
        )
        # Wait for completion; raises if the coroutine fails
        future.result()
    except Exception as e:
        # Re-raise so the scheduler marks the job as errored
        raise e

async def initialize_scheduler(bot):
    """Set up the job scheduler with MongoDB persistence"""
    if hasattr(bot, 'scheduler'):
        return
        
    try:
        bot.scheduler = BackgroundScheduler(
            jobstores={
                'default': MongoDBJobStore(
                    client=dbclient, 
                    database='theseusdb', 
                    collection='apscheduler_jobs'
                )
            },
            job_defaults={
                'coalesce': True, 
                'max_instances': SCHEDULER_MAX_INSTANCES,
                'misfire_grace_time': SCHEDULER_MISFIRE_GRACE_TIME
            }
        )
        
        bot.scheduler.start()
        
        # Register job completion handler
        def _cleanup_completed_jobs(event):
            try:
                if hasattr(event, 'exception') and event.exception:
                    logger.warning(f"Job {event.job_id} failed, keeping database record")
                else:
                    db.reminder_ops.remove_rem_doc(event.job_id)
                    logger.debug(f"Cleaned up completed job {event.job_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup job {event.job_id}: {e}")

        bot.scheduler.add_listener(_cleanup_completed_jobs, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # Handle any missed reminders
        await process_missed_reminders(bot)
        
        logger.info("Scheduler initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")

async def process_missed_reminders(bot):
    """Process reminders that were missed while bot was offline"""
    try:
        missed_reminders = db.reminder_ops.get_missed_reminders()
        
        if not missed_reminders:
            logger.debug("No missed reminders found")
            return
            
        active_job_ids = {job.id for job in bot.scheduler.get_jobs()}
        processed = 0
        
        for reminder in missed_reminders:
            job_id = reminder.get("job_id")
            if not job_id or job_id in active_job_ids:
                continue
                
            user_id = reminder.get("userId")
            title = reminder.get("title", "Reminder")
            desc = reminder.get("desc", "")
            
            try:
                # Send with missed indicator
                missed_title = f"⏰ {title}"
                missed_desc = f"{desc}\n\n*This reminder was delayed due to system downtime*"
                
                await execute_task(user_id, missed_title, missed_desc)
                db.reminder_ops.remove_rem_doc(job_id)
                processed += 1
                
                # Rate limiting to avoid overwhelming Discord API
                if processed % 5 == 0:
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                    
            except Exception as e:
                logger.error(f"Failed to process missed reminder {job_id}: {e}")
        
        if processed > 0:
            logger.info(f"Processed {processed} missed reminders")
            
    except Exception as e:
        logger.error(f"Error processing missed reminders: {e}")
    
