import logging
import json
import asyncio
import random
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Tuple
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.ext import (
    Application, 
    CallbackQueryHandler, 
    ContextTypes,
    CommandHandler
)

# Add database directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))

# Import database
from database import db

# Configure logging with rotation and size limits
def setup_logging():
    """Setup logging with rotation to prevent large files"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Rotating file handler for quiz bot
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        'logs/quiz_bot.log',
        maxBytes=10*1024*1024,  # 10MB per file
        backupCount=5,          # Keep 5 backup files
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

# Configuration
QUIZ_INTERVAL_MINUTES = 120  # Post every 120 minutes (2 hours)
MESSAGE_DELETE_DELAY = 30  # seconds

# Load configuration from JSON file
def load_config():
    """Load bot configuration from JSON file"""
    try:
        with open('configs/tokens.json', 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        logger.error("Config file not found. Please create configs/tokens.json")
        return {}
    except KeyError as e:
        logger.error(f"Configuration key not found: {e}")
        return {}

# Load quiz data from JSON file (questions stay in JSON)
def load_quiz_data():
    """Load quiz data from JSON file"""
    try:
        with open('configs/quizzes.json', 'r') as f:
            data = json.load(f)
        return data['quiz_batches']
    except FileNotFoundError:
        logger.error("Quiz data file not found. Please create configs/quizzes.json")
        return []
    except KeyError:
        logger.error("quiz_batches not found in quiz file")
        return []

# Bot configuration
CONFIG = load_config()
BOT_TOKEN = CONFIG.get('quiz_bot_token')
TARGET_CHATS = CONFIG.get('target_chats', [-1002478514549, -1002763968200])  # Fallback to original chats

if not BOT_TOKEN:
    logger.error("Bot token not found. Exiting.")
    exit(1)

class AtenuQuizBot:
    """Atenu Quiz Bot with Database Backend"""
    
    def __init__(self, token: str):
        self.token = token
        self.quiz_data = load_quiz_data()
        self.available_batches = list(range(len(self.quiz_data)))  # Track available batches
        self.current_batch_index = None  # Will be set randomly
        
        # Shuffle batches for random order
        random.shuffle(self.available_batches)
        
        # Build application
        self.application = (
            Application.builder()
            .token(token)
            .concurrent_updates(True)
            .build()
        )
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup all bot handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("quiz", self.manual_quiz_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        self.application.add_handler(CommandHandler("top", self.leaderboard_command))  # Alias
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the quiz bot")
        
        welcome_text = f"""
🎯 Welcome to AtenuQuizBot, {user.first_name}!

I automatically post quiz batches every {QUIZ_INTERVAL_MINUTES} minutes to help you practice.

📚 **Commands:**
• /quiz - Get current quiz manually
• /stats - View your quiz statistics
• /leaderboard - View current rankings
• /start - Show this message

📊 **Current Status:**
• Total Batches: {len(self.quiz_data)}
• Batches Remaining: {len(self.available_batches)}
• Random Order: Enabled
• Database: SQLite ⚡
• Anti-Abuse: Progressive Cooldown 🛡️

🛡️ **Answer Limits:**
• 1st attempt: Immediate
• 2nd attempt: 1-hour cooldown
• 3rd attempt: 6-hour cooldown
• 4th+ attempts: 24-hour cooldown

The next quiz will be posted automatically!
"""
        
        await update.message.reply_text(welcome_text)

    async def manual_quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /quiz command - get current quiz manually"""
        chat_id = update.effective_chat.id
        
        if chat_id not in TARGET_CHATS:
            await update.message.reply_text("❌ This command only works in designated quiz groups.")
            return
        
        if not self.quiz_data:
            await update.message.reply_text("❌ No quiz data available.")
            return
        
        # Send current batch to this chat only
        if self.current_batch_index is not None:
            await self.send_quiz_batch([chat_id], context)
        else:
            await update.message.reply_text("⏳ No quiz batch is currently active. Wait for the next scheduled quiz!")

    async def send_quiz_batch(self, target_chats: List[int], context: ContextTypes.DEFAULT_TYPE):
        """Send the current quiz batch to target chats"""
        try:
            if not self.quiz_data or self.current_batch_index is None or self.current_batch_index >= len(self.quiz_data):
                logger.error("No quiz data available or invalid batch index")
                return
            
            batch = self.quiz_data[self.current_batch_index]
            
            # Calculate batch position in random sequence
            completed_batches = len(self.quiz_data) - len(self.available_batches)
            total_batches = len(self.quiz_data)
            
            # Format header message
            current_time = datetime.now().strftime('%H:%M')
            header_text = f"""
🎯 **Quiz Batch {completed_batches + 1}/{total_batches}** (Random Order)
📚 **{batch['title']}**

⏰ Time: {current_time}
📊 Questions: {len(batch['questions'])}
🎲 Batch ID: {batch['batch_id']}
⚡ Database: SQLite
🛡️ Anti-Abuse: Progressive Cooldown

Answer each question by clicking the buttons below!
**Note:** Multiple attempts have progressive cooldowns (1h → 6h → 24h)
"""
            
            # Send to all target chats
            for chat_id in target_chats:
                try:
                    # Send header
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=header_text,
                        parse_mode='Markdown'
                    )
                    
                    # Send each question
                    for i, question in enumerate(batch['questions'], 1):
                        question_text = f"""
❓ **Question {i}:**
{question['question'].replace('__________', '----------')}

**Options:**
A. {question['options'][0]}
B. {question['options'][1]}
C. {question['options'][2]}
D. {question['options'][3]}

*Click your answer below:*
"""
                        
                        # Create answer keyboard
                        keyboard = [
                            [
                                InlineKeyboardButton("A", callback_data=f"answer_{question['id']}_0"),
                                InlineKeyboardButton("B", callback_data=f"answer_{question['id']}_1"),
                                InlineKeyboardButton("C", callback_data=f"answer_{question['id']}_2"),
                                InlineKeyboardButton("D", callback_data=f"answer_{question['id']}_3")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=question_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                        
                        # Small delay between questions
                        await asyncio.sleep(0.5)
                    
                    logger.info(f"Successfully sent random quiz batch (ID: {batch['batch_id']}) to chat {chat_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send quiz to chat {chat_id}: {e}")
                    # Continue with other chats even if one fails
                    continue
                    
        except Exception as e:
            logger.error(f"Critical error in send_quiz_batch: {e}")
            # Reset current batch index to prevent blocking
            self.current_batch_index = None

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        
        if query.data.startswith("answer_"):
            await self.handle_answer(update, context)
        elif query.data.startswith("explanation_"):
            await self.handle_explanation(update, context)
        else:
            # Handle unknown callback types
            await query.answer("❌ Unknown action!", show_alert=True)

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user answer with progressive cooldown anti-abuse"""
        query = update.callback_query
        user_id = query.from_user.id
        user_name = query.from_user.first_name or query.from_user.username or f"User_{user_id}"
        
        # Parse callback data
        parts = query.data.split('_')
        question_id = int(parts[1])
        selected_option = int(parts[2])
        
        # CHECK COOLDOWN TO PREVENT ABUSE
        can_answer, cooldown_message = await db.check_answer_cooldown(user_id, question_id)
        if not can_answer:
            await query.answer(cooldown_message, show_alert=True)
            return
        
        # Find the question
        question = None
        for batch in self.quiz_data:
            for q in batch['questions']:
                if q['id'] == question_id:
                    question = q
                    break
            if question:
                break
        
        if not question:
            await query.answer("❌ Question not found.", show_alert=True)
            return
        
        # Check if answer is correct
        is_correct = selected_option == question["correct_answer"]
        
        # Calculate points: +3 for correct (+2 correct + 1 participation), -1 for incorrect (-2 wrong + 1 participation)
        points = 3 if is_correct else -1
        
        # Save to DATABASE
        try:
            await db.save_user_answer(
                user_id=user_id,
                question_id=question_id,
                selected=selected_option,
                correct_answer=question["correct_answer"],
                is_correct=is_correct,
                points=points,
                username=query.from_user.username,
                first_name=query.from_user.first_name
            )
            logger.info(f"💾 Database: Saved answer for {user_name} (ID: {user_id})")
        except Exception as e:
            logger.error(f"❌ Database error saving answer: {e}")
            # Fallback: Inform user of technical issue
            await query.answer("⚠️ Technical issue saving your answer. Please try again.", show_alert=True)
            return
        
        # Answer the callback query (acknowledge button press)
        await query.answer(f"Answer recorded! {'+3' if is_correct else '-1'} points")
        
        # Format result
        selected_letter = chr(65 + selected_option)
        correct_letter = chr(65 + question["correct_answer"])
        
        if is_correct:
            result_text = f"✅ **{user_name}**, you selected {selected_letter} - **Correct!** (+3 points)"
        else:
            result_text = f"❌ **{user_name}**, you selected {selected_letter} - **Incorrect!** (-1 point)\nThe correct answer is {correct_letter}."
        
        result_text += f"\n\n**Your Answer:** {question['options'][selected_option]}"
        result_text += f"\n**Correct Answer:** {question['options'][question['correct_answer']]}"
        
        # Add cooldown info for transparency
        result_text += f"\n\n🛡️ **Anti-Abuse:** {cooldown_message}"
        
        # Add explanation button
        keyboard = [[
            InlineKeyboardButton("📝 Show Explanation", callback_data=f"explanation_{question_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        sent_message = await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=result_text,
            reply_to_message_id=query.message.message_id,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Schedule message deletion
        context.job_queue.run_once(
            self.delete_message,
            when=MESSAGE_DELETE_DELAY,
            data={'chat_id': query.message.chat.id, 'message_id': sent_message.message_id}
        )

    async def handle_explanation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show explanation for the question"""
        query = update.callback_query
        
        # Parse callback data
        parts = query.data.split('_')
        question_id = int(parts[1])
        
        # Find the question
        question = None
        for batch in self.quiz_data:
            for q in batch['questions']:
                if q['id'] == question_id:
                    question = q
                    break
            if question:
                break
        
        if question:
            # Answer callback query
            await query.answer("📝 Showing explanation...")
            
            current_text = query.message.text
            explanation_text = f"\n\n📝 **Explanation:**\n{question['explanation']}"
            
            await query.edit_message_text(
                current_text + explanation_text,
                parse_mode='Markdown'
            )
            
            # Schedule message deletion
            context.job_queue.run_once(
                self.delete_message,
                when=MESSAGE_DELETE_DELAY,
                data={'chat_id': query.message.chat.id, 'message_id': query.message.message_id}
            )
        else:
            await query.answer("❌ Question not found.", show_alert=True)

    async def delete_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Delete a message"""
        try:
            job_data = context.job.data
            await context.bot.delete_message(
                chat_id=job_data['chat_id'],
                message_id=job_data['message_id']
            )
        except Exception:
            pass  # Message might already be deleted

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - Database Version"""
        user_id = update.effective_user.id
        
        # Get stats from DATABASE
        try:
            user_stats = await db.get_user_stats(user_id)
            
            if not user_stats:
                await update.message.reply_text("📊 You haven't answered any questions yet!")
                return
            
            stats_text = f"""
📊 **Your Quiz Statistics**

🎯 **Overall Performance:**
• Questions Answered: {user_stats['total_questions_answered']}
• Correct Answers: {user_stats['total_correct_answers']}
• Overall Accuracy: {user_stats['overall_accuracy']:.1f}%
• Total Points: {user_stats['total_points']} 🏆

📅 **Last Activity:** {user_stats['last_activity'][:19].replace('T', ' ')}
⚡ **Database**: SQLite
🛡️ **Anti-Abuse**: Progressive Cooldown Active

Use /leaderboard to see rankings!
"""
            
            await update.message.reply_text(stats_text)
            
        except Exception as e:
            logger.error(f"❌ Database error getting user stats: {e}")
            await update.message.reply_text("❌ Error retrieving your stats. Please try again.")

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leaderboard command - Database Version"""
        try:
            # Get leaderboards from DATABASE with error handling
            current_time = datetime.now(timezone.utc)
            today = current_time.strftime('%Y-%m-%d')
            week = current_time.strftime('%Y-W%U')
            month = current_time.strftime('%Y-%m')
            
            daily_top = await db.get_leaderboard('daily', today, 5)
            weekly_top = await db.get_leaderboard('weekly', week, 5)
            monthly_top = await db.get_leaderboard('monthly', month, 5)
            
            leaderboard_text = f"""
🏆 **LEADERBOARD** 🏆

📅 **Today ({today}):**
{self.format_top_users(daily_top)}

📊 **This Week:**
{self.format_top_users(weekly_top)}

📈 **This Month:**
{self.format_top_users(monthly_top)}

💡 **Scoring System:**
• Correct Answer: +3 points (+2 correct + 1 participation)
• Wrong Answer: -1 point (-2 wrong + 1 participation)
• Minimum Points: 0 (no negative balance)

🛡️ **Anti-Abuse System:**
• Progressive cooldowns prevent spam (1h → 6h → 24h)
• Fair competition for all participants

⚡ **Database**: SQLite
"""
            
            await update.message.reply_text(leaderboard_text)
            
        except Exception as e:
            logger.error(f"❌ Database error getting leaderboard: {e}")
            await update.message.reply_text("❌ Error retrieving leaderboard. Please try again.")

    def format_top_users(self, top_users: List[Tuple[str, int, int, float]]) -> str:
        """Format top users for display"""
        if not top_users:
            return "🚫 No participants yet"
        
        formatted = []
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (name, points, questions, accuracy) in enumerate(top_users):
            if i < 3:  # Top 3 get medals
                medal = medals[i]
            else:  # Others get numbered position
                medal = f"{i+1}."
            
            # Truncate long names
            display_name = name[:15] + "..." if len(name) > 15 else name
            formatted.append(f"{medal} {display_name}: {points} pts ({questions}Q, {accuracy:.0f}%)")
        
        return "\n".join(formatted)

    async def weekly_leaderboard_announcement(self, context: ContextTypes.DEFAULT_TYPE):
        """Send weekly leaderboard announcement every Sunday"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Calculate last Monday (proper ISO week start)
            days_since_monday = current_time.weekday()  # 0=Monday, 6=Sunday
            last_monday = current_time - timedelta(days=days_since_monday + 7)
            last_week = last_monday.strftime('%Y-W%U')
            
            # Get winners from DATABASE
            top_users = await db.get_leaderboard('weekly', last_week, 3)
            
            if not top_users:
                logger.info("No participants for weekly leaderboard")
                return
            
            # Create announcement message with proper week dates
            week_start = last_monday.strftime('%B %d')
            week_end = (last_monday + timedelta(days=6)).strftime('%B %d, %Y')
            
            announcement_text = f"""
🎉 **WEEKLY LEADERBOARD RESULTS** 🎉

📊 **Week of {week_start} - {week_end}**

🏆 **Top Performers:**
{self.format_top_users(top_users)}

Congratulations to all participants! 🎊

Keep participating in our quizzes to climb the leaderboard!
Next announcement: Next Sunday

Use /leaderboard to see current rankings anytime!
⚡ **Database**: SQLite
🛡️ **Fair Play**: Anti-abuse system ensures fair competition
"""
            
            # Send to all target chats
            for chat_id in TARGET_CHATS:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=announcement_text,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Sent weekly leaderboard to chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send weekly leaderboard to {chat_id}: {e}")
            
            logger.info("Weekly leaderboard announcement completed")
            
        except Exception as e:
            logger.error(f"Error in weekly leaderboard announcement: {e}")

    async def monthly_leaderboard_announcement(self, context: ContextTypes.DEFAULT_TYPE):
        """Send monthly leaderboard announcement on last day of month and clear data"""
        try:
            current_time = datetime.now(timezone.utc)
            # Get last month's data (proper month calculation)
            if current_time.month == 1:
                last_month_date = current_time.replace(year=current_time.year - 1, month=12)
            else:
                last_month_date = current_time.replace(month=current_time.month - 1)
            
            last_month = last_month_date.strftime('%Y-%m')
            
            # Get winners from DATABASE
            top_users = await db.get_leaderboard('monthly', last_month, 3)
            
            if not top_users:
                logger.info("No participants for monthly leaderboard")
                # Clear monthly data even if no participants
                await db.clear_monthly_leaderboard()
                return
            
            # Create announcement message
            announcement_text = f"""
🎉 **MONTHLY LEADERBOARD RESULTS** 🎉

📊 **Month of {last_month_date.strftime('%B %Y')}**

🏆 **Top Performers:**
{self.format_top_users(top_users)}

🌟 Congratulations to all participants! 🎊

Monthly leaderboard has been reset for the new month.
Keep participating in our quizzes!

Use /leaderboard to see current rankings anytime!
⚡ **Database**: SQLite
🛡️ **Fair Play**: Anti-abuse system ensures fair competition
"""
            
            # Send to all target chats
            for chat_id in TARGET_CHATS:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=announcement_text,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Sent monthly leaderboard to chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send monthly leaderboard to {chat_id}: {e}")
            
            # Clear monthly leaderboard data after announcement
            await db.clear_monthly_leaderboard()
            logger.info("Monthly leaderboard announcement completed and data cleared")
            
        except Exception as e:
            logger.error(f"Error in monthly leaderboard announcement: {e}")

    async def scheduled_quiz_sender(self, context: ContextTypes.DEFAULT_TYPE):
        """Send scheduled quiz with random selection"""
        try:
            if not self.quiz_data:
                logger.error("No quiz data available")
                return
            
            # Check if we have available batches
            if not self.available_batches:
                # All batches completed, start new random cycle
                logger.info("All quiz batches completed! Starting new random cycle.")
                self.available_batches = list(range(len(self.quiz_data)))
                random.shuffle(self.available_batches)
            
            # Get next random batch
            self.current_batch_index = self.available_batches.pop(0)
            current_batch = self.quiz_data[self.current_batch_index]
            
            # Send current batch
            await self.send_quiz_batch(TARGET_CHATS, context)
            
            remaining_batches = len(self.available_batches)
            completed_batches = len(self.quiz_data) - remaining_batches
            
            logger.info(f"Sent random quiz batch {completed_batches}/{len(self.quiz_data)} (ID: {current_batch['batch_id']}, Title: '{current_batch['title']}')")
            logger.info(f"Remaining batches in current cycle: {remaining_batches}")
            
        except Exception as e:
            logger.error(f"Error in scheduled_quiz_sender: {e}")

    async def weekly_cleanup(self, context: ContextTypes.DEFAULT_TYPE):
        """Weekly cleanup of old answers (runs every Sunday at 2 AM)"""
        try:
            await db.cleanup_old_answers()
            logger.info("Weekly cleanup completed - removed answers older than 30 days")
        except Exception as e:
            logger.error(f"Error in weekly cleanup: {e}")

    def run(self):
        """Start the bot with scheduling"""
        try:
            job_queue = self.application.job_queue
            if job_queue is None:
                raise RuntimeError("JobQueue not available")
            
            # Send first batch immediately (after 10 seconds)
            job_queue.run_once(
                self.scheduled_quiz_sender,
                when=10  # Start first quiz after 10 seconds
            )
            
            # Schedule subsequent quizzes every 120 minutes
            job_queue.run_repeating(
                self.scheduled_quiz_sender,
                interval=timedelta(minutes=QUIZ_INTERVAL_MINUTES),
                first=timedelta(minutes=QUIZ_INTERVAL_MINUTES + 0.17)  # Start regular schedule after first quiz
            )
            
            # Schedule weekly leaderboard announcement every Sunday at 9:00 AM
            now = datetime.now()
            days_until_sunday = (6 - now.weekday()) % 7  # 0 = Monday, 6 = Sunday
            if days_until_sunday == 0 and now.hour >= 9:  # If it's Sunday and past 9 AM
                days_until_sunday = 7  # Schedule for next Sunday
            
            next_sunday = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
            
            job_queue.run_repeating(
                self.weekly_leaderboard_announcement,
                interval=timedelta(weeks=1),
                first=next_sunday
            )
            
            # Schedule monthly leaderboard announcement on last day of each month at 11:00 PM
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            
            # Last day of current month
            last_day_current_month = next_month - timedelta(days=1)
            last_day_announcement_time = last_day_current_month.replace(hour=23, minute=0, second=0, microsecond=0)
            
            # If we've already passed this month's last day, schedule for next month
            if now > last_day_announcement_time:
                if next_month.month == 12:
                    next_next_month = next_month.replace(year=next_month.year + 1, month=1, day=1)
                else:
                    next_next_month = next_month.replace(month=next_month.month + 1, day=1)
                last_day_announcement_time = (next_next_month - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
            
            # Schedule weekly cleanup (every Sunday at 2:00 AM)
            cleanup_time = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if now > cleanup_time:
                cleanup_time += timedelta(days=1)  # Next day if already passed
            
            # Find next Sunday for cleanup
            days_until_sunday_cleanup = (6 - now.weekday()) % 7
            if days_until_sunday_cleanup == 0 and now.hour >= 2:
                days_until_sunday_cleanup = 7
            
            next_cleanup = cleanup_time + timedelta(days=days_until_sunday_cleanup)
            
            job_queue.run_repeating(
                self.weekly_cleanup,
                interval=timedelta(weeks=1),
                first=next_cleanup
            )
            
            # Schedule monthly announcements
            job_queue.run_repeating(
                self.monthly_leaderboard_announcement,
                interval=timedelta(days=30),  # Approximate interval, will auto-adjust
                first=last_day_announcement_time
            )
            
            logger.info(f"🤖 Atenu Quiz Bot started with SQLite Database!")
            logger.info(f"📊 Total quiz batches: {len(self.quiz_data)}")
            logger.info(f"⏰ Quiz schedule: First batch in 10 seconds, then every {QUIZ_INTERVAL_MINUTES} minutes")
            logger.info(f"🏆 Weekly leaderboard: Every Sunday at 9:00 AM")
            logger.info(f"📅 Monthly leaderboard: Last day of each month at 11:00 PM (with data clearing)")
            logger.info(f"🛡️ ANTI-ABUSE SYSTEM: Progressive cooldown enabled (1h → 6h → 24h)")
            logger.info(f"🧹 Weekly cleanup: Old answers deleted every Sunday at 2:00 AM")
            logger.info(f"🎯 Target chats: {TARGET_CHATS}")
            logger.info(f"⚡ Database: SQLite at database/atenu_quiz.db")
            
            # Run with optimized settings
            self.application.run_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query']
            )
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

def main():
    """Main function"""
    bot = AtenuQuizBot(BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    main()