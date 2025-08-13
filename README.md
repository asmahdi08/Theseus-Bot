# Theseus Bot

A powerful Discord bot built with Python that provides reminder scheduling, interactive polls, and custom command management with persistent data storage.

## Features

### 🕒 Smart Reminders
- **Timezone Support**: Set your local timezone for accurate reminders
- **Persistent Scheduling**: Reminders survive bot restarts
- **Missed Reminder Recovery**: Automatically handles reminders missed during downtime
- **Flexible Date/Time Input**: Easy-to-use date and time format

### 📊 Interactive Polls
- **Real-time Voting**: Click buttons to vote on poll options
- **Live Results**: See vote counts update instantly
- **Poll Management**: Create and close polls with detailed results
- **Visual Feedback**: Clean embed design with progress indicators

### ⚙️ Custom Commands
- **Dynamic Commands**: Create custom bot responses
- **Easy Management**: Add and remove commands on-the-fly
- **Prefix Support**: Use `!` prefix for quick command access

## Installation

### Prerequisites
- Python 3.8 or higher
- MongoDB database
- Discord Bot Token

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/asmahdi08/Theseus-Bot.git
   cd Theseus-Bot
   ```

2. **Install dependencies**
   ```bash
   pip install discord.py pymongo apscheduler pytz python-dotenv
   ```

3. **Configure environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   GUILD_ID=your_discord_server_id_here
   MONGODB_URI=your_mongodb_connection_string_here
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## Commands

### Timezone Management
- `/settimezone` - Set your timezone for accurate reminders

### Reminders
- `/setreminder` - Schedule a new reminder
  - **title**: Title of your reminder
  - **description**: Detailed description
  - **date**: Date in DD-MM-YYYY format
  - **time**: Time in HH:MM (24-hour format)
- `/listreminders` - View all your active reminders

### Polls
- `/createpoll` - Create an interactive poll
  - **question**: The poll question
  - **option1-option4**: Up to 4 poll options
- `/closepoll` - Close a poll and show final results

### Custom Commands
- `/set_custom_command` - Create a custom command
- `/remove_custom_command` - Remove a custom command
- `/list_custom_commands` - View all custom commands

## Architecture

### Core Components

- **Scheduler**: APScheduler with MongoDB persistence for reliable job management
- **Database**: MongoDB for storing reminders, polls, user settings, and custom commands
- **UI Components**: Discord.py views and buttons for interactive elements
- **Timezone Handling**: pytz integration for accurate time conversions

### File Structure

```
Theseus-Bot/
├── bot.py              # Main bot logic and commands
├── db/
│   ├── db.py          # Database operations
│   └── dbtest.py      # Database testing utilities
├── utils/
│   ├── utils.py       # Utility functions
│   └── timezones.py   # Timezone definitions
├── bot.log            # Application logs
└── .env               # Environment variables
```

## Technical Features

### Reliability
- **Job Persistence**: Reminders survive bot restarts using MongoDB job storage
- **Error Recovery**: Comprehensive error handling and logging
- **Rate Limiting**: Built-in protections against API rate limits
- **Graceful Degradation**: Handles missing data and edge cases

### Performance
- **Efficient Scheduling**: Background scheduler with optimized job execution
- **Database Indexing**: Optimized MongoDB queries with proper indexing
- **Memory Management**: Clean resource handling and job cleanup

### Security
- **Input Validation**: Comprehensive validation for all user inputs
- **Permission Checks**: Proper Discord permission handling
- **Error Logging**: Detailed logging without exposing sensitive data

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Discord bot token | Yes |
| `GUILD_ID` | Discord server ID | Yes |
| `MONGO_CONN_STR` | MongoDB connection string | Yes |

### Customization

The bot can be customized by modifying:
- **Timezone list**: Edit `utils/timezones.py` to add/remove supported timezones
- **Logging level**: Adjust logging configuration in `bot.py`
- **Rate limits**: Modify constants for API rate limiting
- **Poll options**: Change maximum poll options in poll creation logic

## Contributing

Contributions are welcome!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue on GitHub or contact the maintainers.

---

**Made with ❤️ for Discord communities**
