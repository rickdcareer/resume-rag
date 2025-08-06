# Resume RAG System - Technical Overview

## 🎯 System Purpose

This is a **working, Resume RAG (Retrieval Augmented Generation) API** that:
- Takes resume files (PDF or text) and job descriptions
- Uses local embeddings to find relevant resume sections
- Generates tailored resume bullets using OpenAI GPT-4o
- Provides cited outputs showing which resume chunks were used

**Current Status**: Fully functional with real implementation, no stubs or placeholder code.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Resume RAG API                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   FastAPI   │  │  SQLAlchemy │  │   OpenAI GPT-4o     │ │
│  │   Uvicorn   │  │   SQLite    │  │   Text Generation   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ HuggingFace │  │  Vector     │  │   Citation          │ │
│  │ MiniLM-L6v2 │  │  Search &   │  │   Parsing &         │ │
│  │ Embeddings  │  │  Retrieval  │  │   Result Tracking   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 End-to-End Flow

### Phase 1: Resume Upload & Processing

```
1. CLIENT POST /resume/ (PDF or text file)
   │
   ▼
2. app/api/resume.py:upload_resume()
   │ • Validates file format and size (10MB max)
   │ • Extracts text using PyPDF2 (for PDFs) or UTF-8 decode
   │ • Calls ingestion service
   │
   ▼
3. app/services/ingestion.py:ingest_resume()
   │ • clean_text() - normalizes whitespace
   │ • chunk_resume_text() - splits by sentences into ~200 word chunks
   │ • Creates Resume database record
   │
   ▼
4. app/vectorstore/hf_embedder.py:encode()
   │ • Uses sentence-transformers/all-MiniLM-L6-v2 model
   │ • Generates 384-dimensional embeddings
   │ • Normalizes vectors for cosine similarity
   │
   ▼
5. Database Storage (SQLAlchemy + SQLite)
   │ • Saves Resume record with raw text and timestamp
   │ • Saves ResumeChunk records with text and JSON embeddings
   │
   ▼
6. Response: {id: 1, chunk_count: 3, text_length: 1500}
```

### Phase 2: Resume Tailoring

```
1. CLIENT POST /tailor/ {resume_id: 1, jd_text: "..."}
   │
   ▼
2. app/api/tailor.py:tailor_resume()
   │ • Validates resume exists in database
   │ • Calls retrieval service
   │
   ▼
3. app/services/retrieval.py:retrieve_relevant_chunks()
   │ • Embeds job description using same MiniLM model
   │ • Searches database using cosine distance in Python
   │ • Returns top 12 most relevant chunks
   │
   ▼
4. app/services/generation.py:generate_tailored_bullets()
   │ • Constructs prompt with retrieved chunks + job description
   │ • Calls OpenAI GPT-4o API (temp=0.7, max_tokens=1000)
   │ • Parses citations [C1], [C2] from response
   │
   ▼
5. Response: {bullets: [...], cited_chunks: [0,1,2]}
```

## ⚙️ Core Components

### 1. Configuration (`config.py`)

**Purpose**: Centralized settings management

**Configuration Values**:
- Database: SQLite file at `./resume_rag.db`
- OpenAI: GPT-4o model with 0.7 temperature, 1000 max tokens
- Embeddings: sentence-transformers/all-MiniLM-L6-v2 with 384 dimensions
- Processing: 200-word chunks, 12 retrieval limit

**Key Features**:
- JSON config file support with environment variable overrides
- Security: API keys from environment variables only
- No hardcoded sensitive values

### 2. Database Layer (`app/models/tables.py`)

**Purpose**: Persistent storage with vector support

**Tables**:
- `Resume`: Stores ID, raw text, creation timestamp, with relationship to chunks
- `ResumeChunk`: Stores ID, resume foreign key, chunk text, and JSON embedding data

**Key Features**:
- SQLite database with JSON column for 384-dimensional embeddings
- Proper foreign key relationships with cascade deletes
- Simple schema optimized for vector similarity search

### 3. Embedding Service (`app/vectorstore/hf_embedder.py`)

**Purpose**: Local, cost-free text embeddings

**Functions**:
- `HuggingFaceEmbedder.__init__()`: Downloads and loads sentence-transformers/all-MiniLM-L6-v2 model (~90MB)
- `encode()`: Takes list of text strings, returns 384-dimensional normalized vector embeddings

**Key Features**:
- No external API costs for embeddings
- Consistent 384-dimensional vectors
- Normalization for cosine similarity
- Batch processing capability

### 4. Ingestion Service (`app/services/ingestion.py`)

**Purpose**: Transform raw resume text into searchable chunks

**Functions**:
- `clean_text()`: Normalizes whitespace using regex `r'\s+'` replacement
- `chunk_resume_text()`: Splits by sentences using `r'[.!?]+'`, groups into 200-word chunks, filters chunks under 10 words
- `ingest_resume()`: Orchestrates text cleaning, Resume record creation, chunking, embedding generation, and database storage

**Implementation Details**:
- Sentence splitting using regex pattern for punctuation
- Word-based chunking with 200-word target
- Minimum 10 words per chunk filter
- Transaction safety for database operations

### 5. Retrieval Service (`app/services/retrieval.py`)

**Purpose**: Find relevant resume chunks for job descriptions

**Functions**:
- `retrieve_relevant_chunks()`: Embeds job description, queries database for chunks, calculates cosine distances in Python, returns top 12 matches
- `get_embedder()`: Returns singleton HuggingFace embedder instance

**Implementation Details**:
- SQLite-compatible cosine distance calculation using numpy
- JSON embedding deserialization from database
- Configurable result limit (default: 12)
- Distance threshold filtering

### 6. Generation Service (`app/services/generation.py`)

**Purpose**: Generate tailored resume bullets using GPT-4o

**Functions**:
- `generate_tailored_bullets()`: Constructs prompt with chunks and job description, calls OpenAI API, parses response
- `parse_bullets_and_citations()`: Extracts bullet points and citation references from LLM response using regex
- `get_generator()`: Returns singleton ResumeGenerator instance

**Implementation Details**:
- OpenAI client v1.99.1 with error handling
- Citation parsing using regex pattern `r'\[C(\d+)\]'`
- Bullet point extraction from structured LLM response
- Chunk index tracking for citation purposes

## 🌐 API Documentation

### Health Check
- **GET /health** → `{"status": "ok"}`

### Resume Upload
- **POST /resume/**
  - **Input**: Multipart form with file (PDF or text)
  - **Max Size**: 10MB
  - **Output**: `{id: int, text_length: int, chunk_count: int}`
  - **File Processing**: PyPDF2 for PDFs, UTF-8 decode for text

### Resume Tailoring
- **POST /tailor/**
  - **Input**: `{resume_id: int, jd_text: string}`
  - **Output**: `{bullets: string[], cited_chunks: int[]}`
  - **Processing**: Retrieval → OpenAI GPT-4o → Citation parsing

### Interactive Documentation
- **GET /docs** → Swagger UI (FastAPI auto-generated)

## 🚀 Deployment

### Current Method: Podman Container

```bash
# 1. Build pre-configured image
python build_image.py

# 2. One-click startup (handles everything)
python start.py

# 3. Manual container run
podman run -d --name resume-api \
  -p 8000:8000 \
  -v ./:/app \
  -e OPENAI_API_KEY=your-key \
  resume-rag-ready:latest
```

### Dependencies (Poetry)
- Python 3.11+, FastAPI 0.110, Uvicorn 0.29, SQLAlchemy 2.0
- sentence-transformers 2.6, torch 2.2, PyPDF2 3.0
- openai 1.12+, python-multipart 0.0.9, requests 2.31

### Environment Requirements
- **Python**: 3.11+
- **OpenAI API Key**: Required for GPT-4o
- **Storage**: ~300KB SQLite database
- **Memory**: ~500MB (for transformer model)

## 🎯 Technical Achievements

### RAG Implementation
✅ **Vector Similarity Search**: Cosine distance calculation in Python  
✅ **Local Embeddings**: HuggingFace sentence-transformers (no API costs)  
✅ **Chunking Strategy**: Sentence-based splitting with word limits  
✅ **Citation Tracking**: LLM response parsing with chunk references  

### Production Features
✅ **File Upload**: PDF parsing with PyPDF2, text file support  
✅ **Error Handling**: Comprehensive exception handling and logging  
✅ **Database**: SQLAlchemy ORM with SQLite backend  
✅ **API Documentation**: FastAPI auto-generated Swagger UI  
✅ **Containerization**: Podman/Docker support with one-click startup  

### Code Quality
✅ **Type Hints**: Full Python type annotations  
✅ **Logging**: Structured logging throughout application  
✅ **Configuration**: Environment-based config management  
✅ **Testing**: Smoke test script for end-to-end validation  

## 🧪 Testing

### Smoke Test (`scripts/smoke_demo.py`)
```bash
python scripts/smoke_demo.py
```

**Test Coverage**:
1. API health check
2. Resume upload (sample_resume.txt)
3. Resume tailoring (sample_jd.txt)
4. Output validation and file saving
5. Citation verification

**Sample Output**:
- Generated 8 tailored bullet points
- Cited 2 resume chunks
- Saved to `samples/output/tailored_resume_YYYYMMDD_HHMMSS.txt`

### Manual Testing
- Health check: GET request to `/health` endpoint
- Upload resume: POST multipart form with PDF/text file to `/resume/`
- Tailor resume: POST JSON with resume_id and jd_text to `/tailor/`

## 📝 System Limitations

### Current Scope
- **Database**: SQLite only (no PostgreSQL pgvector in current setup)
- **File Types**: PDF and text files only
- **LLM**: OpenAI GPT-4o only (no local LLM support)
- **Embedding**: Single model (all-MiniLM-L6-v2)
- **Architecture**: Simple RAG (no multi-agent or graph features)

### Known Issues
- PDF text extraction quality depends on PDF structure
- Chunking strategy may split related content across chunks
- No batch processing for multiple resumes
- No user authentication or multi-tenancy

### Extension Points
The current architecture could support:
1. **Additional LLMs**: Local models via transformers
2. **Enhanced Chunking**: Semantic chunking with NLP
3. **Better PDF Processing**: OCR for scanned documents
4. **Database Scaling**: PostgreSQL with pgvector
5. **Authentication**: User management and API keys

---

**Generated**: August 2025  
**Status**: Production-ready, fully functional RAG system  
**Tech Stack**: FastAPI + SQLite + HuggingFace + OpenAI GPT-4o  