"""
Database operations for Atenu Quiz Bot
Handles all database interactions using SQLAlchemy with SQLite
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import create_engine, and_, desc, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from models import Base, User, UserAnswer, LeaderboardEntry, HelpTicket

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations for the quiz bot"""
    
    def __init__(self, db_path: str = "database/atenu_quiz.db"):
        """Initialize database connection"""
        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Create SQLite database
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        logger.info(f"Database initialized at {db_path}")
    
    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()
    
    # User Management
    async def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None) -> User:
        """Get existing user or create new one"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                user = User(
                    user_id=user_id,
                    username=username or '',
                    first_name=first_name or '',
                    registration_date=datetime.utcnow()
                )
                session.add(user)
                session.commit()
                logger.info(f"Created new user: {first_name} (ID: {user_id})")
            else:
                # Update user info if provided
                if username:
                    user.username = username
                if first_name:
                    user.first_name = first_name
                session.commit()
            
            session.refresh(user)
            return user
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error getting/creating user {user_id}: {e}")
            raise
        finally:
            session.close()
    
    async def save_user_answer(self, user_id: int, question_id: int, selected: int, 
                             correct_answer: int, is_correct: bool, points: int,
                             username: str = None, first_name: str = None) -> None:
        """Save user answer and update stats"""
        session = self.get_session()
        try:
            # Get or create user
            user = await self.get_or_create_user(user_id, username, first_name)
            
            # Save the answer
            answer = UserAnswer(
                user_id=user_id,
                question_id=question_id,
                selected_option=selected,
                correct_answer=correct_answer,
                is_correct=is_correct,
                points=points,
                timestamp=datetime.utcnow()
            )
            session.add(answer)
            
            # Update user stats
            user.total_questions_answered += 1
            if is_correct:
                user.total_correct_answers += 1
            
            # Update points (no negative balance)
            user.total_points = max(0, user.total_points + points)
            
            # Update accuracy
            if user.total_questions_answered > 0:
                user.overall_accuracy = (user.total_correct_answers / user.total_questions_answered) * 100
            
            user.last_activity = datetime.utcnow()
            
            # Update leaderboards
            await self._update_leaderboards(session, user_id, points, is_correct)
            
            session.commit()
            logger.info(f"Saved answer for user {first_name} (ID: {user_id}) - Points: {points}")
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error saving user answer: {e}")
            raise
        finally:
            session.close()
    
    async def _update_leaderboards(self, session: Session, user_id: int, points: int, is_correct: bool) -> None:
        """Update leaderboard entries for daily, weekly, monthly"""
        current_time = datetime.utcnow()
        
        periods = {
            'daily': current_time.strftime('%Y-%m-%d'),
            'weekly': current_time.strftime('%Y-W%U'),
            'monthly': current_time.strftime('%Y-%m')
        }
        
        for period_type, period_key in periods.items():
            # Get or create leaderboard entry
            entry = session.query(LeaderboardEntry).filter(
                and_(
                    LeaderboardEntry.user_id == user_id,
                    LeaderboardEntry.period_type == period_type,
                    LeaderboardEntry.period_key == period_key
                )
            ).first()
            
            if not entry:
                entry = LeaderboardEntry(
                    user_id=user_id,
                    period_type=period_type,
                    period_key=period_key,
                    points=0,
                    questions_answered=0,
                    correct_answers=0
                )
                session.add(entry)
            
            # Update entry
            entry.points = max(0, entry.points + points)
            entry.questions_answered += 1
            if is_correct:
                entry.correct_answers += 1
    
    async def get_leaderboard(self, period_type: str, period_key: str, limit: int = 5) -> List[Tuple[str, int, int, float]]:
        """Get leaderboard for specific period"""
        session = self.get_session()
        try:
            results = session.query(
                LeaderboardEntry, User.first_name, User.username
            ).join(
                User, LeaderboardEntry.user_id == User.user_id
            ).filter(
                and_(
                    LeaderboardEntry.period_type == period_type,
                    LeaderboardEntry.period_key == period_key
                )
            ).order_by(
                desc(LeaderboardEntry.points),
                desc(LeaderboardEntry.correct_answers)
            ).limit(limit).all()
            
            leaderboard = []
            for entry, first_name, username in results:
                name = first_name or username or f"User_{entry.user_id}"
                accuracy = (entry.correct_answers / max(1, entry.questions_answered)) * 100
                leaderboard.append((name, entry.points, entry.questions_answered, accuracy))
            
            return leaderboard
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
        finally:
            session.close()
    
    async def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Get user statistics"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                return None
            
            return {
                'total_questions_answered': user.total_questions_answered,
                'total_correct_answers': user.total_correct_answers,
                'total_points': user.total_points,
                'overall_accuracy': user.overall_accuracy,
                'last_activity': user.last_activity.isoformat() if user.last_activity else '',
                'registration_date': user.registration_date.isoformat() if user.registration_date else ''
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting user stats: {e}")
            return None
        finally:
            session.close()
    
    async def check_user_answered_question(self, user_id: int, question_id: int) -> bool:
        """Check if user has already answered a specific question"""
        session = self.get_session()
        try:
            answer = session.query(UserAnswer).filter(
                and_(
                    UserAnswer.user_id == user_id,
                    UserAnswer.question_id == question_id
                )
            ).first()
            
            return answer is not None
            
        except SQLAlchemyError as e:
            logger.error(f"Error checking user answer: {e}")
            return False
        finally:
            session.close()
    
    async def check_answer_cooldown(self, user_id: int, question_id: int) -> tuple:
        """Check if user can answer based on progressive cooldown"""
        session = self.get_session()
        try:
            # Count previous attempts
            attempts = session.query(UserAnswer).filter(
                and_(
                    UserAnswer.user_id == user_id,
                    UserAnswer.question_id == question_id
                )
            ).count()
            
            if attempts == 0:
                return True, "✅ First attempt"
            
            # Get last attempt time
            last_attempt = session.query(UserAnswer).filter(
                and_(
                    UserAnswer.user_id == user_id,
                    UserAnswer.question_id == question_id
                )
            ).order_by(UserAnswer.timestamp.desc()).first()
            
            time_since_last = datetime.utcnow() - last_attempt.timestamp
            
            # Progressive cooldown: 1hr → 6hr → 24hr
            if attempts == 1:
                cooldown = timedelta(hours=1)
                next_wait = "6 hours"
            elif attempts == 2:
                cooldown = timedelta(hours=6)
                next_wait = "24 hours"
            else:
                cooldown = timedelta(hours=24)
                next_wait = "24 hours"
            
            if time_since_last < cooldown:
                remaining = cooldown - time_since_last
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                return False, f"⏳ Wait {hours}h {minutes}m before retry #{attempts + 1} (next: {next_wait})"
            
            return True, f"✅ Retry #{attempts + 1} allowed (next wait: {next_wait})"
            
        except SQLAlchemyError as e:
            logger.error(f"Error checking answer cooldown: {e}")
            return True, "✅ Proceeding (error occurred)"
        finally:
            session.close()
    
    async def clear_monthly_leaderboard(self) -> None:
        """Clear monthly leaderboard data"""
        session = self.get_session()
        try:
            session.query(LeaderboardEntry).filter(
                LeaderboardEntry.period_type == 'monthly'
            ).delete()
            session.commit()
            logger.info("Monthly leaderboard data cleared")
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error clearing monthly leaderboard: {e}")
            raise
        finally:
            session.close()
    
    async def log_help_interaction(self, user_id: int, username: str, command: str) -> None:
        """Log help bot interaction"""
        session = self.get_session()
        try:
            ticket = HelpTicket(
                user_id=user_id,
                username=username,
                command=command,
                timestamp=datetime.utcnow()
            )
            session.add(ticket)
            session.commit()
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error logging help interaction: {e}")
        finally:
            session.close()
    
    def backup_to_json(self, backup_path: str = "data/backup") -> None:
        """Backup database to JSON files (for compatibility)"""
        import json
        os.makedirs(backup_path, exist_ok=True)
        
        session = self.get_session()
        try:
            # Backup users
            users = session.query(User).all()
            users_data = {
                "users": {
                    str(user.user_id): {
                        "user_id": user.user_id,
                        "username": user.username or '',
                        "first_name": user.first_name or '',
                        "total_questions_answered": user.total_questions_answered,
                        "total_correct_answers": user.total_correct_answers,
                        "total_points": user.total_points,
                        "overall_accuracy": user.overall_accuracy,
                        "last_activity": user.last_activity.isoformat() if user.last_activity else '',
                        "registration_date": user.registration_date.isoformat() if user.registration_date else ''
                    }
                    for user in users
                }
            }
            
            with open(f"{backup_path}/user_stats_backup.json", 'w') as f:
                json.dump(users_data, f, indent=2)
            
            logger.info(f"Database backed up to {backup_path}")
            
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
        finally:
            session.close()

# Global database instance
db = DatabaseManager()