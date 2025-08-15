import discord
from discord import app_commands
from discord.ext import commands
import db
import logging
import dotenv
import os
import pytz
from datetime import datetime
from utils.scheduler_utils import run_reminder_job  # Import from utils

# Set up logger for this cog
logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv("GUILD_ID"))

class RemindersCog(commands.Cog):
    def __init__(self, bot : commands.Bot):
        self.bot = bot
        logger.info("RemindersCog initialized")
        
    @app_commands.command(name="setreminder", description="Set a reminder")
    @app_commands.describe(
        title="Title of your reminder",
        description="Description of your reminder", 
        date="Date of reminder (format: DD-MM-YYYY)",
        time="Time of the day to remind (24-hour format HH:MM)"
    )
    async def setreminder(self,interaction: discord.Interaction, title: str, description: str, date: str, time: str):
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
        if not hasattr(self.bot, 'scheduler'):
            await interaction.response.send_message("Scheduler not ready. Please try again in a moment.", ephemeral=True)
            return

        # Schedule the reminder and get job ID
        reminder_job = self.bot.scheduler.add_job(
            run_reminder_job,  # Use the imported function from utils
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

        
        
async def setup(bot:commands.Bot):
    
    cog = RemindersCog(bot)
    await bot.add_cog(cog)