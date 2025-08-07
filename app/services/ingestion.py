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
    """Clean and normalize resume text while preserving structure."""
    # Replace multiple whitespace with single spaces, but preserve line breaks for now
    text = re.sub(r'[ \t]+', ' ', text)  # Only compress spaces/tabs, not newlines
    text = re.sub(r'\n+', '\n', text)     # Compress multiple newlines to single
    
    # Remove special characters but keep basic punctuation and preserve periods
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\n@]', ' ', text)
    
    # Clean up extra spaces again
    text = re.sub(r' +', ' ', text)
    text = text.strip()
    
    return text

def chunk_resume_text(text: str, max_chunk_size: int = None) -> List[str]:
    """
    Split resume text into chunks for embedding, preserving resume structure.
    
    Args:
        text: Resume text to chunk
        max_chunk_size: Maximum words per chunk (uses config.CHUNK_MAX_WORDS if None)
        
    Returns:
        List of text chunks
    """
    logger.info(f"🔧 CHUNKING: Starting chunk_resume_text with {len(text)} chars input")
    
    # Use config default if not specified
    if max_chunk_size is None:
        max_chunk_size = config.CHUNK_MAX_WORDS
    
    logger.info(f"🔧 CHUNKING: Using max_chunk_size = {max_chunk_size}")
    
    # Clean the text first (preserves structure)
    cleaned_text = clean_text(text)
    logger.info(f"🔧 CHUNKING: After cleaning: {len(cleaned_text)} chars")
    logger.info(f"🔧 CHUNKING: Cleaned text preview: {repr(cleaned_text[:200])}")
    
    # Try to split by major sections first (based on common resume structure)
    # Look for section headers like EXPERIENCE, EDUCATION, SKILLS, etc.
    section_pattern = r'\n(?=[A-Z][A-Z\s]{3,})\n*'
    sections = re.split(section_pattern, cleaned_text)
    
    logger.info(f"🔧 CHUNKING: Split into {len(sections)} sections")
    for i, section in enumerate(sections):
        logger.info(f"🔧 CHUNKING: Section {i+1}: {len(section)} chars, preview: {repr(section[:100])}")
    
    chunks = []
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Count words in this section
        section_words = len(section.split())
        
        if section_words <= max_chunk_size:
            # Section fits in one chunk
            if section_words >= 10:  # Only keep chunks with enough content
                chunks.append(section)
        else:
            # Section too large, split by sentences and/or line breaks
            # Split by periods, exclamation marks, question marks, or double newlines
            sentences = re.split(r'[.!?]+|\n\n+', section)
            
            current_chunk = []
            current_word_count = 0
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                word_count = len(sentence.split())
                
                # If adding this sentence would exceed the limit, save current chunk
                if current_word_count + word_count > max_chunk_size and current_chunk:
                    chunk_text = ' '.join(current_chunk).strip()
                    if len(chunk_text.split()) >= 10:  # Only keep substantial chunks
                        chunks.append(chunk_text)
                    current_chunk = [sentence]
                    current_word_count = word_count
                else:
                    current_chunk.append(sentence)
                    current_word_count += word_count
            
            # Add the last chunk if it has content
            if current_chunk:
                chunk_text = ' '.join(current_chunk).strip()
                if len(chunk_text.split()) >= 10:
                    chunks.append(chunk_text)
    
    # If no good chunks found, fall back to simple word-based chunking
    if not chunks:
        words = cleaned_text.split()
        for i in range(0, len(words), max_chunk_size):
            chunk_words = words[i:i + max_chunk_size]
            if len(chunk_words) >= 10:
                chunks.append(' '.join(chunk_words))
    
    logger.info(f"🔧 CHUNKING: FINAL RESULT: {len(chunks)} chunks created")
    for i, chunk in enumerate(chunks):
        logger.info(f"🔧 CHUNKING: Final chunk {i+1}: {len(chunk)} chars, {len(chunk.split())} words")
        logger.info(f"🔧 CHUNKING: Final chunk {i+1} preview: {repr(chunk[:150])}")
    
    logger.info(f"Split text into {len(chunks)} chunks (avg {sum(len(c.split()) for c in chunks) // len(chunks) if chunks else 0} words per chunk)")
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
