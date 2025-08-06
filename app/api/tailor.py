"""Tailor API endpoints - the complete RAG pipeline."""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.retrieval import retrieve_chunks_for_resume
from app.services.generation import rewrite_chunks
from app.models.tables import Resume

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tailor", tags=["Resume Tailoring"])

class TailorRequest(BaseModel):
    """Request model for resume tailoring."""
    
    resume_id: int = Field(..., description="ID of the resume to tailor", example=1)
    jd_text: str = Field(..., description="Job description text to tailor the resume for", min_length=10)
    max_bullets: Optional[int] = Field(8, description="Maximum number of bullets to generate", ge=1, le=20)
    style: Optional[str] = Field("professional", description="Writing style", pattern="^(professional|concise|impact)$")
    retrieval_limit: Optional[int] = Field(12, description="Maximum chunks to retrieve", ge=1, le=50)

class TailorResponse(BaseModel):
    """Response model for resume tailoring."""
    
    resume_id: int
    tailored_bullets: list[str]
    cited_chunks: list[int]
    chunk_count: int
    metadata: Dict[str, Any]
    
@router.post("/", summary="Tailor resume to job description", response_model=TailorResponse)
async def tailor_resume(
    request: TailorRequest,
    db: Session = Depends(get_db)
) -> TailorResponse:
    """
    Tailor a resume to a specific job description using the complete RAG pipeline.
    
    This endpoint:
    1. Retrieves the most relevant resume chunks for the job description
    2. Uses GPT-4o to rewrite them into tailored bullets with citations
    3. Returns the finished resume section with cite tags
    
    Args:
        request: Tailor request with resume_id and job description
        db: Database session
        
    Returns:
        JSON response with tailored bullets and citations
        
    Raises:
        HTTPException: If resume not found, retrieval fails, or generation fails
    """
    logger.info(f"Tailoring resume {request.resume_id} for JD ({len(request.jd_text)} chars)")
    
    try:
        # 1. Validate resume exists
        resume = db.query(Resume).filter(Resume.id == request.resume_id).first()
        if not resume:
            raise HTTPException(
                status_code=404,
                detail=f"Resume {request.resume_id} not found"
            )
        
        logger.info(f"Found resume {request.resume_id} created at {resume.created_at}")
        
        # 2. Retrieve relevant chunks using our retrieval service
        logger.info(f"Retrieving up to {request.retrieval_limit} relevant chunks...")
        
        relevant_chunks = retrieve_chunks_for_resume(
            job_description=request.jd_text,
            resume_id=request.resume_id,
            limit=request.retrieval_limit,
            db=db
        )
        
        if not relevant_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"No relevant chunks found for resume {request.resume_id}. "
                       "Resume may be empty or job description may not match any content."
            )
        
        logger.info(f"Retrieved {len(relevant_chunks)} relevant chunks")
        
        # 3. Generate tailored bullets using our generation service
        logger.info(f"Generating tailored bullets with GPT-4o...")
        
        generation_result = rewrite_chunks(
            chunks=relevant_chunks,
            job_description=request.jd_text,
            max_bullets=request.max_bullets,
            style=request.style
        )
        
        logger.info(f"Generated {len(generation_result.tailored_bullets)} bullets")
        
        # 4. Prepare response with complete metadata
        response = TailorResponse(
            resume_id=request.resume_id,
            tailored_bullets=generation_result.tailored_bullets,
            cited_chunks=generation_result.cited_chunks,
            chunk_count=len(relevant_chunks),
            metadata={
                **generation_result.metadata,
                "retrieval": {
                    "chunks_retrieved": len(relevant_chunks),
                    "retrieval_limit": request.retrieval_limit,
                    "distance_range": {
                        "min": min(chunk.distance for chunk in relevant_chunks),
                        "max": max(chunk.distance for chunk in relevant_chunks)
                    } if relevant_chunks else None
                },
                "request": {
                    "style": request.style,
                    "max_bullets": request.max_bullets,
                    "jd_length": len(request.jd_text)
                },
                "resume": {
                    "id": resume.id,
                    "created_at": resume.created_at.isoformat(),
                    "original_length": len(resume.raw_text)
                }
            }
        )
        
        logger.info(f"✅ Successfully tailored resume {request.resume_id}")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Resume tailoring failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Resume tailoring failed: {str(e)}"
        )

@router.get("/{resume_id}/preview", summary="Preview available chunks for tailoring")
async def preview_chunks(
    resume_id: int,
    jd_text: str,
    limit: int = 5,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Preview the chunks that would be used for tailoring without generating bullets.
    
    Useful for debugging and understanding what content will be used.
    
    Args:
        resume_id: ID of the resume
        jd_text: Job description text
        limit: Number of chunks to preview
        db: Database session
        
    Returns:
        Preview of chunks with similarity scores
    """
    try:
        # Validate resume exists
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
        
        # Get chunks for preview
        chunks = retrieve_chunks_for_resume(
            job_description=jd_text,
            resume_id=resume_id,
            limit=limit,
            db=db
        )
        
        return {
            "resume_id": resume_id,
            "chunks_found": len(chunks),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "distance": round(chunk.distance, 4),
                    "text_preview": chunk.chunk_text[:200] + "..." if len(chunk.chunk_text) > 200 else chunk.chunk_text
                }
                for chunk in chunks
            ],
            "jd_length": len(jd_text)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chunk preview failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chunk preview failed: {str(e)}")

@router.get("/", summary="Get tailoring status and info")
async def get_tailor_info() -> Dict[str, Any]:
    """
    Get information about the tailoring service.
    
    Returns:
        Service information and status
    """
    return {
        "service": "Resume Tailoring API",
        "version": "1.0.0",
        "description": "Complete RAG pipeline: retrieval + GPT-4o generation",
        "endpoints": {
            "POST /tailor/": "Tailor resume to job description",
            "GET /tailor/{resume_id}/preview": "Preview chunks for tailoring",
            "GET /tailor/": "Service information"
        },
        "pipeline": [
            "1. Retrieve relevant resume chunks using local embeddings + pgvector",
            "2. Generate tailored bullets using GPT-4o with citation tracking",
            "3. Return formatted resume section with cite IDs"
        ],
        "supported_styles": ["professional", "concise", "impact"],
        "max_bullets_range": "1-20",
        "max_retrieval_limit": 50
    }
