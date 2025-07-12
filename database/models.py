"""
Database models for Atenu Quiz Bot
Using SQLAlchemy with SQLite for local storage
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User table - stores basic user information and overall stats"""
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=True)
    total_quizzes_taken = Column(Integer, default=0)
    total_questions_answered = Column(Integer, default=0)
    total_correct_answers = Column(Integer, default=0)
    total_points = Column(Integer, default=0)
    overall_accuracy = Column(Float, default=0.0)
    last_activity = Column(DateTime, default=datetime.utcnow)
    registration_date = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    answers = relationship("UserAnswer", back_populates="user")
    leaderboard_entries = relationship("LeaderboardEntry", back_populates="user")

class UserAnswer(Base):
    """User answers table - stores individual question responses"""
    __tablename__ = 'user_answers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    question_id = Column(Integer, nullable=False)
    selected_option = Column(Integer, nullable=False)
    correct_answer = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    points = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="answers")

class LeaderboardEntry(Base):
    """Leaderboard entries - daily, weekly, monthly rankings"""
    __tablename__ = 'leaderboard_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    period_type = Column(String(10), nullable=False)  # 'daily', 'weekly', 'monthly'
    period_key = Column(String(20), nullable=False)   # '2025-07-12', '2025-W28', '2025-07'
    points = Column(Integer, default=0)
    questions_answered = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    
    # Relationship
    user = relationship("User", back_populates="leaderboard_entries")
    
    # Composite index for fast queries
    __table_args__ = (
        {'mysql_engine': 'InnoDB'}
    )

class HelpTicket(Base):
    """Help bot interactions - track user interactions with help bot"""
    __tablename__ = 'help_tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(50), nullable=True)
    command = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)