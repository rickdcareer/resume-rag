#!/usr/bin/env python3
"""
Test individual components to isolate the slow startup issue.
"""

import subprocess
import time
import sys
from pathlib import Path

def run_wsl_podman(cmd):
    """Run a podman command via WSL with the working format."""
    wsl_cmd = f'wsl -d Ubuntu -- {cmd}'
    print(f"🔄 Running: {cmd}")
    try:
        result = subprocess.run(wsl_cmd, shell=True, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"✅ Success")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Failed (exit {result.returncode})")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout after 2 minutes")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_basic_imports():
    """Test basic Python imports in container."""
    print("\n🧪 Testing basic Python imports...")
    
    tests = [
        'python -c "print(\\"Python works\\")"',
        'python -c "import sys; print(f\\"Python {sys.version}\\")"',
        'python -c "import fastapi; print(\\"FastAPI imported\\")"',
        'python -c "import uvicorn; print(\\"Uvicorn imported\\")"',
        'python -c "import torch; print(\\"PyTorch imported\\")"',
        'python -c "import sentence_transformers; print(\\"SentenceTransformers imported\\")"',
    ]
    
    for i, test in enumerate(tests, 1):
        print(f"\n  Test {i}: {test.split(';')[0].replace('import ', '').replace('print(', '').split(')')[0]}")
        cmd = f'podman run --rm resume-rag-ready:latest {test}'
        run_wsl_podman(cmd)

def test_app_imports():
    """Test importing our app modules."""
    print("\n🧪 Testing app module imports...")
    
    workspace_path = "/mnt/c/Users/ocean/workspace/resume-rag"
    
    tests = [
        'python -c "import sys; sys.path.insert(0, \\"/app\\"); import config; print(\\"Config imported\\")"',
        'python -c "import sys; sys.path.insert(0, \\"/app\\"); from app.database import create_tables; print(\\"Database imported\\")"',
        'python -c "import sys; sys.path.insert(0, \\"/app\\"); from app.api import api_router; print(\\"API router imported\\")"',
    ]
    
    for i, test in enumerate(tests, 1):
        print(f"\n  App Test {i}: {test.split(';')[-1].strip()}")
        cmd = f'podman run --rm -v {workspace_path}:/app -w /app resume-rag-ready:latest {test}'
        run_wsl_podman(cmd)

def test_model_loading():
    """Test the slow model loading specifically."""
    print("\n🧪 Testing HuggingFace model loading (this is the suspected culprit)...")
    
    workspace_path = "/mnt/c/Users/ocean/workspace/resume-rag"
    
    print("\n  🤖 Testing sentence-transformers model loading...")
    model_test = 'python -c "from sentence_transformers import SentenceTransformer; print(\\"Loading model...\\"); model = SentenceTransformer(\\"sentence-transformers/all-MiniLM-L6-v2\\"); print(\\"Model loaded!\\"); embedding = model.encode([\\"test\\"]); print(f\\"Embedding shape: {embedding.shape}\\")"'
    
    cmd = f'podman run --rm -v {workspace_path}:/app -w /app resume-rag-ready:latest {model_test}'
    
    start_time = time.time()
    success = run_wsl_podman(cmd)
    elapsed = time.time() - start_time
    
    if success:
        print(f"✅ Model loading completed in {elapsed:.2f}s")
        if elapsed > 30:
            print("⚠️ This is very slow - likely downloading model files")
        else:
            print("🚀 This is fast - model files are cached")
    else:
        print(f"❌ Model loading failed after {elapsed:.2f}s")

def test_app_startup():
    """Test the actual app startup."""
    print("\n🧪 Testing actual app startup...")
    
    workspace_path = "/mnt/c/Users/ocean/workspace/resume-rag"
    
    print("\n  🚀 Testing FastAPI app import and startup...")
    app_test = 'python -c "import sys; sys.path.insert(0, \\"/app\\"); from app.main import app; print(\\"App imported successfully\\")"'
    
    cmd = f'podman run --rm -v {workspace_path}:/app -w /app -e DB_URL=sqlite:///./test.db resume-rag-ready:latest {app_test}'
    
    start_time = time.time()
    success = run_wsl_podman(cmd)
    elapsed = time.time() - start_time
    
    print(f"   App import took {elapsed:.2f}s")

def main():
    """Run all component tests."""
    print("🧪 Resume RAG Component Tests")
    print("=" * 50)
    print("This will test each component individually to find the bottleneck")
    
    # Test 1: Basic container functionality
    test_basic_imports()
    
    # Test 2: App module imports
    test_app_imports()
    
    # Test 3: Model loading (suspected slow part)
    test_model_loading()
    
    # Test 4: App startup
    test_app_startup()
    
    print("\n🏁 Component testing complete!")
    print("The slowest test above is likely causing the startup delay.")

if __name__ == "__main__":
    main()