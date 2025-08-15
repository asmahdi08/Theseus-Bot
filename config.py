"""
Configuration settings for Theseus Bot
"""
import os
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
COMMAND_PREFIX = "!"

# Scheduler Configuration
SCHEDULER_MISFIRE_GRACE_TIME = 300  # 5 minutes
SCHEDULER_MAX_INSTANCES = 1
RATE_LIMIT_DELAY = 1  # seconds between batch operations

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'bot.log'

# Cogs to load
COGS = [
    "cogs.polls",
    "cogs.reminders",
    "cogs.custom_commands"
]
