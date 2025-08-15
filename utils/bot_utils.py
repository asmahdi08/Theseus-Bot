"""
Bot utilities and initialization functions
"""
import discord
import logging
from discord.ext import commands
from config import COGS, GUILD_ID
from utils.scheduler_utils import set_bot_instance, initialize_scheduler

logger = logging.getLogger(__name__)

def setup_logging():
    """Configure logging for the bot"""
    from config import LOG_LEVEL, LOG_FORMAT, LOG_FILE
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )

def create_bot():
    """Create and configure the bot instance"""
    from config import COMMAND_PREFIX
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
    
    return bot

async def load_cogs(bot):
    """Load all cogs"""
    try:
        for cog in COGS:
            await bot.load_extension(cog)
        
        logger.info("All cogs loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load cog: {e}")

async def sync_commands(bot):
    """Sync slash commands to guild"""
    try:
        synced = await bot.tree.sync(guild=discord.Object(GUILD_ID))
        logger.info(f"Successfully synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

async def initialize_bot_components(bot):
    """Initialize all bot components on ready"""
    logger.info(f"Bot logged in as {bot.user}")
    
    # Set bot instance for scheduler utils
    set_bot_instance(bot)
    
    # Load cogs
    await load_cogs(bot)
    
    # Sync commands
    await sync_commands(bot)
    
    # Initialize scheduler
    await initialize_scheduler(bot)
