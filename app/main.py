"""FastAPI application entry point."""

import time
import logging
from fastapi import FastAPI
from config import config
from app.api import api_router
from app.database import create_tables

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Resume RAG API",
    description="Local RAG résumé-tailoring API",
    version="0.1.0"
)

# Include API routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Application startup event with detailed timing."""
    startup_start = time.time()
    print("🚀 Resume RAG API starting up...")
    logger.info("Starting Resume RAG API startup sequence")
    
    # Step 1: Configuration
    step_start = time.time()
    print("📊 Loading configuration...")
    config.print_config_summary()
    print(f"⏱️ Config loaded in {time.time() - step_start:.2f}s")
    
    # Step 2: Validate configuration  
    step_start = time.time()
    print("🔍 Validating configuration...")
    if not config.validate_required_settings():
        raise RuntimeError("Configuration validation failed")
    print(f"⏱️ Config validated in {time.time() - step_start:.2f}s")
    
    # Step 3: Database setup
    step_start = time.time()
    print("🗄️ Setting up database...")
    try:
        create_tables()
        print(f"✅ Database ready in {time.time() - step_start:.2f}s")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        logger.error(f"Database setup failed: {e}")
        raise
    
    # Step 4: Load embedding model (this is probably the slow part!)
    step_start = time.time()
    print("🤖 Loading HuggingFace embedding model...")
    print("   This may take 30-60 seconds on first run (downloading model)...")
    try:
        from app.vectorstore import embedder
        # Force model load by encoding a test string
        print("   📥 Downloading/loading model files...")
        test_embedding = embedder.encode(["test"])
        print(f"✅ Embedding model ready in {time.time() - step_start:.2f}s")
        print(f"   Model dimension: {len(test_embedding[0])}")
        logger.info(f"Embedding model loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load embedding model: {e}")
        logger.error(f"Model loading failed: {e}")
        raise
    
    total_time = time.time() - startup_start
    print(f"🎯 API startup complete in {total_time:.2f}s total!")
    logger.info(f"Startup completed in {total_time:.2f}s")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    print("🛑 Resume RAG API shutting down...")
