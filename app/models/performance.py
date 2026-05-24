"""Performance review and goal models."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, Float
from app.database import Base


class ReviewCycle(str, enum.Enum):
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    ANNUAL = "annual"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    SELF_REVIEW = "self_review"
    MANAGER_REVIEW = "manager_review"
    COMPLETED = "completed"


class GoalStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False)
    reviewer_id = Column(Integer, nullable=True)
    cycle = Column(SAEnum(ReviewCycle), default=ReviewCycle.ANNUAL)
    period = Column(String, nullable=True)  # e.g., "Q1 2024", "2024"
    status = Column(SAEnum(ReviewStatus), default=ReviewStatus.PENDING)
    
    # Ratings (1-5)
    technical_rating = Column(Float, nullable=True)
    communication_rating = Column(Float, nullable=True)
    leadership_rating = Column(Float, nullable=True)
    teamwork_rating = Column(Float, nullable=True)
    innovation_rating = Column(Float, nullable=True)
    overall_rating = Column(Float, nullable=True)
    
    self_review = Column(Text, nullable=True)
    manager_review = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    improvements = Column(Text, nullable=True)
    recommendation = Column(String, nullable=True)  # promote, increment, pip, no_change
    # 360° Feedback
    peer_feedback = Column(Text, nullable=True)       # JSON list of peer comments
    peer_rating = Column(Float, nullable=True)         # avg peer rating
    subordinate_feedback = Column(Text, nullable=True) # JSON
    subordinate_rating = Column(Float, nullable=True)
    ai_review_draft = Column(Text, nullable=True)      # AI-generated review draft
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(DateTime, nullable=True)
    status = Column(SAEnum(GoalStatus), default=GoalStatus.NOT_STARTED)
    progress = Column(Integer, default=0)  # 0-100
    priority = Column(String, default="medium")  # low, medium, high
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
