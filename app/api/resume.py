"""Resume upload API endpoints."""

import logging
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import PyPDF2
import io

from app.database import get_db
from app.services.ingestion import ingest_resume

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["Resume"])

def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_content: Raw PDF file content as bytes
        
    Returns:
        Extracted text content as string
        
    Raises:
        ValueError: If PDF parsing fails
    """
    try:
        pdf_file = io.BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_content = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text_content += page.extract_text() + "\n"
        
        # Clean up the extracted text
        text_content = text_content.strip()
        
        if not text_content:
            raise ValueError("No text content could be extracted from PDF")
            
        logger.info(f"Successfully extracted {len(text_content)} characters from PDF")
        return text_content
        
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")

def process_uploaded_file(file: UploadFile) -> str:
    """
    Process an uploaded file and extract text content.
    
    Args:
        file: FastAPI UploadFile object
        
    Returns:
        Extracted text content
        
    Raises:
        HTTPException: If file processing fails
    """
    try:
        # Read file content
        content = file.file.read()
        
        if file.content_type == "application/pdf":
            # Handle PDF files
            text_content = extract_text_from_pdf(content)
        elif file.content_type == "text/plain":
            # Handle plain text files
            text_content = content.decode('utf-8')
        else:
            # Try to decode as text anyway for common formats
            try:
                text_content = content.decode('utf-8')
                logger.info(f"Successfully decoded file as UTF-8 text (content-type: {file.content_type})")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}. Please upload PDF or text files."
                )
        
        if not text_content.strip():
            raise HTTPException(
                status_code=400,
                detail="File appears to be empty or contains no readable text"
            )
            
        logger.info(f"Successfully processed file: {file.filename} ({len(text_content)} characters)")
        return text_content.strip()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File processing error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process uploaded file: {str(e)}"
        )

@router.post("/", summary="Upload resume", response_model=Dict[str, Any])
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (PDF or text)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload and process a resume file.
    
    Accepts PDF or plain text files, extracts text content, chunks it,
    generates embeddings, and stores everything in the database.
    
    Args:
        file: Resume file to upload (PDF or text format)
        db: Database session
        
    Returns:
        JSON response with resume ID and processing stats
        
    Raises:
        HTTPException: If file processing or ingestion fails
    """
    logger.info(f"Received resume upload: {file.filename} ({file.content_type})")
    
    try:
        # Extract text content from uploaded file
        resume_text = process_uploaded_file(file)
        
        logger.info(f"🚀 API UPLOAD: Extracted text length: {len(resume_text)} chars")
        logger.info(f"🚀 API UPLOAD: Text preview: {repr(resume_text[:200])}")
        
        # Ingest the resume using our ingestion service
        logger.info(f"🚀 API UPLOAD: Calling ingest_resume...")
        resume_id = ingest_resume(resume_text, db)
        logger.info(f"🚀 API UPLOAD: ingest_resume returned ID: {resume_id}")
        
        # Get some stats for the response
        from app.models.tables import Resume, ResumeChunk
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        chunk_count = db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume_id).count()
        
        response_data = {
            "id": resume_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "text_length": len(resume_text),
            "chunk_count": chunk_count,
            "created_at": resume.created_at.isoformat() if resume else None,
            "status": "success",
            "message": f"Resume successfully uploaded and processed into {chunk_count} chunks"
        }
        
        logger.info(f"Successfully uploaded resume {resume_id}: {file.filename}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Resume upload failed: {str(e)}"
        )

@router.get("/{resume_id}", summary="Get resume info")
async def get_resume_info(
    resume_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get information about a specific resume.
    
    Args:
        resume_id: ID of the resume to retrieve
        db: Database session
        
    Returns:
        Resume information including stats
        
    Raises:
        HTTPException: If resume not found
    """
    from app.models.tables import Resume, ResumeChunk
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
    
    chunk_count = db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume_id).count()
    
    return {
        "id": resume.id,
        "text_length": len(resume.raw_text),
        "chunk_count": chunk_count,
        "created_at": resume.created_at.isoformat(),
        "preview": resume.raw_text[:200] + "..." if len(resume.raw_text) > 200 else resume.raw_text
    }
