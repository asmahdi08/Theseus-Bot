import asyncio
import discord
import logging
from datetime import datetime

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
    
