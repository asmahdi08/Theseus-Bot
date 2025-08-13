import discord
import asyncio
import logging
import os
from discord import app_commands
from discord.ext import commands
import utils.utils as utils
from db import db
from utils import timezones
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from datetime import datetime, timedelta
import pytz
import dotenv

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

# Suppress PyNaCl warning since we don't use voice features
logging.getLogger('discord.client').setLevel(logging.ERROR)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

TzMenuOptions = []
for x in timezones.timezones_list:
    TzMenuOptions.append(discord.SelectOption(label=x,value=x))

@bot.event
async def on_ready():
    """Initialize bot components when ready"""
    logger.info(f"Bot logged in as {bot.user}")
    
    try:
        synced = await bot.tree.sync(guild=discord.Object(GUILD_ID))
        logger.info(f"Successfully synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        
    # Initialize scheduler once
    await _initialize_scheduler()
    
async def _initialize_scheduler():
    """Set up the job scheduler with MongoDB persistence"""
    if hasattr(bot, 'scheduler'):
        return
        
    try:
        bot.scheduler = BackgroundScheduler(
            jobstores={
                'default': MongoDBJobStore(
                    client=db.client, 
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
                    db.remove_rem_doc(event.job_id)
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
        missed_reminders = db.get_missed_reminders()
        
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
                db.remove_rem_doc(job_id)
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
        db.create_tz_doc(interaction.user.id,chosen)
        
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
    user_timezone = db.get_user_tz(userId=interaction.user.id)
    
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
        _run_reminder_job,
        'date',
        run_date=scheduled_time,
        timezone=user_tz,
        args=[interaction.user.id, title, description],
        misfire_grace_time=60
    )
    job_id = reminder_job.id

    # Store reminder in DB with job_id
    db.create_rem_doc(interaction.user.id, title, description, date, time, job_id)

    await interaction.response.send_message(f"Reminder scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M %Z')} (Job ID: {job_id})", ephemeral=True)
    logger.info(f"Reminder scheduled for user {interaction.user.id}, job ID: {job_id}")
    
    
@bot.tree.command(name="listreminders", description="List all of your reminders currently active", guild=discord.Object(GUILD_ID))
async def listreminders(interaction: discord.Interaction):
    try:
        # Fetch user's reminders
        docs = list(db.reminder_collection.find({"userId": interaction.user.id}))
        tz_name = db.get_user_tz(userId=interaction.user.id)
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
        db.remove_rem_doc(job_id)
        await interaction.response.send_message(f"Cancelled reminder with Job ID `{job_id}`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to cancel: {e}", ephemeral=True)

# Poll system
@bot.tree.command(name="createpoll", description="Create a poll with multiple options", guild=discord.Object(GUILD_ID))
@app_commands.describe(
    question="The poll question",
    options="Poll options separated by commas (e.g., Option1, Option2, Option3)"
)
async def createpoll(interaction: discord.Interaction, question: str, options: str):
    try:
        # Parse options
        option_list = [opt.strip() for opt in options.split(',') if opt.strip()]
        
        if len(option_list) < 2:
            await interaction.response.send_message("Please provide at least 2 options separated by commas.", ephemeral=True)
            return
        
        if len(option_list) > 10:
            await interaction.response.send_message("Maximum 10 options allowed.", ephemeral=True)
            return
        
        # Create poll embed
        embed = discord.Embed(
            title=f"📊 {question}",
            description="Click the buttons below to vote!",
            color=discord.Color.blue()
        )
        
        # Add options to embed
        for i, option in enumerate(option_list):
            embed.add_field(
                name=f"{i+1}️⃣ {option}",
                value="0 votes",
                inline=False
            )
        
        embed.set_footer(text=f"Poll created using Theseus Bot")
        
        # Create buttons for voting
        view = PollView(option_list, question, interaction.user.id)
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # Get the message ID after sending
        poll_msg = await interaction.original_response()
        poll_msg_id = poll_msg.id
        
        # Store poll in database
        poll_data = {
            "question": question,
            "options": option_list,
            "votes": {str(i): [] for i in range(len(option_list))},  # Store user IDs who voted for each option
            "poll_msg_id": str(poll_msg_id),
            "creator_id": interaction.user.id,
            "channel_id": interaction.channel.id,
            "created_at": datetime.now().isoformat()
        }
        
        result = db.polls_collection.insert_one(poll_data)
        view.poll_id = str(result.inserted_id)
        
    except Exception as e:
        await interaction.response.send_message(f"Error creating poll: {e}", ephemeral=True)

class PollView(discord.ui.View):
    def __init__(self, options, question, creator_id):
        super().__init__(timeout=None)  # No timeout for polls
        self.options = options
        self.question = question
        self.creator_id = creator_id
        self.poll_id = None
        
        # Create buttons for each option (max 10)
        for i, option in enumerate(options[:10]):
            button = PollButton(label=f"{i+1}. {option[:50]}", option_index=i, emoji=f"{i+1}️⃣")
            self.add_item(button)
        
        # Add results button
        results_button = discord.ui.Button(
            label="Show Results",
            style=discord.ButtonStyle.secondary,
            emoji="📊"
        )
        results_button.callback = self.show_results
        self.add_item(results_button)

    async def show_results(self, interaction: discord.Interaction):
        if not self.poll_id:
            await interaction.response.send_message("Poll ID not found.", ephemeral=True)
            return
        
        try:
            from bson import ObjectId
            poll_data = db.polls_collection.find_one({"_id": ObjectId(self.poll_id)})
            
            if not poll_data:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return
            
            # Calculate results
            embed = discord.Embed(
                title=f"📊 {poll_data['question']} - Results",
                color=discord.Color.green()
            )
            
            total_votes = sum(len(voters) for voters in poll_data['votes'].values())
            
            for i, option in enumerate(poll_data['options']):
                vote_count = len(poll_data['votes'].get(str(i), []))
                percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
                
                bar = "█" * int(percentage // 5) + "░" * (20 - int(percentage // 5))
                
                embed.add_field(
                    name=f"{i+1}️⃣ {option}",
                    value=f"{bar} {vote_count} votes ({percentage:.1f}%)",
                    inline=False
                )
            
            embed.set_footer(text=f"Total votes: {total_votes}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            
        except Exception as e:
            await interaction.response.send_message(f"Error showing results: {e}", ephemeral=True)

class PollButton(discord.ui.Button):
    def __init__(self, label, option_index, emoji):
        super().__init__(label=label, style=discord.ButtonStyle.primary, emoji=emoji)
        self.option_index = option_index
    
    async def callback(self, interaction: discord.Interaction):
        try:
            poll_view = self.view
            if not poll_view.poll_id:
                await interaction.response.send_message("Poll ID not found.", ephemeral=True)
                return
            
            from bson import ObjectId
            user_id = interaction.user.id
            
            # Get current poll data
            poll_data = db.polls_collection.find_one({"_id": ObjectId(poll_view.poll_id)})
            
            if not poll_data:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return
            
            # Check if user already voted for this option
            current_votes = poll_data['votes'].get(str(self.option_index), [])
            
            if user_id in current_votes:
                await interaction.response.send_message("You have already voted for this option!", ephemeral=True)
                return
            
            # Remove user's vote from other options (allow vote changing)
            for option_idx in poll_data['votes']:
                if user_id in poll_data['votes'][option_idx]:
                    poll_data['votes'][option_idx].remove(user_id)
            
            # Add vote to selected option
            if str(self.option_index) not in poll_data['votes']:
                poll_data['votes'][str(self.option_index)] = []
            poll_data['votes'][str(self.option_index)].append(user_id)
            
            # Update database
            db.polls_collection.update_one(
                {"_id": ObjectId(poll_view.poll_id)},
                {"$set": {"votes": poll_data['votes']}}
            )
            
            # Update the embed
            embed = discord.Embed(
                title=f"📊 {poll_data['question']}",
                description="Click the buttons below to vote!",
                color=discord.Color.blue()
            )
            
            for i, option in enumerate(poll_data['options']):
                vote_count = len(poll_data['votes'].get(str(i), []))
                embed.add_field(
                    name=f"{i+1}️⃣ {option}",
                    value=f"{vote_count} votes",
                    inline=False
                )
            
            embed.set_footer(text=f"Poll created by {interaction.guild.get_member(poll_data['creator_id']).display_name if interaction.guild.get_member(poll_data['creator_id']) else 'Unknown'}")
            
            await interaction.response.edit_message(embed=embed, view=poll_view)
            
        except Exception as e:
            await interaction.response.send_message(f"Error voting: {e}", ephemeral=True)

@bot.tree.command(name="listpolls", description="lists all active polls", guild=discord.Object(GUILD_ID))
async def listpolls(interaction: discord.Interaction):
    try:
        message = "Here are all the active polls:\n"
        stored_polls = db.get_all_polls()
        
        poll_count = 0
        for poll in stored_polls:
            poll_object_id = str(poll["_id"])  # MongoDB ObjectId
            poll_msg_id = poll.get("poll_msg_id", "N/A")  # Discord message ID
            poll_title = poll["question"]
            
            # Count total votes
            total_votes = sum(len(voters) for voters in poll.get("votes", {}).values())
            
            message += f"\n📊 **{poll_title}**\n"
            message += f"   Poll Object ID: `{poll_object_id}`\n"
            message += f"   Message ID: `{poll_msg_id}`\n"
            message += f"   Total Votes: {total_votes}\n"
            poll_count += 1
        
        if poll_count == 0:
            message = "No active polls found."
            
        await interaction.response.send_message(message, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"Error listing polls: {e}", ephemeral=True)


@bot.tree.command(name="closepoll", description="close an already created poll", guild=discord.Object(GUILD_ID))
@app_commands.describe(poll_id="id of poll to close")
async def closepoll(interaction: discord.Interaction, poll_id: str):
    try:
        # Get poll data before deleting
        poll_data = db.get_poll_by_id(poll_id)
        if not poll_data:
            await interaction.response.send_message(f"Poll `{poll_id}` not found.", ephemeral=True)
            return
        
        # Delete from database
        success = db.rem_poll_doc(poll_id)
        if not success:
            await interaction.response.send_message(f"Failed to delete poll `{poll_id}` from database.", ephemeral=True)
            return
        
        # Try to delete the Discord message
        try:
            channel = interaction.guild.get_channel(poll_data['channel_id'])
            if channel:
                poll_message = await channel.fetch_message(int(poll_data['poll_msg_id']))
                await poll_message.delete()
                await interaction.response.send_message(f"Poll '{poll_data['question']}' has been closed and removed.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Poll '{poll_data['question']}' removed from database but couldn't find the channel.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message(f"Poll '{poll_data['question']}' removed from database but message was already deleted.", ephemeral=True)
        except Exception as msg_error:
            await interaction.response.send_message(f"Poll '{poll_data['question']}' removed from database but couldn't delete message: {msg_error}", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error closing poll {poll_id}: {e}")
        await interaction.response.send_message(f"Error closing poll: {e}", ephemeral=True)

@bot.tree.command(name="set_custom_command", description="set a custom command that replies with a predefined message", guild=discord.Object(GUILD_ID))
@app_commands.describe(command_name="name of the command", message="message that the command will reply with")
async def set_custom_command(interaction: discord.Interaction, command_name:str, message:str):
    existing_names = db.get_existing_command_names()
    
    if command_name in existing_names:
        await interaction.response.send_message(":red_circle: Command with that name already exists", ephemeral=True)
    else:
        db.add_command_doc(command_name, message)
        await interaction.response.send_message(":green_circle: Command added successfully", ephemeral=True)
   
   
@bot.tree.command(name="remove_custom_command", description="remove an existing custom command", guild=discord.Object(GUILD_ID))
@app_commands.describe(command_name="name of the command")
async def remove_custom_command(interaction: discord.Interaction, command_name:str):
    existing_names = db.get_existing_command_names()
    
    if command_name in existing_names:
        db.rem_custom_command(command_name=command_name)
        await interaction.response.send_message(":green_circle: Command successfully removed", ephemeral=True)
    else:
        await interaction.response.send_message(":red_circle: Command doesn't exist", ephemeral=True)

@bot.tree.command(name="list_custom_commands", description="list all existing custom commands", guild=discord.Object(GUILD_ID))
async def list_custom_commands(interaction: discord.Interaction):
    try:
        message = "Here are all the custom commands:\n"
        customcommands = db.get_all_commands()
        
        cmd_count = 0
        for cmd in customcommands:
            command = cmd["command_name"]
            
            message += f"\n- 💻 **{command}**\n"
            cmd_count += 1
        
        if cmd_count == 0:
            message = "No custom commands were found."
            
        await interaction.response.send_message(message, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"Error listing custom commands: {e}", ephemeral=True)

        
      
@bot.event
async def on_message(message: discord.Message):
    if message.content.startswith("!"):
        main_command = message.content.removeprefix("!")
        existing_names = db.get_existing_command_names()
        
        if main_command in existing_names:
            reply = db.get_reply(main_command)
            await message.channel.send(reply, reference=message)

bot.run(BOT_TOKEN)
