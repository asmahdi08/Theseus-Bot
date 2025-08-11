import discord
import asyncio
import dotenv
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

dotenv.load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TzMenuOptions = []
for x in timezones.timezones_list:
    TzMenuOptions.append(discord.SelectOption(label=x,value=x))

@bot.event
async def on_ready():
    print(f"logged in")
    try:
        synced = await bot.tree.sync(guild=discord.Object(GUILD_ID))
        print(f"synced {len(synced)} commands successfully")
    except Exception as e:
        print("Error occured while syncing commands")
        print(e)
        
    # Use a global scheduler instance
    if not hasattr(bot, 'scheduler'):
        bot.scheduler = BackgroundScheduler(
            jobstores={
                'default': MongoDBJobStore(client=db.client, database='theseusdb', collection='apscheduler_jobs')
            },
            job_defaults={'coalesce': True, 'max_instances': 1}
        )
        bot.scheduler.start()
        # Register a listener once to clean up reminder docs when jobs finish
        def _on_job_done(event):
            try:
                # Only remove on success. If event has an exception, keep the doc for visibility.
                if hasattr(event, 'exception') and event.exception:
                    print(f"Job {event.job_id} failed; keeping DB doc.")
                else:
                    db.remove_rem_doc(event.job_id)
                    
                    try:
                        bot.scheduler.remove_job(event.job_id)
                    except Exception as e:
                        print(f"job already removed")
            except Exception as err:
                print(f"Failed to remove reminder doc for job {event.job_id}: {err}")

        bot.scheduler.add_listener(_on_job_done, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
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
    title = "Title of your reminder",
    desc = "description of your reminder",
    date = "date of reminder, eg.20-02-2050",
    time = "time of the day to remind (24hour format)"
    )
async def setreminder(interaction: discord.Interaction , title: str, desc: str, date: str, time: str):
    tz_name = db.get_user_tz(userId=interaction.user.id)
    
    if tz_name == "-1":
        await interaction.response.send_message("You haven't set your timezone yet. run `/settimezone`", ephemeral=True)
        return 0
    
    try:
        tz = pytz.timezone(tz_name)
        run_time = datetime.strptime(f"{date} {time}", "%d-%m-%Y %H:%M")
        run_time = tz.localize(run_time)
    except Exception as e:
        await interaction.response.send_message(f"Invalid date/time: {e}", ephemeral=True)
        return

    # Prevent scheduling in the past
    now_local = datetime.now(tz)
    if run_time <= now_local:
        await interaction.response.send_message("Please choose a future time.", ephemeral=True)
        return

    # Ensure scheduler is ready (should be created in on_ready)
    if not hasattr(bot, 'scheduler'):
        await interaction.response.send_message("Scheduler not ready. Please try again in a moment.", ephemeral=True)
        return

    # Schedule the reminder and get job ID
    job = bot.scheduler.add_job(
        _run_reminder_job,
        'date',
        run_date=run_time,
        timezone=tz,
        args=[interaction.user.id, title, desc],
        misfire_grace_time=60
    )
    job_id = job.id

    # Store reminder in DB with job_id
    db.create_rem_doc(interaction.user.id, title, desc, date, time, job_id)

    await interaction.response.send_message(f"Reminder scheduled for {run_time.strftime('%Y-%m-%d %H:%M %Z')} (Job ID: {job_id})", ephemeral=True)
    print(f"reminder command executed, job id: {job_id}")
    
    
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
    except Exception as e:
        await interaction.response.send_message(f"Failed to list reminders: {e}", ephemeral=True)
        
    print("listing command executed")
    
@bot.tree.command(name="test_embed",description=".", guild=discord.Object(GUILD_ID))
async def test_embed(interaction: discord.Interaction):
    await execute_task(757854639168159854, "Go to school", desc="lorem ipsum dolor sit amet")
    
async def execute_task(userId, title, desc):
    embed = discord.Embed(
        title="Reminder",
        description=f"""
            # {title}
            \n
            ### Reminder Description:\n
            {desc}
        """,
        color=discord.Color.green()
    )
    embed.set_footer(text="this reminder was automatically sent by Theseus Bot")
    
    try:
        user = await bot.fetch_user(userId)
        
        if user:
            await user.send(embed=embed)
            print(f"sent reminder to user: {user.global_name}")
        else:
            print("user not found")
    except Exception as e:
        print(e)

# Synchronous wrapper for APScheduler to wait for the async DM send to complete
def _run_reminder_job(user_id: int, title: str, desc: str):
    try:
        fut = asyncio.run_coroutine_threadsafe(
            execute_task(user_id, title, desc), bot.loop
        )
        # Wait for completion; raises if the coroutine fails
        fut.result()
    except Exception as e:
        # Re-raise so the scheduler marks the job as errored (listener still logs and keeps doc)
        raise e

@bot.tree.command(name="cancelreminder", description="Cancel a scheduled reminder by Job ID", guild=discord.Object(GUILD_ID))
@app_commands.describe(job_id="The Job ID shown when you created the reminder or in /listreminders")
async def cancelreminder(interaction: discord.Interaction, job_id: str):
    if not hasattr(bot, 'scheduler'):
        await interaction.response.send_message("Scheduler not running.", ephemeral=True)
        return
    try:
        bot.scheduler.remove_job(job_id)
        # Remove from DB as well
        db.remove_rem_doc(job_id)
        await interaction.response.send_message(f"Cancelled reminder with Job ID `{job_id}`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to cancel: {e}", ephemeral=True)

@bot.tree.command(name="createpoll", description="Create a poll with multiple options", guild=discord.Object(GUILD_ID))
@app_commands.describe(
    question="The poll question",
    option1="First option",
    option2="Second option", 
    option3="Third option (optional)",
    option4="Fourth option (optional)",
    option5="Fifth option (optional)"
)
async def createpoll(interaction: discord.Interaction, question: str, option1: str, option2: str, 
                    option3: str = None, option4: str = None, option5: str = None):
    
    # Collect non-empty options
    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4) 
    if option5: options.append(option5)
    
    if len(options) < 2:
        await interaction.response.send_message("You need at least 2 options for a poll!", ephemeral=True)
        return
        
    # Create poll embed
    embed = discord.Embed(
        title="📊 " + question,
        description="React to vote!",
        color=discord.Color.blue()
    )
    
    # Number emojis for voting
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    
    # Add options to embed
    poll_text = ""
    for i, option in enumerate(options):
        poll_text += f"{number_emojis[i]} {option}\n"
        
    embed.add_field(name="Options:", value=poll_text, inline=False)
    embed.add_field(name="Votes:", value="No votes yet", inline=False)
    embed.set_footer(text=f"Poll created by {interaction.user.display_name}")
    
    # Send the poll
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # Add reaction buttons
    for i in range(len(options)):
        await message.add_reaction(number_emojis[i])
    
    # Store poll in database
    poll_data = {
        "message_id": message.id,
        "channel_id": interaction.channel.id,
        "creator_id": interaction.user.id,
        "question": question,
        "options": options,
        "votes": {str(i): [] for i in range(len(options))},  # Track user IDs per option
        "created_at": datetime.now(pytz.utc).isoformat()
    }
    
    db.polls_collection.insert_one(poll_data)
    print(f"Poll created: {question}")

@bot.event
async def on_reaction_add(reaction, user):
    # Ignore bot reactions
    if user.bot:
        return
        
    # Check if reaction is on a poll
    poll = db.polls_collection.find_one({"message_id": reaction.message.id})
    if not poll:
        return
        
    # Check if it's a valid poll emoji
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    if str(reaction.emoji) not in number_emojis[:len(poll["options"])]:
        return
        
    option_index = str(number_emojis.index(str(reaction.emoji)))
    
    # Remove user from all other options (single vote per user)
    for i in range(len(poll["options"])):
        if str(i) != option_index and user.id in poll["votes"].get(str(i), []):
            db.polls_collection.update_one(
                {"message_id": reaction.message.id},
                {"$pull": {f"votes.{i}": user.id}}
            )
            # Remove their reactions from other options
            for other_reaction in reaction.message.reactions:
                if str(other_reaction.emoji) == number_emojis[i] and other_reaction.emoji != reaction.emoji:
                    await other_reaction.remove(user)
    
    # Add user to voted option (if not already there)
    if user.id not in poll["votes"].get(option_index, []):
        db.polls_collection.update_one(
            {"message_id": reaction.message.id},
            {"$addToSet": {f"votes.{option_index}": user.id}}
        )
    
    # Update the embed with vote counts
    await update_poll_embed(reaction.message)

@bot.event 
async def on_reaction_remove(reaction, user):
    # Ignore bot reactions
    if user.bot:
        return
        
    # Check if reaction is on a poll
    poll = db.polls_collection.find_one({"message_id": reaction.message.id})
    if not poll:
        return
        
    # Check if it's a valid poll emoji
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    if str(reaction.emoji) not in number_emojis[:len(poll["options"])]:
        return
        
    option_index = str(number_emojis.index(str(reaction.emoji)))
    
    # Remove user from this option
    db.polls_collection.update_one(
        {"message_id": reaction.message.id},
        {"$pull": {f"votes.{option_index}": user.id}}
    )
    
    # Update the embed with vote counts
    await update_poll_embed(reaction.message)

async def update_poll_embed(message):
    """Update poll embed with current vote counts"""
    poll = db.polls_collection.find_one({"message_id": message.id})
    if not poll:
        return
        
    # Create updated embed
    embed = discord.Embed(
        title="📊 " + poll["question"],
        description="React to vote!",
        color=discord.Color.blue()
    )
    
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    
    # Add options to embed
    poll_text = ""
    votes_text = ""
    total_votes = 0
    
    for i, option in enumerate(poll["options"]):
        vote_count = len(poll["votes"].get(str(i), []))
        total_votes += vote_count
        poll_text += f"{number_emojis[i]} {option}\n"
        
    # Create vote count display with bars
    if total_votes > 0:
        for i, option in enumerate(poll["options"]):
            vote_count = len(poll["votes"].get(str(i), []))
            percentage = (vote_count / total_votes) * 100 if total_votes > 0 else 0
            
            # Create visual bar (max 10 chars)
            bar_length = int(percentage / 10)
            bar = "█" * bar_length + "░" * (10 - bar_length)
            votes_text += f"{number_emojis[i]} **{vote_count}** votes ({percentage:.1f}%)\n`{bar}`\n"
    else:
        votes_text = "No votes yet"
        
    embed.add_field(name="Options:", value=poll_text, inline=False)
    embed.add_field(name=f"Votes ({total_votes} total):", value=votes_text, inline=False)
    
    creator = await bot.fetch_user(poll["creator_id"])
    embed.set_footer(text=f"Poll created by {creator.display_name if creator else 'Unknown'}")
    
    try:
        await message.edit(embed=embed)
    except Exception as e:
        print(f"Failed to update poll embed: {e}")

@bot.tree.command(name="endpoll", description="End a poll and show final results", guild=discord.Object(GUILD_ID))
@app_commands.describe(message_id="The message ID of the poll to end")
async def endpoll(interaction: discord.Interaction, message_id: str):
    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.response.send_message("Invalid message ID!", ephemeral=True)
        return
        
    poll = db.polls_collection.find_one({"message_id": msg_id})
    if not poll:
        await interaction.response.send_message("Poll not found!", ephemeral=True)
        return
        
    # Check if user is poll creator or has manage messages permission
    if (poll["creator_id"] != interaction.user.id and 
        not interaction.user.guild_permissions.manage_messages):
        await interaction.response.send_message("You can only end polls you created!", ephemeral=True)
        return
        
    # Get the poll message and clear reactions
    try:
        channel = bot.get_channel(poll["channel_id"])
        message = await channel.fetch_message(msg_id)
        await message.clear_reactions()
        
        # Update embed to show final results
        embed = discord.Embed(
            title="📊 " + poll["question"] + " (ENDED)",
            description="Final Results:",
            color=discord.Color.red()
        )
        
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        
        # Calculate final results
        total_votes = sum(len(poll["votes"].get(str(i), [])) for i in range(len(poll["options"])))
        
        results_text = ""
        if total_votes > 0:
            # Sort options by vote count
            sorted_options = []
            for i, option in enumerate(poll["options"]):
                vote_count = len(poll["votes"].get(str(i), []))
                sorted_options.append((vote_count, i, option))
            sorted_options.sort(reverse=True)
            
            for vote_count, i, option in sorted_options:
                percentage = (vote_count / total_votes) * 100 if total_votes > 0 else 0
                bar_length = int(percentage / 10)
                bar = "█" * bar_length + "░" * (10 - bar_length)
                
                winner_emoji = "🏆 " if vote_count == sorted_options[0][0] and vote_count > 0 else ""
                results_text += f"{winner_emoji}{number_emojis[i]} **{option}**\n"
                results_text += f"**{vote_count}** votes ({percentage:.1f}%)\n"
                results_text += f"`{bar}`\n\n"
        else:
            results_text = "No votes were cast."
            
        embed.add_field(name=f"Final Results ({total_votes} total votes):", value=results_text, inline=False)
        
        creator = await bot.fetch_user(poll["creator_id"])
        embed.set_footer(text=f"Poll ended by {interaction.user.display_name}")
        
        await message.edit(embed=embed)
        
        # Remove poll from database
        db.polls_collection.delete_one({"message_id": msg_id})
        
        await interaction.response.send_message("Poll ended successfully!", ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"Error ending poll: {e}", ephemeral=True)
    
    
    
    








bot.run(BOT_TOKEN)

# Synchronous wrapper for APScheduler to wait for the async DM send to complete
def _run_reminder_job(user_id: int, title: str, desc: str):
    try:
        fut = asyncio.run_coroutine_threadsafe(
            execute_task(user_id, title, desc), bot.loop
        )
        # Wait for completion; raises if the coroutine fails
        fut.result()
    except Exception as e:
        # Re-raise so the scheduler marks the job as errored (listener still cleans up)
        raise e
    
    
    
    
    








bot.run(BOT_TOKEN)
