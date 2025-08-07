"""Retrieval service for finding relevant resume chunks."""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import numpy as np

from config import config
from app.models.tables import ResumeChunk, Resume
from app.vectorstore.hf_embedder import embedder
from app.database import SessionLocal, DATABASE_URL

logger = logging.getLogger(__name__)

class RetrievalResult:
    """Container for retrieval results."""
    
    def __init__(self, chunk_id: int, resume_id: int, chunk_text: str, distance: float, metadata: Optional[Dict] = None):
        self.chunk_id = chunk_id
        self.resume_id = resume_id
        self.chunk_text = chunk_text
        self.distance = distance
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "chunk_id": self.chunk_id,
            "resume_id": self.resume_id,
            "chunk_text": self.chunk_text,
            "distance": self.distance,
            "metadata": self.metadata
        }
    
    def __repr__(self):
        return f"<RetrievalResult(chunk_id={self.chunk_id}, distance={self.distance:.4f})>"

def retrieve_relevant_chunks(
    job_description: str,
    resume_id: Optional[int] = None,
    limit: int = None,
    distance_threshold: float = None,
    db: Session = None
) -> List[RetrievalResult]:
    """
    Retrieve the most relevant resume chunks for a given job description.
    
    Args:
        job_description: The job description text to search against
        resume_id: Optional specific resume ID to search within (None = search all)
        limit: Maximum number of chunks to return (uses config.RETRIEVAL_LIMIT if None)
        distance_threshold: Maximum distance for results (uses config.DISTANCE_THRESHOLD if None)
        db: Database session (will create if not provided)
        
    Returns:
        List of RetrievalResult objects ordered by similarity (ascending distance)
        
    Raises:
        ValueError: If job description is empty or no results found
        RuntimeError: If database query fails
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        # Use config defaults if not specified
        if limit is None:
            limit = config.RETRIEVAL_LIMIT
        if distance_threshold is None:
            distance_threshold = config.DISTANCE_THRESHOLD
        
        logger.info(f"Starting retrieval for job description ({len(job_description)} chars)")
        
        # Validate input
        if not job_description.strip():
            raise ValueError("Job description cannot be empty")
        
        # 1. Generate embedding for the job description
        logger.info("Generating embedding for job description...")
        jd_embedding = embedder.encode_single(job_description.strip())
        
        expected_dim = 384  # MiniLM-L6-v2 embedding dimension
        if len(jd_embedding) != expected_dim:
            raise RuntimeError(f"Unexpected embedding dimension: {len(jd_embedding)} vs {expected_dim}")
        
        logger.info(f"Generated {len(jd_embedding)}-dimensional embedding")
        
        # 2. Handle PostgreSQL vs SQLite differently
        if "postgresql" in DATABASE_URL:
            # PostgreSQL with pgvector - use native distance operators
            base_query = """
            SELECT 
                rc.id as chunk_id,
                rc.resume_id,
                rc.chunk_text,
                rc.embedding <-> :query_embedding as distance,
                r.created_at
            FROM resume_chunks rc
            JOIN resumes r ON rc.resume_id = r.id
            """
            
            where_clause = ""
            params = {"query_embedding": jd_embedding}
            
            if resume_id is not None:
                where_clause = "WHERE rc.resume_id = :resume_id"
                params["resume_id"] = resume_id
            
            sql_query = f"""
            {base_query}
            {where_clause}
            ORDER BY distance ASC
            LIMIT :limit
            """
            
            params["limit"] = limit
            
            logger.info(f"Executing PostgreSQL pgvector similarity search (resume_id={resume_id}, limit={limit})")
            
            result = db.execute(text(sql_query), params)
            rows = result.fetchall()
            
            if not rows:
                logger.warning("No chunks found matching the query")
                return []
            
            # Process PostgreSQL results
            retrieval_results = []
            for row in rows:
                if row.distance <= distance_threshold:
                    result_obj = RetrievalResult(
                        chunk_id=row.chunk_id,
                        resume_id=row.resume_id,
                        chunk_text=row.chunk_text,
                        distance=float(row.distance),
                        metadata={
                            "created_at": None  # Chunk doesn't have created_at field
                        }
                    )
                    retrieval_results.append(result_obj)
        else:
            # SQLite - retrieve all embeddings and compute similarity in Python
            base_query = """
            SELECT 
                rc.id as chunk_id,
                rc.resume_id,
                rc.chunk_text,
                rc.embedding,
                r.created_at
            FROM resume_chunks rc
            JOIN resumes r ON rc.resume_id = r.id
            """
            
            where_clause = ""
            params = {}
            
            if resume_id is not None:
                where_clause = "WHERE rc.resume_id = :resume_id"
                params["resume_id"] = resume_id
            
            sql_query = f"{base_query} {where_clause}"
            
            logger.info(f"Executing SQLite similarity search (resume_id={resume_id})")
            
            result = db.execute(text(sql_query), params)
            rows = result.fetchall()
            
            if not rows:
                logger.warning("No chunks found matching the query")
                return []
            
            # Parse all embeddings and compute similarity vectorized
            retrieval_results = []
            jd_embedding_np = np.array(jd_embedding)
            
            # Collect all embeddings and metadata
            chunk_embeddings = []
            chunk_metadata = []
            
            for row in rows:
                try:
                    # Parse JSON embedding
                    if isinstance(row.embedding, str):
                        chunk_embedding = np.array(json.loads(row.embedding))
                    else:
                        chunk_embedding = np.array(row.embedding)
                    
                    chunk_embeddings.append(chunk_embedding)
                    chunk_metadata.append({
                        'chunk_id': row.chunk_id,
                        'resume_id': row.resume_id,
                        'chunk_text': row.chunk_text
                    })
                except Exception as e:
                    logger.warning(f"Failed to process chunk {row.chunk_id}: {e}")
                    continue
            
            if not chunk_embeddings:
                logger.warning("No valid embeddings found")
                return []
            
            # Vectorized similarity computation
            chunk_embeddings_matrix = np.vstack(chunk_embeddings)
            
            # Choose similarity metric from config
            similarity_metric = config.SIMILARITY_METRIC.lower()
            
            if similarity_metric == "cosine":
                # Cosine similarity: dot product of normalized vectors
                # Since embeddings are already normalized, this is just dot product
                similarities = np.dot(chunk_embeddings_matrix, jd_embedding_np)
                # Convert to distance (1 - similarity) for consistency
                distances = 1.0 - similarities
            elif similarity_metric == "euclidean":
                # Euclidean distance
                distances = np.linalg.norm(chunk_embeddings_matrix - jd_embedding_np, axis=1)
            elif similarity_metric == "dot_product":
                # Negative dot product to use as distance (higher dot product = lower distance)
                similarities = np.dot(chunk_embeddings_matrix, jd_embedding_np)
                distances = -similarities
            else:
                logger.warning(f"Unknown similarity metric '{similarity_metric}', defaulting to cosine")
                similarities = np.dot(chunk_embeddings_matrix, jd_embedding_np)
                distances = 1.0 - similarities
            
            # Create results for chunks within threshold
            for i, distance in enumerate(distances):
                if distance <= distance_threshold:
                    metadata = chunk_metadata[i]
                    result_obj = RetrievalResult(
                        chunk_id=metadata['chunk_id'],
                        resume_id=metadata['resume_id'],
                        chunk_text=metadata['chunk_text'],
                        distance=float(distance),
                        metadata={
                            "created_at": None,
                            "similarity_metric": similarity_metric
                        }
                    )
                    retrieval_results.append(result_obj)
            
            # Sort by distance (ascending) and limit results
            retrieval_results.sort(key=lambda x: x.distance)
            retrieval_results = retrieval_results[:limit]
        
        logger.info(f"Retrieved {len(retrieval_results)} chunks (filtered by distance <= {distance_threshold})")
        
        # Log some stats
        if retrieval_results:
            distances = [r.distance for r in retrieval_results]
            logger.info(f"Distance range: {min(distances):.4f} - {max(distances):.4f}")
        
        return retrieval_results
        
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise RuntimeError(f"Retrieval failed: {str(e)}")
    
    finally:
        if close_db:
            db.close()

def retrieve_chunks_for_resume(
    job_description: str,
    resume_id: int,
    limit: int = 12,
    db: Session = None
) -> List[RetrievalResult]:
    """
    Convenience function to retrieve chunks for a specific resume.
    
    Args:
        job_description: Job description text
        resume_id: Specific resume ID to search within
        limit: Maximum number of chunks to return
        db: Database session
        
    Returns:
        List of RetrievalResult objects
    """
    return retrieve_relevant_chunks(
        job_description=job_description,
        resume_id=resume_id,
        limit=limit,
        db=db
    )

def retrieve_top_chunks_all_resumes(
    job_description: str,
    limit: int = 12,
    db: Session = None
) -> List[RetrievalResult]:
    """
    Convenience function to retrieve top chunks across all resumes.
    
    Args:
        job_description: Job description text
        limit: Maximum number of chunks to return
        db: Database session
        
    Returns:
        List of RetrievalResult objects
    """
    return retrieve_relevant_chunks(
        job_description=job_description,
        resume_id=None,
        limit=limit,
        db=db
    )

# Example usage function for REPL testing
def test_retrieval(job_description: str = None, resume_id: int = None) -> None:
    """
    Test function for REPL usage.
    
    Args:
        job_description: Test job description (uses default if None)
        resume_id: Optional resume ID to test with
    """
    if job_description is None:
        job_description = """
        We are looking for a Senior Software Engineer with expertise in Python, 
        machine learning, and web development. The ideal candidate should have 
        experience with FastAPI, React, and cloud platforms. Strong background 
        in data science and AI/ML is preferred.
        """
    
    print(f"🔍 Testing retrieval with job description ({len(job_description)} chars)")
    
    try:
        results = retrieve_relevant_chunks(
            job_description=job_description,
            resume_id=resume_id,
            limit=5  # Smaller limit for testing
        )
        
        print(f"✅ Retrieved {len(results)} chunks")
        
        for i, result in enumerate(results, 1):
            print(f"\n--- Chunk {i} (ID: {result.chunk_id}, Distance: {result.distance:.4f}) ---")
            print(result.chunk_text[:200] + "..." if len(result.chunk_text) > 200 else result.chunk_text)
        
        if not results:
            print("⚠️  No chunks found - make sure you have resume data in the database")
        
        return results
        
    except Exception as e:
        print(f"❌ Retrieval test failed: {e}")
        return []

if __name__ == "__main__":
    # This part is for testing the retrieval service directly
    print("🧪 Testing retrieval service...")
    test_retrieval()
