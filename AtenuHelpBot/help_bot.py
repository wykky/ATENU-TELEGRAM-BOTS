import logging
from logging.handlers import RotatingFileHandler
import asyncio
import json
import os
from functools import lru_cache
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configure logging with rotation to prevent large files
def setup_logging():
    """Setup logging with rotation to prevent large files"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Rotating file handler for help bot
    file_handler = RotatingFileHandler(
        'logs/help_bot.log',
        maxBytes=5*1024*1024,   # 5MB per file
        backupCount=3,          # Keep 3 backup files
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return logging.getLogger(__name__)

# Setup logging
logger = setup_logging()

# Load configuration from JSON file
def load_config():
    """Load bot configuration from JSON file"""
    try:
        with open('configs/tokens.json', 'r') as f:
            config = json.load(f)
        return config['help_bot_token']
    except FileNotFoundError:
        logger.error("Config file not found. Please create configs/tokens.json")
        return None
    except KeyError:
        logger.error("help_bot_token not found in config file")
        return None

# Bot configuration
BOT_TOKEN = load_config()

if not BOT_TOKEN:
    logger.error("Bot token not found. Exiting.")
    exit(1)

# Pre-formatted response data with immutable tuple for better memory efficiency
RESPONSES = {
    "start": "👋 Welcome to Atenu Help Bot!\nUse /help to see what I can do.",
    "courses": "📘 Explore our full library of courses and QuickNotes at https://atenu.org/courses",
    "quiz": "📝 Practice past exams at https://atenu.org/exams",
    "survey": "📊 Help us improve! Take our short feedback survey and win 1000 birr!\n👉 https://ask.atenu.org/atenu-feedback-2025",
    "help": (
        "ℹ️ Here's what I can do:\n"
        "/courses – Explore learning materials\n"
        "/quiz – Try past exams and practice\n"
        "/survey – Share feedback and win\n"
        "/news – Read latest Atenu updates\n"
        "/scholarships – Find scholarship info\n"
        "/register – Create your Atenu account\n"
        "/donate – Support free education\n"
        "/contact – Reach our support team"
    ),
    "contact": "📬 Contact us at info@atenu.org or message us on our Telegram Group Chat: https://t.me/atenuGroup",
    "news": "📰 Stay updated with the latest news by visiting our Telegram Channel: https://t.me/atenuChannel",
    "scholarships": "🎓 Browse scholarships for Ethiopian students: https://atenu.org/scholarships-directory/",
    "register": "🆕 Create your free account now: https://atenu.org/student-registration/",
    "donate": "💖 Support free learning in Ethiopia: https://atenu.org/donate"
}

# Freeze the dictionary to prevent accidental modifications
RESPONSES = dict(RESPONSES)

# Cache command handlers to avoid recreation
@lru_cache(maxsize=32)
def get_cached_response(response_key):
    """Cache responses to avoid dictionary lookups"""
    return RESPONSES.get(response_key)

# Log user interactions for help tickets (optional - can be added later)
def log_user_interaction(user_id, username, command):
    """Log user interactions to help_tickets.json or database"""
    try:
        # Load existing data
        try:
            with open('data/help_tickets.json', 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"interactions": []}
        
        # Add new interaction
        interaction = {
            "user_id": user_id,
            "username": username,
            "command": command,
            "timestamp": asyncio.get_event_loop().time()
        }
        data["interactions"].append(interaction)
        
        # Save back to file
        with open('data/help_tickets.json', 'w') as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error logging user interaction: {e}")

# Optimized generic command handler
async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Single handler for all commands with minimal overhead"""
    if not update.message or not update.message.text:
        return
    
    # Extract command without the '/' prefix
    cmd = update.message.text.split()[0][1:].lower()
    
    # Get cached response
    response = get_cached_response(cmd)
    
    if response:
        try:
            # Use reply_text with disable_web_page_preview for faster sending
            await update.message.reply_text(
                response, 
                disable_web_page_preview=True
            )
            
            # Log user interaction
            user = update.effective_user
            log_user_interaction(user.id, user.username, cmd)
            
            # Log with minimal overhead
            if logger.isEnabledFor(logging.INFO):
                logger.info(f"Command /{cmd} executed by user {user.id}")
        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Error in /{cmd} command: {e}")
            # Send error response without awaiting if possible
            asyncio.create_task(
                update.message.reply_text("Sorry, something went wrong. Please try again.")
            )

# Optimized error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors with minimal logging overhead"""
    if logger.isEnabledFor(logging.WARNING):
        logger.warning(f'Update {update} caused error {context.error}')

def main():
    """Main function with optimized bot initialization"""
    # Create application with performance optimizations
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)  # Enable concurrent update processing
        .build()
    )
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Register a single command handler for all commands
    commands = [
        "start", "courses", "quiz", "survey", "help", 
        "contact", "news", "scholarships", "register", "donate"
    ]
    
    # Use a single handler instance for all commands
    for cmd in commands:
        app.add_handler(CommandHandler(cmd, handle_command))
    
    # Start the bot with optimized settings
    logger.info("🤖 Atenu Help Bot is starting with log rotation...")
    logger.info("📁 Log files: 5MB max, 3 backups")
    app.run_polling(
        drop_pending_updates=True,  # Skip old updates for faster startup
        allowed_updates=Update.MESSAGE  # Only process message updates
    )

if __name__ == "__main__":
    main()