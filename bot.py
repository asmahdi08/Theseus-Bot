import discord
import db
from utils import timezones
from utils.bot_utils import setup_logging, create_bot, initialize_bot_components
from config import BOT_TOKEN, GUILD_ID

# Configure logging
setup_logging()

# Create bot instance
bot = create_bot()

# Timezone selection options
TzMenuOptions = []
for x in timezones.timezones_list:
    TzMenuOptions.append(discord.SelectOption(label=x, value=x))

@bot.event
async def on_ready():
    """Initialize bot components when ready"""
    await initialize_bot_components(bot)

@bot.tree.command(name="settimezone", description="Set a timezone for your reminders", guild=discord.Object(GUILD_ID))
async def settimezone(interaction: discord.Interaction):
    dropdownMenu = discord.ui.Select(options=TzMenuOptions)
    
    async def buttonCallback(callbackinteraction: discord.Interaction):
        chosen = callbackinteraction.data['values'][0]
        await callbackinteraction.response.send_message("Timezone added!")
        db.user_ops.create_tz_doc(interaction.user.id, chosen)
        
    dropdownMenu.callback = buttonCallback
    
    view = discord.ui.View()
    view.add_item(dropdownMenu)
    await interaction.response.send_message("Pick your timezone from below", view=view, ephemeral=True)

@bot.event
async def on_message(message: discord.Message):
    if message.content.startswith("!"):
        main_command = message.content.removeprefix("!")
        existing_names = db.custom_commands_ops.get_existing_command_names()
        
        if main_command in existing_names:
            reply = db.custom_commands_ops.get_reply(main_command)
            await message.channel.send(reply, reference=message)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
