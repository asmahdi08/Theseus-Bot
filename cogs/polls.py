import discord
from discord.ext import commands
from discord import app_commands
from ui.PollButton import PollButton
from ui.PollView import PollView
from datetime import datetime
import db
import os
import logging

# Set up logger for this cog
logger = logging.getLogger(__name__)

# Get GUILD_ID from environment
GUILD_ID = int(os.getenv("GUILD_ID"))

class PollsCog(commands.Cog):
    def __init__(self, bot : commands.Bot):
        self.bot = bot
        logger.info("PollsCog initialized")
        
    
        
    # Poll system
    @app_commands.command(name="createpoll", description="Create a poll with multiple options")
    @app_commands.describe(
        question="The poll question",
        options="Poll options separated by commas (e.g., Option1, Option2, Option3)"
    )
    async def createpoll(self, interaction: discord.Interaction, question: str, options: str):
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
            
            result = db.dbmanager.polls_collection.insert_one(poll_data)
            view.poll_id = str(result.inserted_id)
            
            logger.info(f"Poll created by {interaction.user.global_name} (ID: {interaction.user.id}): '{question}'")
            
        except Exception as e:
            logger.error(f"Error creating poll for user {interaction.user.id}: {e}")
            await interaction.response.send_message(f"Error creating poll: {e}", ephemeral=True)
            
    @app_commands.command(name="listpolls", description="lists all active polls")
    async def listpolls(self, interaction: discord.Interaction):
        try:
            message = "Here are all the active polls:\n"
            stored_polls = db.polls_ops.get_all_polls()
            
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
            logger.info(f"User {interaction.user.global_name} listed polls ({poll_count} found)")
            
        except Exception as e:
            logger.error(f"Error listing polls for user {interaction.user.id}: {e}")
            await interaction.response.send_message(f"Error listing polls: {e}", ephemeral=True)

    @app_commands.command(name="closepoll", description="close an already created poll")
    @app_commands.describe(poll_id="id of poll to close")
    async def closepoll(self, interaction: discord.Interaction, poll_id: str):
        try:
            # Get poll data before deleting
            poll_data = db.polls_ops.get_poll_by_id(poll_id)
            if not poll_data:
                await interaction.response.send_message(f"Poll `{poll_id}` not found.", ephemeral=True)
                return
            
            # Delete from database
            success = db.polls_ops.rem_poll_doc(poll_id)
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


async def setup(bot:commands.Bot):
    
    cog = PollsCog(bot)
    await bot.add_cog(cog)
    
    bot.tree.add_command(cog.createpoll, guild=discord.Object(GUILD_ID))
    bot.tree.add_command(cog.listpolls, guild=discord.Object(GUILD_ID))
    bot.tree.add_command(cog.closepoll, guild= discord.Object(GUILD_ID))
