Of course\! Here is a comprehensive `README.md` file for your `AtenuHelpBot` and `AtenuQuizBot` GitHub repository, based on the entire development journey you've outlined.

-----

# Atenu Telegram Bots: Help & Quiz Ecosystem

This repository contains the source code for a powerful and scalable Telegram bot ecosystem, featuring **AtenuQuizBot** and **AtenuHelpBot**.

**AtenuQuizBot** is designed to engage users with automated, scheduled quizzes, a competitive leaderboard system, and robust performance backed by a SQLite database. **AtenuHelpBot** provides simple, command-based support and logs user interactions. This project is built to be secure, scalable, and easy to deploy on a production server using `systemd`.

 (*Image placeholder: Consider adding a GIF showcasing the bots in action.*)

-----

## 🚀 Features

### AtenuQuizBot (The Main Star ⭐)

  * **🤖 Automated Quiz Scheduling**: Automatically posts quizzes to designated chat groups at a configurable 30-minute interval.
  * **🎲 Randomized Batch System**: Shuffles the order of quiz batches to ensure content remains fresh and unpredictable for users.
  * **🏆 Comprehensive Leaderboard**:
      * Tracks **Daily**, **Weekly**, and **Monthly** user rankings.
      * Users can check standings anytime with the `/leaderboard` command.
      * **Automated Announcements**: Posts the weekly winners every Sunday and monthly winners on the last day of the month.
  * **🧠 Smart Scoring System**:
      * **+3 points** for a correct answer (+2 for correctness, +1 for participation).
      * **-1 point** for an incorrect answer (-2 for wrong, +1 for participation).
      * **No negative balances**: A user's score cannot drop below zero.
  * **🔄 24-Hour Answer Reset**: Users can retry a question after 24 hours, encouraging daily practice and learning without allowing spam.
  * **⚡ High-Performance Database Backend**:
      * Uses **SQLite** to handle tens of thousands of users and millions of answers without performance degradation.
      * Asynchronous database operations (`asyncio.to_thread`) prevent the bot from blocking, ensuring a smooth user experience.
      * **Unique constraints** prevent data duplication and ensure integrity.
  * **🧹 Automatic Data Management**:
      * Monthly leaderboard data is automatically cleared after the winner announcement.
      * A weekly cleanup job removes user answers older than 30 days and leaderboard entries older than 90 days to keep the database lean.
  * **🔒 Robust & Secure**:
      * Prevents duplicate answers within the 24-hour window with clear user notifications.
      * Graceful error handling for database issues and API timeouts.
  * **📁 Smart Log Rotation**: Log files are automatically rotated (e.g., 10MB limit with 5 backups) to prevent them from consuming excessive disk space.

### AtenuHelpBot

  * **🙋 Simple Command-Based Support**: Provides quick answers and links based on user commands.
  * **✍️ Interaction Logging**: Logs all user interactions to the SQLite database for analytics.
  * **📄 Config-Driven Responses**: Help responses are managed via a simple JSON file.
  * **📁 Log Rotation**: Implements the same smart log rotation as the Quiz Bot.

-----

## 🏗️ Architecture & Project Structure

The project is designed for clean separation of concerns, scalability, and ease of maintenance. It uses a central SQLite database for all dynamic data, while static content and configurations are handled by JSON files.

```
atenu-telegram-bots/
├── AtenuHelpBot/
│   ├── help_bot.py           # Main code for the help bot
│   └── requirements.txt      # Python dependencies
├── AtenuQuizBot/
│   ├── quiz_bot.py           # Main code for the quiz bot
│   └── requirements.txt      # Python dependencies
├── configs/
│   ├── tokens.json           # Stores bot tokens and target chat IDs
│   ├── quizzes.json          # All quiz batches and questions
│   ├── help_responses.json   # Responses for the help bot
│   └── database.json         # Configuration for the database
├── data/
│   └── (backups of old JSON files may appear here after migration)
├── database/
│   ├── atenu_quiz.db         # The SQLite database file
│   ├── database.py           # Handles all database operations (CRUD)
│   ├── models.py             # Defines the database schema (SQLAlchemy models)
│   └── migrate_from_json.py  # Script to migrate old JSON data to SQLite
└── logs/
    ├── help_bot.log          # Rotated logs for the help bot
    └── quiz_bot.log          # Rotated logs for the quiz bot
```

-----

## 🛠️ Setup and Installation

Follow these steps to get the bot ecosystem running on your local machine or a production server.

### Prerequisites

  * Python 3.8+
  * `pip` for installing packages

### 1\. Clone the Repository

```bash
git clone <your-repo-url>
cd atenu-telegram-bots
```

### 2\. Install Dependencies

It's recommended to use a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r AtenuQuizBot/requirements.txt
pip install -r AtenuHelpBot/requirements.txt
```

The quiz bot `requirements.txt` should contain:

```
python-telegram-bot
sqlalchemy
aiosqlite
```

### 3\. Configure the Bots

You need to provide API tokens and define your quiz content.

**A. Create `configs/tokens.json`:**
This file holds your secret tokens and the group chat IDs where the quiz bot will post.

```json
{
  "help_bot_token": "YOUR_HELP_BOT_TOKEN_HERE",
  "quiz_bot_token": "YOUR_QUIZ_BOT_TOKEN_HERE",
  "target_chats": [**********, **********]
}
```

**B. Create `configs/quizzes.json`:**
Add your quiz batches here. The bot will randomly select from this list.

```json
{
  "quiz_batches": [
    {
      "batch_id": 1,
      "title": "Grammar: Verb Tenses",
      "questions": [
        {
          "id": 1,
          "question": "By the time we arrived, the movie __________.",
          "options": ["already started", "had already started", "has already started", "starts"],
          "correct_answer": 1,
          "explanation": "Use past perfect for an action completed before another past action."
        }
      ]
    }
    // Add your other 20+ batches here...
  ]
}
```

### 4\. Initialize the Database

The first time you run the bots, the SQLite database and its tables will be created automatically. If you previously used the JSON-based version, you can migrate your data.

  * **For a fresh start**: No action needed. The database file `database/atenu_quiz.db` will be created on the first run.
  * **To migrate from old JSON files**: Place your `user_stats.json` and `help_tickets.json` in the `data/` directory and run the migration script:
    ```bash
    python3 database/migrate_from_json.py
    ```
    This will safely transfer your data into the new SQLite database and create backups of the old JSON files.

-----

## 🚀 Deployment (Production VPS with systemd)

For production, it is highly recommended to run the bots as dedicated `systemd` services under an unprivileged user.

### 1\. Create a Dedicated User

Create a system user named `telegram-bots` that cannot log in, and create its home directory.

```bash
sudo useradd -r -s /bin/false -d /opt/telegram-bots telegram-bots
sudo mkdir -p /opt/telegram-bots
sudo chown -R telegram-bots:telegram-bots /opt/telegram-bots
```

### 2\. Transfer Project Files

Copy your entire project repository to `/opt/telegram-bots`. Ensure the `telegram-bots` user owns all files.

```bash
sudo cp -r . /opt/telegram-bots/
sudo chown -R telegram-bots:telegram-bots /opt/telegram-bots
```

### 3\. Create systemd Service Files

**A. For `AtenuQuizBot`:**
Create the service file:

```bash
sudo nano /etc/systemd/system/atenu-quiz-bot.service
```

Paste the following configuration:

```ini
[Unit]
Description=Atenu Telegram Quiz Bot
After=network.target

[Service]
Type=simple
User=telegram-bots
Group=telegram-bots
WorkingDirectory=/opt/telegram-bots/AtenuQuizBot
ExecStart=/usr/bin/python3 /opt/telegram-bots/AtenuQuizBot/quiz_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**B. For `AtenuHelpBot`:**
Create the service file:

```bash
sudo nano /etc/systemd/system/atenu-help-bot.service
```

Paste the following configuration:

```ini
[Unit]
Description=Atenu Telegram Help Bot
After=network.target

[Service]
Type=simple
User=telegram-bots
Group=telegram-bots
WorkingDirectory=/opt/telegram-bots/AtenuHelpBot
ExecStart=/usr/bin/python3 /opt/telegram-bots/AtenuHelpBot/help_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4\. Enable and Start the Services

Reload `systemd`, enable the services to start on boot, and start them now.

```bash
sudo systemctl daemon-reload
sudo systemctl enable atenu-quiz-bot.service atenu-help-bot.service
sudo systemctl start atenu-quiz-bot.service atenu-help-bot.service
```

### 5\. Check Service Status

You can check the status and logs of your bots at any time:

```bash
sudo systemctl status atenu-quiz-bot.service
sudo journalctl -u atenu-quiz-bot.service -f
```

-----

## 💬 Usage Commands

  * `/start` - Welcome message.
  * `/quiz` - Manually start a quiz from the current batch.
  * `/leaderboard` - View the daily, weekly, and monthly leaderboards.
  * `/stats` - View your personal quiz statistics.
  * `/help` - (In Help Bot) Get a list of available help commands.

-----

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
