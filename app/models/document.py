"""Document management model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, Boolean
from app.database import Base


class DocumentCategory(str, enum.Enum):
    OFFER_LETTER       = "offer_letter"
    APPOINTMENT_LETTER = "appointment_letter"
    SALARY_REVISION    = "salary_revision"
    EXPERIENCE_LETTER  = "experience_letter"
    RELIEVING_LETTER   = "relieving_letter"
    NDA                = "nda"
    POLICY             = "policy"
    ID_PROOF           = "id_proof"
    ADDRESS_PROOF      = "address_proof"
    EDUCATIONAL        = "educational"
    PAN_CARD           = "pan_card"
    AADHAR             = "aadhar"
    BANK_PROOF         = "bank_proof"
    PAYSLIP            = "payslip"
    APPRAISAL          = "appraisal"
    WARNING_LETTER     = "warning_letter"
    OTHER              = "other"


class DocumentStatus(str, enum.Enum):
    ACTIVE   = "active"
    ARCHIVED = "archived"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {'extend_existing': True}

    id              = Column(Integer, primary_key=True, index=True)
    employee_id     = Column(Integer, nullable=True)   # None = company-wide
    uploaded_by     = Column(Integer, nullable=True)
    title           = Column(String, nullable=False)
    description     = Column(Text, nullable=True)
    category        = Column(SAEnum(DocumentCategory), default=DocumentCategory.OTHER)
    status          = Column(SAEnum(DocumentStatus), default=DocumentStatus.ACTIVE)
    file_name       = Column(String, nullable=False)
    file_path       = Column(String, nullable=False)
    file_size       = Column(Integer, default=0)
    file_type       = Column(String, nullable=True)
    is_confidential = Column(Boolean, default=False)
    tags            = Column(String, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
