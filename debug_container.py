#!/usr/bin/env python3
"""
Debug the resume-api container directly without WSL password issues.
This script creates a simple test container to see what's actually failing.
"""

import subprocess
import time
import sys
from pathlib import Path
import os

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
    """Run a podman command inside WSL Ubuntu - with different syntax."""
    # Try multiple WSL command formats
    wsl_commands = [
        f'wsl -d Ubuntu -e bash -c "{podman_cmd}"',
        f'wsl -d Ubuntu -- {podman_cmd}',
        f'wsl -d Ubuntu {podman_cmd}',
    ]
    
    for wsl_cmd in wsl_commands:
        print(f"🔄 Trying WSL: {wsl_cmd}")
        try:
            result = subprocess.run(wsl_cmd, shell=True, capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout and "bash: -c: option requires an argument" not in result.stdout:
                print(f"   ✅ Success: {result.stdout.strip()}")
                return result
            else:
                print(f"   ❌ Failed: {result.stderr}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    print("❌ All WSL command formats failed")
    return None

def test_simple_container():
    """Test a simple container without mounting anything."""
    print("🧪 Testing simple container (no mount)...")
    
    # First, clean up any existing container
    cleanup_cmd = 'podman rm -f resume-test'
    run_wsl_podman_command(cleanup_cmd, check=False)
    
    # Run a simple test - just python version
    test_cmd = 'podman run --name resume-test resume-rag-ready:latest python --version'
    result = run_wsl_podman_command(test_cmd)
    
    if result and result.returncode == 0:
        print("✅ Basic Python works in container")
        
        # Now test importing our packages
        import_test_cmd = 'podman run --rm resume-rag-ready:latest python -c "import fastapi, uvicorn; print(\\"FastAPI imports OK\\")"'
        result2 = run_wsl_podman_command(import_test_cmd)
        
        if result2 and result2.returncode == 0:
            print("✅ FastAPI imports work")
            return True
        else:
            print("❌ FastAPI imports failed")
            return False
    else:
        print("❌ Basic Python failed in container")
        return False

def test_mounted_container():
    """Test container with Windows directory mounted."""
    print("🧪 Testing container with Windows mount...")
    
    cleanup_cmd = 'podman rm -f resume-mount-test'
    run_wsl_podman_command(cleanup_cmd, check=False)
    
    workspace_path = "/mnt/c/Users/ocean/workspace/resume-rag"
    mount_test_cmd = f'podman run --name resume-mount-test -v {workspace_path}:/app resume-rag-ready:latest ls -la /app'
    result = run_wsl_podman_command(mount_test_cmd)
    
    if result and result.returncode == 0:
        print("✅ Mount works, files visible")
        
        # Test if Python can import from mounted directory
        python_test_cmd = f'podman run --rm -v {workspace_path}:/app resume-rag-ready:latest bash -c "cd /app && python -c \\"import sys; print(\'Python path test OK\')\""'
        result2 = run_wsl_podman_command(python_test_cmd)
        
        if result2 and result2.returncode == 0:
            print("✅ App imports work with mount")
            return True
        else:
            print("❌ App imports failed with mount")
            # Try to get more details
            debug_cmd = f'podman run --rm -v {workspace_path}:/app resume-rag-ready:latest bash -c "cd /app && python -c \\"import sys; print(\'Debug done\')\""'
            debug_result = run_wsl_podman_command(debug_cmd)
            return False
    else:
        print("❌ Mount failed")
        return False

def get_actual_logs():
    """Try to get the actual container logs using different methods."""
    print("📋 Attempting to get container logs...")
    
    # Try to get logs from the failed container
    logs_cmd = 'podman logs resume-api'
    result = run_wsl_podman_command(logs_cmd, check=False)
    
    if result:
        print("📋 Container logs:")
        print("=" * 50)
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print("=" * 50)
    else:
        print("❌ Could not get container logs")

def main():
    """Main debug function."""
    print("🐛 Resume RAG Container Debug")
    print("=" * 50)
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Step 1: Try to get logs from failed container
    get_actual_logs()
    
    # Step 2: Test simple container
    if test_simple_container():
        print("\n✅ Basic container works")
        
        # Step 3: Test with mount
        if test_mounted_container():
            print("\n✅ Mounted container works")
            print("\n🤔 Container should be working... checking startup command...")
        else:
            print("\n❌ Mount is the problem")
            print("💡 Solution: Fix the mount or file permissions")
    else:
        print("\n❌ Basic container is broken")
        print("💡 Solution: Rebuild the resume-rag-ready image")
    
    print("\n🏁 Debug complete")

if __name__ == "__main__":
    main()