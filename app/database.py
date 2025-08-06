"""Database configuration and connection."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import config
from .models.tables import Base

# Database URL from config
DATABASE_URL = config.DATABASE_URL

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all tables using SQLAlchemy metadata."""
    # Enable pgvector extension (only for PostgreSQL)
    if "postgresql" in DATABASE_URL:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        print("✅ PostgreSQL vector extension enabled")
    else:
        print("✅ Using SQLite (no vector extension needed)")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # Test table creation
    create_tables()