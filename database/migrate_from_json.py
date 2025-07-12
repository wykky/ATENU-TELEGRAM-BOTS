"""
Migration script to convert existing JSON data to SQLite database
Run this once to migrate your existing data
"""

import json
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Add the parent directory to path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import User, LeaderboardEntry, HelpTicket
from database.database import DatabaseManager

def migrate_user_stats():
    """Migrate user stats from JSON to database"""
    print("🔄 Starting migration from JSON to SQLite...")
    
    # Initialize database
    db = DatabaseManager()
    session = db.get_session()
    
    try:
        # Load existing JSON data
        json_path = "data/user_stats.json"
        if not os.path.exists(json_path):
            print(f"❌ JSON file not found: {json_path}")
            return
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        users_data = data.get("users", {})
        leaderboard_data = data.get("leaderboard", {})
        
        print(f"📊 Found {len(users_data)} users to migrate")
        
        # Migrate users
        migrated_users = 0
        for user_id_str, user_info in users_data.items():
            user_id = int(user_id_str)
            
            # Check if user already exists
            existing_user = session.query(User).filter(User.user_id == user_id).first()
            if existing_user:
                print(f"⚠️  User {user_id} already exists, skipping...")
                continue
            
            # Create new user
            user = User(
                user_id=user_id,
                username=user_info.get('username', ''),
                first_name=user_info.get('first_name', ''),
                total_quizzes_taken=user_info.get('total_quizzes_taken', 0),
                total_questions_answered=user_info.get('total_questions_answered', 0),
                total_correct_answers=user_info.get('total_correct_answers', 0),
                total_points=user_info.get('total_points', 0),
                overall_accuracy=user_info.get('overall_accuracy', 0.0),
                last_activity=datetime.fromisoformat(user_info.get('last_activity', datetime.utcnow().isoformat())),
                registration_date=datetime.fromisoformat(user_info.get('registration_date', datetime.utcnow().isoformat()))
            )
            
            session.add(user)
            migrated_users += 1
            
            if migrated_users % 100 == 0:
                print(f"✅ Migrated {migrated_users} users...")
        
        # Migrate leaderboard data
        migrated_entries = 0
        for period_type, periods in leaderboard_data.items():
            if period_type == "all_time":
                continue  # Skip all_time as we removed it
            
            print(f"📈 Migrating {period_type} leaderboard data...")
            
            for period_key, users in periods.items():
                for user_id_str, entry_data in users.items():
                    user_id = int(user_id_str)
                    
                    # Check if entry already exists
                    existing_entry = session.query(LeaderboardEntry).filter(
                        LeaderboardEntry.user_id == user_id,
                        LeaderboardEntry.period_type == period_type,
                        LeaderboardEntry.period_key == period_key
                    ).first()
                    
                    if existing_entry:
                        continue
                    
                    # Create leaderboard entry
                    entry = LeaderboardEntry(
                        user_id=user_id,
                        period_type=period_type,
                        period_key=period_key,
                        points=entry_data.get('points', 0),
                        questions_answered=entry_data.get('questions', 0),
                        correct_answers=entry_data.get('correct', 0)
                    )
                    
                    session.add(entry)
                    migrated_entries += 1
        
        # Commit all changes
        session.commit()
        
        print(f"✅ Migration completed successfully!")
        print(f"   👥 Users migrated: {migrated_users}")
        print(f"   📊 Leaderboard entries migrated: {migrated_entries}")
        print(f"   💾 Database saved to: database/atenu_quiz.db")
        
        # Create backup of original JSON
        backup_path = f"data/user_stats_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.rename(json_path, backup_path)
        print(f"   🔒 Original JSON backed up to: {backup_path}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        session.close()

def migrate_help_tickets():
    """Migrate help tickets from JSON to database"""
    print("🔄 Migrating help tickets...")
    
    db = DatabaseManager()
    session = db.get_session()
    
    try:
        json_path = "data/help_tickets.json"
        if not os.path.exists(json_path):
            print(f"❌ Help tickets JSON not found: {json_path}")
            return
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        interactions = data.get("interactions", [])
        print(f"📞 Found {len(interactions)} help interactions to migrate")
        
        migrated_tickets = 0
        for interaction in interactions:
            ticket = HelpTicket(
                user_id=interaction.get('user_id'),
                username=interaction.get('username', ''),
                command=interaction.get('command', ''),
                timestamp=datetime.fromisoformat(interaction.get('timestamp', datetime.utcnow().isoformat()))
            )
            session.add(ticket)
            migrated_tickets += 1
        
        session.commit()
        print(f"✅ Help tickets migrated: {migrated_tickets}")
        
        # Backup original
        backup_path = f"data/help_tickets_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.rename(json_path, backup_path)
        print(f"   🔒 Original help tickets backed up to: {backup_path}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Help tickets migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    print("🚀 Atenu Quiz Bot - JSON to SQLite Migration")
    print("=" * 50)
    
    # Create database directory
    os.makedirs("database", exist_ok=True)
    
    # Run migrations
    migrate_user_stats()
    migrate_help_tickets()
    
    print("\n🎉 Migration completed! Your bots can now use the SQLite database.")
    print("💡 Remember to update your bot code to use the database functions.")
    print("📝 Original JSON files have been backed up in the data/ directory.")