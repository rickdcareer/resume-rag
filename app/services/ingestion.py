"""Resume ingestion service - chunking, embedding, and storage."""

import re
from typing import List, Tuple
from sqlalchemy.orm import Session

from config import config
from ..database import SessionLocal
from ..models.tables import Resume, ResumeChunk
from ..vectorstore.hf_embedder import embedder
import logging

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Clean and normalize resume text."""
    # Remove extra whitespace and normalize line breaks
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)]', ' ', text)
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_resume_text(text: str, max_chunk_size: int = None) -> List[str]:
    """
    Split resume text into chunks for embedding.
    
    Args:
        text: Resume text to chunk
        max_chunk_size: Maximum words per chunk (uses config.CHUNK_MAX_WORDS if None)
        
    Returns:
        List of text chunks
    """
    # Use config default if not specified
    if max_chunk_size is None:
        max_chunk_size = config.CHUNK_MAX_WORDS
    
    # Clean the text first
    cleaned_text = clean_text(text)
    
    # Split by sentences first, then group into chunks
    sentences = re.split(r'[.!?]+', cleaned_text)
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        word_count = len(sentence.split())
        
        # If adding this sentence would exceed the limit, save current chunk
        if current_word_count + word_count > max_chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk).strip())
            current_chunk = [sentence]
            current_word_count = word_count
        else:
            current_chunk.append(sentence)
            current_word_count += word_count
    
    # Add the last chunk if it has content
    if current_chunk:
        chunks.append(' '.join(current_chunk).strip())
    
    # Filter out very short chunks (less than 10 words)
    chunks = [chunk for chunk in chunks if len(chunk.split()) >= 10]
    
    logger.info(f"Split text into {len(chunks)} chunks")
    return chunks

def ingest_resume(resume_text: str, db: Session = None) -> int:
    """
    Complete resume ingestion pipeline.
    
    Args:
        resume_text: Raw resume text to ingest
        db: Optional database session (will create if not provided)
        
    Returns:
        New resume_id
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        logger.info("Starting resume ingestion...")
        
        # 1. Clean and store the raw resume
        cleaned_text = clean_text(resume_text)
        
        # Create resume record
        resume = Resume(raw_text=cleaned_text)
        db.add(resume)
        db.flush()  # Get the ID without committing
        resume_id = resume.id
        
        logger.info(f"Created resume record with ID: {resume_id}")
        
        # 2. Chunk the resume text
        chunks = chunk_resume_text(cleaned_text)
        
        if not chunks:
            raise ValueError("No valid chunks created from resume text")
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # 3. Generate embeddings for all chunks
        logger.info("Generating embeddings...")
        embeddings = embedder.encode(chunks)
        
        if len(embeddings) != len(chunks):
            raise ValueError(f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")
        
        # 4. Create resume chunk records
        chunk_records = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_record = ResumeChunk(
                resume_id=resume_id,
                chunk_text=chunk_text,
                embedding=embedding
            )
            chunk_records.append(chunk_record)
        
        # Bulk insert chunks
        db.add_all(chunk_records)
        db.commit()
        
        logger.info(f"✅ Successfully ingested resume {resume_id} with {len(chunk_records)} chunks")
        return resume_id
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during ingestion: {e}")
        raise
    finally:
        if close_db:
            db.close()

def get_resume_stats(resume_id: int, db: Session = None) -> dict:
    """
    Get statistics for an ingested resume.
    
    Args:
        resume_id: Resume ID to get stats for
        db: Optional database session
        
    Returns:
        Dictionary with resume statistics
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        # Get resume
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")
        
        # Count chunks
        chunk_count = db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume_id).count()
        
        # Get text stats
        original_words = len(resume.raw_text.split())
        
        return {
            "resume_id": resume_id,
            "created_at": resume.created_at,
            "original_word_count": original_words,
            "chunk_count": chunk_count,
            "avg_words_per_chunk": original_words / chunk_count if chunk_count > 0 else 0
        }
        
    finally:
        if close_db:
            db.close()
