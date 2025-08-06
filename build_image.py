#!/usr/bin/env python3
"""
Build custom Resume RAG image with all dependencies pre-installed.

This script creates a custom Podman image based on wsl-python-runner
with all required packages installed. Run this once, then use start.py
for fast startups.

Usage: python build_image.py
"""

import subprocess
import time
import sys
import os
from pathlib import Path

def run_wsl_podman_command(podman_cmd, check=True, show_output=True):
    """Run a podman command inside WSL Ubuntu."""
    wsl_cmd = f'wsl -d Ubuntu -e bash -c "{podman_cmd}"'
    print(f"🔄 Running: {podman_cmd}")
    try:
        if show_output:
            # Show real-time output for building
            result = subprocess.run(wsl_cmd, shell=True, text=True, check=check)
        else:
            result = subprocess.run(wsl_cmd, shell=True, capture_output=True, text=True, check=check)
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ WSL Podman command failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"   Error: {e.stderr}")
        return None

def create_dockerfile():
    """Create a temporary Dockerfile for building the image."""
    dockerfile_content = '''FROM localhost/wsl-python-runner:latest

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python packages (this is the slow part!)
# Fix NumPy compatibility by installing numpy<2 first
RUN pip install --no-cache-dir "numpy<2.0.0" && \\
    pip install --no-cache-dir \\
    fastapi==0.110.* \\
    uvicorn[standard]==0.29.* \\
    sqlalchemy==2.0.* \\
    psycopg2-binary==2.9.* \\
    pgvector==0.2.* \\
    sentence-transformers==2.6.* \\
    torch==2.2.* \\
    python-dotenv==1.0.* \\
    python-multipart==0.0.9 \\
    pypdf2==3.0.* \\
    openai==1.12.* \\
    requests==2.31.*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["bash"]
'''
    
    with open("Dockerfile.resume-rag", "w") as f:
        f.write(dockerfile_content)
    
    print("✅ Created Dockerfile.resume-rag")

def build_image():
    """Build the custom Resume RAG image."""
    print("🔨 Building Resume RAG image (this will take 10-15 minutes)...")
    print("📦 Installing: FastAPI, PyTorch, Sentence Transformers, OpenAI, and more...")
    
    workspace_path = "/mnt/c/Users/ocean/workspace/resume-rag"
    build_cmd = f'cd {workspace_path} && podman build -f Dockerfile.resume-rag -t resume-rag-ready:latest .'
    
    print("⏳ This is the slow part - installing PyTorch (~1GB) and other ML packages...")
    print("   You can get coffee ☕ - this will take 10-15 minutes")
    
    result = run_wsl_podman_command(build_cmd, check=False, show_output=True)
    if not result or result.returncode != 0:
        print("❌ Failed to build image")
        return False
    
    print("✅ Successfully built resume-rag-ready:latest")
    return True

def test_image():
    """Test that the built image works."""
    print("🧪 Testing the built image...")
    
    # Test that Python packages are installed
    test_cmd = 'podman run --rm resume-rag-ready:latest python -c "import fastapi, uvicorn, sqlalchemy, torch, sentence_transformers, openai; print(\\"All packages imported successfully!\\")"'
    
    result = run_wsl_podman_command(test_cmd, check=False, show_output=False)
    if not result or result.returncode != 0:
        print("❌ Image test failed")
        return False
    
    print("✅ Image test passed - all packages available")
    return True

def cleanup():
    """Clean up temporary files."""
    try:
        os.remove("Dockerfile.resume-rag")
        print("✅ Cleaned up temporary files")
    except:
        pass

def show_image_info():
    """Show information about the built image."""
    print("\n📊 Image Information:")
    
    # Show image size
    size_cmd = 'podman images resume-rag-ready:latest --format "{{.Size}}"'
    result = run_wsl_podman_command(size_cmd, check=False, show_output=False)
    if result and result.returncode == 0:
        print(f"   Size: {result.stdout.strip()}")
    
    # Show what's installed
    print("\n📦 Pre-installed packages:")
    print("   ✅ FastAPI + Uvicorn (web framework)")
    print("   ✅ SQLAlchemy (database)")
    print("   ✅ PyTorch (~1GB ML framework)")
    print("   ✅ Sentence Transformers (embeddings)")
    print("   ✅ OpenAI client")
    print("   ✅ All Resume RAG dependencies")

def main():
    """Main build process."""
    print("🏗️  Resume RAG Image Builder")
    print("=" * 50)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {os.getcwd()}")
    
    print("\n🎯 This will create a custom image with ALL dependencies pre-installed")
    print("   After this, start.py will launch in ~10 seconds instead of 15+ minutes!")
    
    choice = input("\n▶️  Continue with build? This will take 10-15 minutes (y/N): ").lower()
    if choice != 'y':
        print("👋 Build cancelled")
        sys.exit(0)
    
    try:
        # Step 1: Create Dockerfile
        create_dockerfile()
        
        # Step 2: Build image
        if not build_image():
            sys.exit(1)
        
        # Step 3: Test image
        if not test_image():
            sys.exit(1)
        
        # Step 4: Show info
        show_image_info()
        
        # Step 5: Cleanup
        cleanup()
        
        print("\n🎉 BUILD COMPLETE!")
        print("=" * 50)
        print("✅ Image 'resume-rag-ready:latest' is ready to use")
        print("✅ All dependencies pre-installed")
        print("🚀 Now run: python start.py")
        print("   (Should start in ~10 seconds instead of 15+ minutes)")
        
    except KeyboardInterrupt:
        print("\n❌ Build interrupted by user")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()