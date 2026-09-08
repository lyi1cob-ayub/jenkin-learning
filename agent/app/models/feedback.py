from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime


Base = declarative_base()

class RCAAnalysisModel(Base):
    """
    Stores agent execution state (using the parsed log snippet from state)
    so feedback requests can hydrate input data without bloated URLs.
    """
    __tablename__ = "rca_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    build_id = Column(String(100), nullable=False, index=True)
    job_name = Column(String(255), nullable=False)
    predicted_failure_type = Column(String(50), nullable=True)
    parsed_log_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RCAFeedbackModel(Base):
    """
    SQLAlchemy ORM Model to capture developer feedback for golden dataset curation.
    """
    __tablename__ = "rca_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    build_id = Column(String(100), nullable=False, index=True)
    job_name = Column(String(255), nullable=False)
    user_email = Column(String(255), nullable=True, default="unknown_user@company.com")
    # Golden Dataset Specific Fields
    predicted_failure_type = Column(String(50), nullable=True)  # What LLM predicted (CODE / INFRASTRUCTURE)
    rating = Column(String(10), nullable=False)                 # UP / DOWN
    corrected_failure_type = Column(String(50), nullable=True)  # Ground truth if LLM was wrong
    user_comments = Column(Text, nullable=True)                 # Developer feedback / correct root cause
    
    raw_log_snippet = Column(Text, nullable=True)               # Store original trace for Golden Dataset
    created_at = Column(DateTime, default=datetime.utcnow)