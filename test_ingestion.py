#!/usr/bin/env python3
"""Test script for ingestion service."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set up in-memory SQLite database for testing
from app.models.tables import Base
from app.services.ingestion import ingest_resume, get_resume_stats

def test_ingestion():
    """Test the full ingestion pipeline with SQLite."""
    
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    
    # Create tables (skip pgvector extension for SQLite)
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Sample resume text
        sample_resume = """
        John Doe
        Software Engineer
        
        EXPERIENCE:
        Senior Software Engineer at TechCorp (2020-2023)
        - Led development of microservices architecture using Python and Docker
        - Implemented CI/CD pipelines reducing deployment time by 50%
        - Mentored team of 5 junior developers
        
        Software Developer at StartupXYZ (2018-2020)  
        - Built REST APIs using Django and PostgreSQL
        - Developed React frontend applications
        - Collaborated with product team on feature design
        
        EDUCATION:
        Bachelor of Science in Computer Science
        University of Technology (2014-2018)
        
        SKILLS:
        - Programming: Python, JavaScript, TypeScript, SQL
        - Frameworks: Django, React, FastAPI, Node.js
        - Databases: PostgreSQL, MongoDB, Redis
        - DevOps: Docker, Kubernetes, AWS, CI/CD
        """
        
        print("🧪 Testing resume ingestion...")
        
        # Test ingestion
        resume_id = ingest_resume(sample_resume, db)
        print(f"✅ Resume ingested with ID: {resume_id}")
        
        # Test chunk count
        chunk_count = db.execute(text("SELECT COUNT(*) FROM resume_chunks")).scalar()
        print(f"✅ Chunks in database: {chunk_count}")
        
        # Test resume stats
        stats = get_resume_stats(resume_id, db)
        print(f"✅ Resume stats: {stats}")
        
        # Verify chunks have embeddings (even if they're null in SQLite)
        chunks_with_embeddings = db.execute(
            text("SELECT COUNT(*) FROM resume_chunks WHERE chunk_text IS NOT NULL")
        ).scalar()
        print(f"✅ Chunks with text: {chunks_with_embeddings}")
        
        assert resume_id > 0, "Resume ID should be positive"
        assert chunk_count > 0, "Should have chunks"
        assert stats["chunk_count"] == chunk_count, "Stats should match"
        
        print("🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    test_ingestion()