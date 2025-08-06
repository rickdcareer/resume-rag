# Resume RAG API - Deployment Guide

## Quick Start

### 1. Install Dependencies
```bash
cd resume-rag
pip install fastapi uvicorn sqlalchemy psycopg2-binary pgvector sentence-transformers torch python-dotenv python-multipart pypdf2 openai requests
```

### 2. Configuration

The API uses a **JSON-based configuration system** with environment variable overrides:

#### Configuration Files
- **`config.json`** - Default settings
- **`config.development.json`** - Development settings (GPT-3.5, debug logging)  
- **`config.production.json`** - Production settings (optimized for performance)

#### Required Settings
```bash
# OpenAI API Key (REQUIRED) - always from environment for security
export OPENAI_API_KEY="your-openai-api-key-here"
```

#### Environment-Specific Configs
```bash
# Load development config (cheaper GPT-3.5, debug logging)
export ENVIRONMENT="development"

# Load production config (optimized settings)
export ENVIRONMENT="production"

# Default: uses config.json
```

#### Configuration Override Examples
```bash
# Override specific settings via environment variables
export OPENAI_MODEL="gpt-3.5-turbo"    # Override model choice
export OPENAI_TEMPERATURE="0.5"        # More conservative generation
export LOG_LEVEL="DEBUG"               # Enable debug logging
export CHUNK_MAX_WORDS="150"           # Smaller chunks
```

#### Quick Setup Options

**Option 1: Interactive Setup**
```bash
cd resume-rag
python setup_config.py
```

**Option 2: Manual JSON Edit**
```bash
# Edit the JSON config directly
nano config.json

# Test your configuration
python config.py
```

**Option 3: Copy Environment Template**
```bash
# Use development settings
cp config.development.json config.json

# Use production settings  
cp config.production.json config.json
```

### 3. Start Database (PostgreSQL with pgvector)
```bash
# Using Podman (recommended)
podman-compose up db -d

# Or using Docker
docker-compose up db -d
```

### 4. Start API Server
```bash
# From the resume-rag directory
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Test End-to-End Pipeline
```bash
# Run the smoke test
python scripts/smoke_demo.py

# This will create a tailored resume file in:
# samples/output/tailored_resume_YYYYMMDD_HHMMSS.txt
```

## Container Deployment (Production)

### Using Podman (Recommended)
```bash
# Build and run everything
podman-compose up

# Test the health endpoint
curl http://localhost:8000/health
```

### Using Docker (Fallback)
```bash
# Build and run everything  
docker-compose up

# Test the health endpoint
curl http://localhost:8000/health
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/resume/` | Upload resume (PDF/text) |
| GET | `/resume/{id}` | Get resume details |
| POST | `/tailor/` | **Main endpoint**: Tailor resume to job description |
| GET | `/tailor/{id}/preview` | Preview chunks (debugging) |
| GET | `/tailor/` | Service information |

## Sample Usage

### 1. Upload Resume
```bash
curl -X POST http://localhost:8000/resume/ \
  -F "file=@path/to/resume.pdf"
```

### 2. Tailor Resume
```bash
curl -X POST http://localhost:8000/tailor/ \
  -H "Content-Type: application/json" \
  -d '{
    "resume_id": 1,
    "job_description": "Senior Python Developer with FastAPI experience..."
  }'
```

## Architecture

- **FastAPI**: Web framework and API
- **PostgreSQL + pgvector**: Database with vector similarity search
- **MiniLM**: Local embedding model (384-dim vectors)
- **GPT-4o**: Text generation for resume tailoring
- **SQLAlchemy**: Database ORM
- **Sentence Transformers**: Embedding pipeline

## Project Structure
```
resume-rag/
├── config.py                # ⭐ Configuration loader
├── config.json              # ⭐ Default settings  
├── config.development.json  # ⭐ Development settings
├── config.production.json   # ⭐ Production settings
├── setup_config.py          # ⭐ Interactive config setup
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database connection
│   ├── api/
│   │   ├── __init__.py      # API router
│   │   ├── resume.py        # Resume upload/retrieval
│   │   └── tailor.py        # Resume tailoring
│   ├── models/
│   │   └── tables.py        # SQLAlchemy models
│   ├── services/
│   │   ├── ingestion.py     # Resume chunking & embedding
│   │   ├── retrieval.py     # Vector similarity search
│   │   └── generation.py    # GPT-4o integration
│   └── vectorstore/
│       └── hf_embedder.py   # HuggingFace embeddings
├── samples/
│   ├── sample_resume.txt    # Test resume
│   ├── sample_jd.txt        # Test job description
│   └── output/              # Generated tailored resumes
├── scripts/
│   └── smoke_demo.py        # End-to-end test
├── docs/
│   └── architecture.md      # Detailed design
├── pyproject.toml           # Dependencies
├── Dockerfile               # Container build
├── docker-compose.yml       # Multi-service setup
└── README.md                # Quick start guide
```

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError: No module named 'app'**
   - Make sure you're running from the `resume-rag` directory
   - Use: `python -m uvicorn app.main:app`

2. **Database connection error**
   - Ensure PostgreSQL is running with pgvector extension
   - Check `DB_URL` environment variable

3. **OpenAI API errors**
   - Verify `OPENAI_API_KEY` is set correctly
   - Check API key has sufficient credits

4. **Embedding model download**
   - First run will download ~90MB MiniLM model
   - Ensure internet connection for initial setup

### Development Tips

- Use `--reload` flag for auto-reloading during development
- Check logs for detailed error information
- Run `python scripts/smoke_demo.py` to test the full pipeline
- Use `/tailor/{id}/preview` to debug chunk retrieval

## Production Considerations

- Use environment variables for all secrets
- Configure proper PostgreSQL instance with pgvector
- Set up monitoring for the embedding model memory usage
- Consider rate limiting for OpenAI API calls
- Use reverse proxy (nginx) for SSL termination
- Set up proper logging and monitoring