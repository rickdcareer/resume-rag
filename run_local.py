#!/usr/bin/env python3
"""
Local development server for Resume RAG API.
Runs everything without containers for easier development.
"""

import subprocess
import sys
import os
import time
import requests
from pathlib import Path

def install_dependencies():
    """Install required Python packages."""
    print("📦 Installing Python dependencies...")
    
    packages = [
        "fastapi", "uvicorn", "sqlalchemy", "psycopg2-binary", 
        "pgvector", "sentence-transformers", "torch", "python-dotenv",
        "python-multipart", "pypdf2", "openai", "requests"
    ]
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package} already installed")
        except ImportError:
            print(f"🔄 Installing {package}...")
            subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

def check_env_file():
    """Check if .env file exists with OpenAI key."""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Please create .env file with:")
        print("OPENAI_API_KEY=your-key-here")
        return False
    
    # Read and check for API key
    with open(env_file, 'r') as f:
        content = f.read()
        if "OPENAI_API_KEY=" not in content or "your-openai-api-key-here" in content:
            print("❌ OpenAI API key not set in .env file!")
            return False
    
    print("✅ .env file found with API key")
    return True

def start_local_postgres():
    """Instructions for starting local PostgreSQL."""
    print("🗄️  Database Setup:")
    print("For local development, you have options:")
    print("1. Install PostgreSQL locally with pgvector extension")
    print("2. Use SQLite (modify config.json)")
    print("3. Use a cloud PostgreSQL service")
    print()
    print("For now, we'll use a simple in-memory SQLite setup...")
    
    # Create a simple SQLite config
    config_content = """{
  "database": {
    "url": "sqlite:///./resume_rag.db"
  },
  "openai": {
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 1000,
    "timeout": 30
  },
  "embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2", 
    "dimension": 384
  },
  "processing": {
    "chunk_max_words": 200,
    "retrieval_limit": 12
  },
  "api": {
    "host": "127.0.0.1",
    "port": 8000,
    "max_upload_size": 10485760
  },
  "logging": {
    "level": "INFO"
  }
}"""
    
    with open("config.local.json", "w") as f:
        f.write(config_content)
    
    # Copy to main config
    with open("config.json", "w") as f:
        f.write(config_content)
    
    print("✅ Created SQLite configuration")

def start_api_server():
    """Start the FastAPI server."""
    print("🚀 Starting FastAPI server...")
    
    # Load environment variables from .env
    if Path(".env").exists():
        from dotenv import load_dotenv
        load_dotenv()
    
    # Set environment for local config
    os.environ["ENVIRONMENT"] = "local"
    
    # Start server
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", "app.main:app", 
            "--host", "127.0.0.1", "--port", "8000", "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

def test_api():
    """Test if API is responding."""
    print("🧪 Testing API...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is running!")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        return False

def main():
    """Main function."""
    print("🏠 Resume RAG API - Local Development")
    print("=" * 50)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check .env file
    if not check_env_file():
        print("\n❌ Setup incomplete. Please create .env file first.")
        print("Example .env content:")
        print("OPENAI_API_KEY=sk-your-key-here")
        return
    
    # Install dependencies
    try:
        install_dependencies()
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        return
    
    # Setup database
    start_local_postgres()
    
    print("\n🎉 Setup complete!")
    print("Now starting the API server...")
    print("Press Ctrl+C to stop")
    print("-" * 30)
    
    # Start API server
    start_api_server()

if __name__ == "__main__":
    main()