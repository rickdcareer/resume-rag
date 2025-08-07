#!/usr/bin/env python3
"""
One-click startup script for Resume RAG API in Podman.

This script handles everything:
- Checks Podman machine status
- Starts Podman machine if needed
- Builds and starts all containers
- Waits for services to be ready
- Tests the API
- Runs the smoke demo

Usage: python start.py
"""

import subprocess
import time
import sys
import os
import requests
from pathlib import Path

def run_command(cmd, capture_output=True, check=True):
    """Run a command and return the result."""
    print(f"🔄 Running: {cmd}")
    try:
        if isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True, check=check)
        else:
            result = subprocess.run(cmd, capture_output=capture_output, text=True, check=check)
        if not capture_output:
            return result
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        if e.stderr:
            print(f"   Error: {e.stderr}")
        return None

def run_wsl_podman_command(podman_cmd, check=True):
    """Run a podman command inside WSL Ubuntu."""
    wsl_cmd = f'wsl -d Ubuntu -e bash -c "{podman_cmd}"'
    print(f"🔄 Running WSL Podman: {podman_cmd}")
    try:
        result = subprocess.run(wsl_cmd, shell=True, capture_output=True, text=True, check=check)
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ WSL Podman command failed: {e}")
        if e.stderr:
            print(f"   Error: {e.stderr}")
        return None

def check_wsl():
    """Check if WSL Ubuntu is available and start it if needed."""
    print("🔍 Checking WSL Ubuntu availability...")
    
    # Just try to start Ubuntu directly - simpler approach
    print("🔄 Starting WSL Ubuntu...")
    start_result = run_command("wsl -d Ubuntu -e echo 'Testing Ubuntu'", check=False)
    if not start_result or start_result.returncode != 0:
        print("❌ WSL Ubuntu failed to start!")
        print("   Error:", start_result.stderr if start_result else "Unknown error")
        return False
    
    print("✅ WSL Ubuntu is running")
    return True

def check_podman_in_wsl():
    """Check if Podman is working inside WSL Ubuntu."""
    print("🔍 Checking Podman in WSL Ubuntu...")
    
    # Test basic podman connectivity
    result = run_wsl_podman_command("podman --version", check=False)
    if not result or result.returncode != 0:
        print("❌ Podman not working in WSL Ubuntu!")
        print("   Please install Podman in WSL Ubuntu:")
        print("   wsl -d Ubuntu -e bash -c 'sudo apt update && sudo apt install -y podman'")
        return False
    
    print(f"✅ Podman in WSL: {result.stdout.strip()}")
    
    # Test podman service
    result = run_wsl_podman_command("podman ps -a", check=False)
    if not result or result.returncode != 0:
        print("❌ Podman service not running in WSL!")
        print("   Starting Podman service...")
        run_wsl_podman_command("podman system service --time=0 &", check=False)
        time.sleep(2)
        
        # Test again
        result = run_wsl_podman_command("podman ps -a", check=False)
        if not result or result.returncode != 0:
            print("❌ Failed to start Podman service")
            return False
    
    print("✅ Podman service ready in WSL")
    return True

def stop_existing_containers():
    """Stop and remove existing containers if they exist."""
    print("🧹 Cleaning up existing containers...")
    
    containers = ["resume-api"]  # Only API container now
    for container in containers:
        # Stop container
        run_wsl_podman_command(f"podman stop {container}", check=False)
        # Remove container
        run_wsl_podman_command(f"podman rm {container}", check=False)
    
    print("✅ Cleanup completed")

def start_database():
    """Use SQLite database instead of PostgreSQL for simplicity."""
    print("🗄️  Setting up SQLite database...")
    
    # Update config to use SQLite
    update_config_for_sqlite()
    return True

def update_config_for_sqlite():
    """Update config.json to use SQLite instead of PostgreSQL."""
    print("🔄 Updating config to use SQLite...")
    try:
        import json
        config_data = {}
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except:
            pass
        
        config_data["database"] = {"url": "sqlite:///./resume_rag.db"}
        
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=2)
        
        print("✅ Config updated to use SQLite")
    except Exception as e:
        print(f"⚠️  Failed to update config: {e}")
        print("   Will use default database settings")

def check_ready_image():
    """Check if the pre-built resume-rag-ready image exists."""
    print("🔍 Checking for pre-built Resume RAG image...")
    
    # Check if we have the resume-rag-ready image
    result = run_wsl_podman_command('podman images resume-rag-ready:latest', check=False)
    if result and result.returncode == 0 and "resume-rag-ready" in result.stdout:
        print("✅ Found pre-built resume-rag-ready:latest image")
        return True
    
    print("❌ Pre-built image not found!")
    print("   Please run: python build_image.py")
    print("   This builds an image with all dependencies pre-installed")
    return False

def create_env_file():
    """Create .env file with API key if it doesn't exist."""
    env_file = Path(".env")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    # Try to get API key from terminal environment first
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_key:
        print("🔑 OpenAI API key not found in environment")
        print("Please enter your OpenAI API key (or press Enter to skip):")
        openai_key = input("API Key: ").strip()
    
    if not openai_key:
        print("⚠️  No API key provided - creating template .env file")
        openai_key = "your-openai-api-key-here"
    
    env_content = f"""# Resume RAG API Environment Variables
# This file is ignored by git for security

# REQUIRED: Your OpenAI API Key
OPENAI_API_KEY={openai_key}

# Database connection  
DB_URL=postgresql://postgres:postgres@host.containers.internal:5432/resume_rag

# Optional overrides
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        if openai_key == "your-openai-api-key-here":
            print("📝 Created .env template file")
            print("❗ Please edit .env file and add your real OpenAI API key!")
            return False
        else:
            print("✅ Created .env file with your API key")
            return True
            
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(".env")
    if not env_file.exists():
        return {}
    
    env_vars = {}
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Remove BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]
            
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Clean any remaining weird characters
                    key = ''.join(c for c in key if c.isprintable())
                    value = ''.join(c for c in value if c.isprintable())
                    if key and value:
                        env_vars[key] = value
        print(f"✅ Loaded {len(env_vars)} variables from .env file")
        return env_vars
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return {}

def start_api():
    """Start the API using pre-built resume-rag-ready image."""
    print("🚀 Starting API container...")
    
    # Load .env file first, then check environment
    env_vars = load_env_file()
    
    # Get API key from .env file or environment
    api_key = env_vars.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found!")
        print("   Please either:")
        print("   1. Copy env.example to .env and add your key, OR")
        print("   2. Set environment: export OPENAI_API_KEY=your-key-here")
        sys.exit(1)
    
    workspace_path = "/mnt/c/Users/ocean/workspace/resume-rag"
    
    # No package installation needed - everything is pre-installed!
    # Use a simple startup command without complex nested quotes
    # Mount logs directory so we can see logs from Windows
    podman_cmd = f'podman run -d --name resume-api -p 8000:8000 -v {workspace_path}:/app -v {workspace_path}/logs:/app/logs -w /app -e OPENAI_API_KEY={api_key} -e DB_URL=sqlite:///./resume_rag.db resume-rag-ready:latest python -u -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug'
    
    print("🚀 Starting API (no installation needed - using pre-built image)...")
    result = run_wsl_podman_command(podman_cmd, check=False)
    if not result or result.returncode != 0:
        print("❌ Failed to start API container")
        return False
    
    print("✅ API container started")
    return True

def wait_for_database():
    """Database ready (SQLite is always ready)."""
    print("✅ Database ready (SQLite)")
    return True

def wait_for_api():
    """Wait for API to be ready."""
    print("⏳ Waiting for API to be ready...")
    
    for i in range(60):  # Wait up to 60 seconds
        try:
            print(f"🔍 Attempt {i+1}: Testing http://localhost:8000/health")
            response = requests.get("http://localhost:8000/health", timeout=5)
            print(f"   Response status: {response.status_code}")
            if response.status_code == 200:
                print("✅ API is ready")
                return True
            else:
                print(f"   Response text: {response.text[:200]}")
        except requests.exceptions.ConnectionError as e:
            print(f"   Connection error: {e}")
        except requests.exceptions.Timeout as e:
            print(f"   Timeout error: {e}")
        except Exception as e:
            print(f"   Other error: {e}")
        
        # Check container status every 5 attempts
        if i % 5 == 4:
            print(f"🔍 Checking container status (attempt {i+1})...")
            container_result = run_wsl_podman_command("podman ps | grep resume-api", check=False)
            if container_result and container_result.stdout:
                print(f"   Container status: {container_result.stdout.strip()}")
            else:
                print("   ❌ Container not found or not running!")
            
            # Check container logs
            print("🔍 Checking container logs...")
            log_result = run_wsl_podman_command("podman logs --tail 10 resume-api", check=False)
            if log_result and log_result.stdout:
                print(f"   Recent logs: {log_result.stdout.strip()}")
            else:
                print("   ❌ No logs available!")
        
        time.sleep(1)
        if i % 10 == 9:  # Print every 10 seconds
            print(f"   Still waiting... ({i+1}/60)")
    
    print("❌ API failed to start in time")
    print("🔍 Final container check...")
    run_wsl_podman_command("podman ps -a | grep resume-api", check=False)
    print("🔍 Final log check...")
    run_wsl_podman_command("podman logs --tail 20 resume-api", check=False)
    return False

def run_smoke_test():
    """Run the smoke test."""
    print("🧪 Running smoke test...")
    
    try:
        result = run_command("python scripts/smoke_demo.py", capture_output=False, check=False)
        if result and result.returncode == 0:
            print("✅ Smoke test passed!")
            return True
        else:
            print("❌ Smoke test failed")
            return False
    except Exception as e:
        print(f"❌ Error running smoke test: {e}")
        return False

def show_status():
    """Show the status of running containers."""
    print("\n📊 Container Status:")
    run_wsl_podman_command("podman ps", check=False)
    
    print("\n🌐 API Endpoints:")
    print("   Health: http://localhost:8000/health")
    print("   Docs:   http://localhost:8000/docs")
    
    print("\n🔧 Useful Commands (run in WSL):")
    print('   View logs: wsl -d Ubuntu -e bash -c "podman logs resume-api"')
    print('   Stop all:  wsl -d Ubuntu -e bash -c "podman stop resume-api resume-db"')
    print('   Remove:    wsl -d Ubuntu -e bash -c "podman rm resume-api resume-db"')

def main():
    """Main startup routine."""
    print("🎯 Resume RAG API - One-Click Startup")
    print("=" * 50)
    
    # Change to the correct directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check prerequisites
    if not check_wsl():
        sys.exit(1)
    
    if not check_podman_in_wsl():
        sys.exit(1)
    
    # Create/check .env file
    if not create_env_file():
        print("❌ API key setup failed. Please edit .env file manually.")
        sys.exit(1)
    
    # Stop existing containers
    stop_existing_containers()
    
    # Check for pre-built image
    if not check_ready_image():
        sys.exit(1)
    
    # Start services
    if not start_database():
        sys.exit(1)
    
    if not wait_for_database():
        sys.exit(1)
    
    if not start_api():
        sys.exit(1)
    
    if not wait_for_api():
        print("❌ API failed to start. Check logs with: podman logs resume-api")
        sys.exit(1)
    
    # Run smoke test
    print("\n" + "=" * 50)
    print("🎉 ALL SERVICES STARTED SUCCESSFULLY!")
    print("=" * 50)
    
    # Show status
    show_status()
    
    # Ask if user wants to run smoke test
    print("\n" + "=" * 50)
    choice = input("🧪 Run smoke test now? (Y/n): ").lower()
    if choice != 'n':
        run_smoke_test()
    
    print("\n🎉 Setup complete! Your Resume RAG API is running!")

if __name__ == "__main__":
    main()