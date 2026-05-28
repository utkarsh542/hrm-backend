"""Approval workflow models."""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Enum as SQLEnum
from datetime import datetime
from app.database import Base
import enum


class ApprovalStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    escalated = "escalated"


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    steps = Column(JSON, nullable=False)
    auto_escalation_hours = Column(Integer, default=48)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    requested_by = Column(Integer, nullable=False, index=True)
    current_step = Column(Integer, default=1)
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.pending, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    approver_id = Column(Integer, nullable=True, index=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    acted_at = Column(DateTime, nullable=True)
