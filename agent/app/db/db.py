# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from loguru import logger
from app.models.feedback import Base, RCAAnalysisModel, RCAFeedbackModel

# Create MySQL SQLAlchemy Engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # Automatically reconnects if MySQL drops idle connections
    pool_recycle=3600,       # Recycles connections hourly
    echo=False
)

# Session factory for API dependency injection
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes table schema inside the target MySQL database."""
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {str(e)}")
        raise e

def get_db():
    """FastAPI generator dependency providing isolated DB sessions per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()