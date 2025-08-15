import discord
from discord import app_commands
from discord.ext import commands
import db
import logging
import dotenv
import os

# Set up logger for this cog
logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv("GUILD_ID"))

class CustomCommandsCog(commands.Cog):
    def __init__(self, bot : commands.Bot):
        self.bot = bot
        logger.info("CustomCommandsCog initialized")
        
    @app_commands.command(name="set_custom_command", description="set a custom command that replies with a predefined message")
    @app_commands.describe(command_name="name of the command", message="message that the command will reply with")
    async def set_custom_command(self, interaction: discord.Interaction, command_name:str, message:str):
        existing_names = db.custom_commands_ops.get_existing_command_names()
        
        if command_name in existing_names:
            await interaction.response.send_message(":red_circle: Command with that name already exists", ephemeral=True)
        else:
            db.custom_commands_ops.add_command_doc(command_name, message)
            await interaction.response.send_message(":green_circle: Command added successfully", ephemeral=True)
    
    @app_commands.command(name="remove_custom_command", description="remove an existing custom command")
    @app_commands.describe(command_name="name of the command")
    async def remove_custom_command(self, interaction: discord.Interaction, command_name:str):
        existing_names = db.custom_commands_ops.get_existing_command_names()
        
        if command_name in existing_names:
            db.custom_commands_ops.rem_custom_command(command_name=command_name)
            await interaction.response.send_message(":green_circle: Command successfully removed", ephemeral=True)
        else:
            await interaction.response.send_message(":red_circle: Command doesn't exist", ephemeral=True)

    @app_commands.command(name="list_custom_commands", description="list all existing custom commands")
    async def list_custom_commands(self, interaction: discord.Interaction):
        try:
            message = "Here are all the custom commands:\n"
            customcommands = db.custom_commands_ops.get_all_commands()
            
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

        

async def setup(bot:commands.Bot):
    
    cog = CustomCommandsCog(bot)
    await bot.add_cog(cog)
    
    bot.tree.add_command(cog.set_custom_command, guild=discord.Object(GUILD_ID))
    bot.tree.add_command(cog.remove_custom_command, guild=discord.Object(GUILD_ID))
    bot.tree.add_command(cog.list_custom_commands, guild=discord.Object(GUILD_ID))