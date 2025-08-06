# Resume RAG API

A **working Resume RAG (Retrieval Augmented Generation) API** that intelligently tailors resumes to job descriptions using local embeddings and OpenAI GPT-4o.

## 🎯 What It Does

- **Upload resumes** (PDF or text files) 
- **Process job descriptions** to understand requirements
- **Find relevant resume sections** using vector similarity search
- **Generate tailored bullet points** with GPT-4o
- **Provide citations** showing which resume chunks were used

## 🚀 Quick Start

### One-Click Startup
```bash
# 1. Build the container image
python build_image.py

# 2. Set up your API key (one-time setup)
cp env.example .env
# Edit .env and add your OpenAI API key

# 3. Start everything (handles Podman, database, API)
python start.py

# 4. Test the API
curl http://localhost:8000/health
```

### Manual Container Deployment
```bash
# Using pre-built image
podman run -d --name resume-api \
  -p 8000:8000 \
  -v ./:/app \
  -e OPENAI_API_KEY=your-key \
  resume-rag-ready:latest
```

## 📋 Prerequisites

- **Podman** (with WSL Ubuntu on Windows)
- **OpenAI API Key** (for GPT-4o) - copy `env.example` to `.env` and add your key
- **Python 3.11+** (for building/running)

## 🌐 API Endpoints

### Health Check
```bash
GET /health
# Returns: {"status": "ok"}
```

### Upload Resume
```bash
POST /resume/
# Upload PDF or text file
# Returns: {id: 1, text_length: 1500, chunk_count: 3}
```

### Tailor Resume
```bash
POST /tailor/
# Body: {resume_id: 1, jd_text: "Job description..."}
# Returns: {bullets: [...], cited_chunks: [0,1,2]}
```

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs

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

## ⚙️ How It Works

### 1. Resume Processing
- **File Upload**: Supports PDF (PyPDF2) and text files
- **Text Chunking**: Splits resume into ~200-word semantic chunks
- **Embedding**: Uses sentence-transformers/all-MiniLM-L6-v2 for 384-dim vectors
- **Storage**: SQLite database with JSON embedding columns

### 2. Job Matching
- **Job Analysis**: Embeds job description using same model
- **Similarity Search**: Cosine distance calculation in Python
- **Chunk Retrieval**: Returns top 12 most relevant resume sections

### 3. Content Generation
- **Prompt Construction**: Combines retrieved chunks with job requirements
- **LLM Generation**: OpenAI GPT-4o creates tailored bullet points
- **Citation Parsing**: Tracks which resume chunks influenced each bullet

## 🛠️ Tech Stack

- **API**: FastAPI 0.110 + Uvicorn
- **Database**: SQLite with SQLAlchemy ORM
- **Embeddings**: HuggingFace sentence-transformers (local, no API costs)
- **LLM**: OpenAI GPT-4o (requires API key)
- **PDF Processing**: PyPDF2 3.0
- **Deployment**: Podman containers

## 🧪 Testing

### Smoke Test
```bash
python scripts/smoke_demo.py
```

**What it tests**:
- API health and connectivity
- Resume upload (uses `samples/sample_resume.txt`)
- Resume tailoring (uses `samples/sample_jd.txt`) 
- Output generation and file saving
- End-to-end RAG pipeline

### Sample Output
The system generates tailored bullets like:
```
• Designed a retrieval augmented generation (RAG) micro-service utilizing 
  FastAPI and GPT-4o, significantly reducing customer support search time by 68% [C1]
• Leveraged Hugging Face Transformers to develop advanced GenAI solutions, 
  aligning closely with customer success objectives [C1]
```

Output saved to: `samples/output/tailored_resume_YYYYMMDD_HHMMSS.txt`

## 📁 Project Structure

```
resume-rag/
├── app/                    # Main application code
│   ├── api/               # FastAPI route handlers
│   ├── services/          # Business logic (ingestion, retrieval, generation)
│   ├── models/            # Database models
│   └── vectorstore/       # Embedding services
├── samples/               # Test data and output
├── scripts/               # Utility scripts
├── docs/                  # Documentation
├── config.json           # Configuration settings
├── start.py              # One-click startup script
└── pyproject.toml        # Dependencies
```

## ⚡ Features

### ✅ Production Ready
- **Real Implementation**: No stubs or placeholder code
- **Error Handling**: Comprehensive exception handling and logging
- **File Processing**: PDF parsing and text file support
- **Vector Search**: Local embedding-based similarity search
- **Citation Tracking**: LLM response parsing with source references

### ✅ Privacy Focused
- **Local Embeddings**: No external API calls for vector generation
- **Minimal Data**: Only sends relevant chunks to OpenAI, not full resume
- **Local Database**: SQLite file storage, no cloud dependencies

### ✅ Developer Friendly
- **Auto Documentation**: FastAPI-generated Swagger UI
- **Type Hints**: Full Python type annotations
- **Container Ready**: Podman deployment with pre-built images
- **Easy Testing**: Smoke test script for validation

## 📊 Performance

- **Storage**: ~300KB SQLite database for typical resume
- **Memory**: ~500MB (transformer model loading)
- **Processing**: ~2-3 seconds for resume upload and chunking
- **Generation**: ~3-5 seconds for tailored bullets (depends on OpenAI API)

## 🔧 Configuration

Key settings in `config.json`:
- **Database**: SQLite file path
- **OpenAI**: Model (gpt-4o), temperature (0.7), max tokens (1000)
- **Embeddings**: Model name and dimensions (384)
- **Processing**: Chunk size (200 words), retrieval limit (12)

## 📝 Current Limitations

- **Database**: SQLite only (no PostgreSQL pgvector)
- **File Types**: PDF and text files only
- **LLM**: OpenAI GPT-4o only (no local LLM support)
- **Architecture**: Simple RAG (no multi-agent or graph features)

## 🔮 Extension Points

The architecture supports future enhancements:
- PostgreSQL with pgvector for better vector operations
- Local LLM integration (Ollama, transformers)
- Enhanced PDF processing with OCR
- Multi-resume batch processing
- User authentication and multi-tenancy

## 📄 License

This project demonstrates a complete RAG implementation for resume tailoring.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with `python scripts/smoke_demo.py`
4. Submit a pull request

---

**Status**: Production-ready RAG system  
**Last Updated**: August 2025