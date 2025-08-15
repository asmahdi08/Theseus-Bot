import discord
import asyncio
import logging
import os
from discord import app_commands
from discord.ext import commands
import utils.utils as utils
import db
from db.dbmanager import client as dbclient
from utils import timezones
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from datetime import datetime, timedelta
import pytz
import dotenv
from ui.PollView import PollView
from utils.scheduler_utils import run_reminder_job, set_bot_instance

# Load environment variables
dotenv.load_dotenv()

# Configuration constants
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
COMMAND_PREFIX = "!"

# Scheduler configuration
SCHEDULER_MISFIRE_GRACE_TIME = 300  # 5 minutes
SCHEDULER_MAX_INSTANCES = 1
RATE_LIMIT_DELAY = 1  # seconds between batch operations

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
COMMAND_PREFIX = "!"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
cogs = [
    "cogs.polls",
    "cogs.custom_commands"
]

TzMenuOptions = []
for x in timezones.timezones_list:
    TzMenuOptions.append(discord.SelectOption(label=x,value=x))

@bot.event
async def on_ready():
    """Initialize bot components when ready"""
    logger.info(f"Bot logged in as {bot.user}")
    
    # Set bot instance for scheduler utils
    set_bot_instance(bot)
    
    # Load cogs
    await load_cogs()
    
    try:
        synced = await bot.tree.sync(guild=discord.Object(GUILD_ID))
        logger.info(f"Successfully synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        
    # Initialize scheduler once
    await _initialize_scheduler()

async def load_cogs():
    """Load all cogs"""
    try:
        for cog in cogs:
            await bot.load_extension(cog)
        
        logger.info("All cogs loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load cog: {e}")
    
async def _initialize_scheduler():
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
        await _process_missed_reminders()
        
        logger.info("Scheduler initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")

        
async def _process_missed_reminders():
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

# Timezone selection options
TzMenuOptions = []
for x in timezones.timezones_list:
    TzMenuOptions.append(discord.SelectOption(label=x,value=x))

@bot.tree.command(name="settimezone", description="Set a timezone for your reminders", guild=discord.Object(GUILD_ID))
async def settimezone(interaction: discord.Interaction):
    dropdownMenu = discord.ui.Select(options=TzMenuOptions)
    
    async def buttonCallback(callbackinteraction: discord.Interaction):
        chosen = callbackinteraction.data['values'][0]
        await callbackinteraction.response.send_message("Timezone added!")
        db.user_ops.create_tz_doc(interaction.user.id,chosen)
        
    dropdownMenu.callback = buttonCallback
    
    view = discord.ui.View()
    view.add_item(dropdownMenu)
    await interaction.response.send_message("Pick your timezone from below", view=view, ephemeral=True)
    
    
@bot.tree.command(name="setreminder", description="Set a reminder", guild=discord.Object(GUILD_ID))
@app_commands.describe(
    title="Title of your reminder",
    description="Description of your reminder", 
    date="Date of reminder (format: DD-MM-YYYY)",
    time="Time of the day to remind (24-hour format HH:MM)"
)
async def setreminder(interaction: discord.Interaction, title: str, description: str, date: str, time: str):
    user_timezone = db.user_ops.get_user_tz(userId=interaction.user.id)
    
    if user_timezone == "-1":
        await interaction.response.send_message("You haven't set your timezone yet. Run `/settimezone` first.", ephemeral=True)
        return
    
    try:
        user_tz = pytz.timezone(user_timezone)
        scheduled_time = datetime.strptime(f"{date} {time}", "%d-%m-%Y %H:%M")
        scheduled_time = user_tz.localize(scheduled_time)
    except Exception as e:
        await interaction.response.send_message(f"Invalid date/time format: {e}", ephemeral=True)
        return

    # Prevent scheduling in the past
    current_time = datetime.now(user_tz)
    if scheduled_time <= current_time:
        await interaction.response.send_message("Please choose a future time.", ephemeral=True)
        return

    # Ensure scheduler is ready
    if not hasattr(bot, 'scheduler'):
        await interaction.response.send_message("Scheduler not ready. Please try again in a moment.", ephemeral=True)
        return

    # Schedule the reminder and get job ID
    reminder_job = bot.scheduler.add_job(
        run_reminder_job,  # Use utils function
        'date',
        run_date=scheduled_time,
        timezone=user_tz,
        args=[interaction.user.id, title, description],  # No bot object
        misfire_grace_time=60
    )
    job_id = reminder_job.id

    # Store reminder in DB with job_id
    db.reminder_ops.create_rem_doc(interaction.user.id, title, description, date, time, job_id)

    await interaction.response.send_message(f"Reminder scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M %Z')} (Job ID: {job_id})", ephemeral=True)
    logger.info(f"Reminder scheduled for user {interaction.user.id}, job ID: {job_id}")
    
    
@bot.tree.command(name="listreminders", description="List all of your reminders currently active", guild=discord.Object(GUILD_ID))
async def listreminders(interaction: discord.Interaction):
    try:
        # Fetch user's reminders
        docs = list(db.dbmanager.reminder_collection.find({"userId": interaction.user.id}))
        tz_name = db.user_ops.get_user_tz(userId=interaction.user.id)
        tz = pytz.timezone(tz_name) if tz_name != "-1" else pytz.utc

        if not docs:
            await interaction.response.send_message("You have no active reminders.", ephemeral=True)
            return

        lines = []
        for d in docs:
            utc_ts = d.get("time")
            job_id = d.get("job_id")
            title = d.get("title", "(no title)")
            # Convert UTC unix to user's local time
            local_dt = datetime.fromtimestamp(utc_ts, tz=pytz.utc).astimezone(tz)
            lines.append(f"• [{title}] at {local_dt.strftime('%Y-%m-%d %H:%M %Z')} (Job ID: `{job_id}`)")

        msg = "Your active reminders:\n" + "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)
        logger.debug(f"Listed reminders for user {interaction.user.id}")
    except Exception as e:
        logger.error(f"Failed to list reminders for user {interaction.user.id}: {e}")
        await interaction.response.send_message(f"Failed to list reminders: {e}", ephemeral=True)
        
async def execute_task(user_id, reminder_title, reminder_description):
    """Send a reminder message to a user via DM"""
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
        user = await bot.fetch_user(user_id)
        
        if user:
            await user.send(embed=reminder_embed)
            logger.info(f"Reminder sent to user: {user.global_name} (ID: {user_id})")
        else:
            logger.warning(f"User not found: {user_id}")
    except Exception as e:
        logger.error(f"Error executing reminder task for user {user_id}: {e}")

# Synchronous wrapper for APScheduler to wait for the async DM send to complete
def _run_reminder_job(user_id: int, title: str, description: str):
    """Synchronous wrapper for APScheduler to execute reminder task"""
    try:
        future = asyncio.run_coroutine_threadsafe(
            execute_task(user_id, title, description), bot.loop
        )
        # Wait for completion; raises if the coroutine fails
        future.result()
    except Exception as e:
        # Re-raise so the scheduler marks the job as errored
        raise e

@bot.tree.command(name="cancelreminder", description="Cancel a scheduled reminder by Job ID", guild=discord.Object(GUILD_ID))
@app_commands.describe(job_id="The Job ID shown when you created the reminder or in /listreminders")
async def cancelreminder(interaction: discord.Interaction, job_id: str):
    if not hasattr(bot, 'scheduler'):
        await interaction.response.send_message("Scheduler not running.", ephemeral=True)
        return
    try:
        bot.scheduler.remove_job(job_id)
        db.reminder_ops.remove_rem_doc(job_id)
        await interaction.response.send_message(f"Cancelled reminder with Job ID `{job_id}`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to cancel: {e}", ephemeral=True)
        
@bot.event
async def on_message(message: discord.Message):
    if message.content.startswith("!"):
        main_command = message.content.removeprefix("!")
        existing_names = db.custom_commands_ops.get_existing_command_names()
        
        if main_command in existing_names:
            reply = db.custom_commands_ops.get_reply(main_command)
            await message.channel.send(reply, reference=message)

bot.run(BOT_TOKEN)
