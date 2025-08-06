#!/usr/bin/env python3
"""
Simple script to view container logs using different methods.
This bypasses the WSL command escaping issues.
"""

import subprocess
import time
import sys
from pathlib import Path

def run_wsl_command(cmd):
    """Try different WSL command formats to get logs."""
    wsl_formats = [
        f'wsl -d Ubuntu -- {cmd}',
        f'wsl -d Ubuntu -e {cmd}',
        f'wsl -d Ubuntu {cmd}',
    ]
    
    for wsl_cmd in wsl_formats:
        print(f"🔄 Trying: {wsl_cmd}")
        try:
            result = subprocess.run(wsl_cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                print("✅ Success!")
                return result.stdout
            else:
                print(f"❌ Failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ Timeout")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return None

def get_container_logs():
    """Get logs from the resume-api container."""
    print("📋 Attempting to get container logs...")
    
    # Method 1: Direct podman logs
    logs = run_wsl_command("podman logs resume-api")
    if logs:
        return logs
    
    # Method 2: Try with follow flag for recent logs
    logs = run_wsl_command("podman logs --tail 50 resume-api")
    if logs:
        return logs
    
    # Method 3: Get container status first
    print("\n🔍 Checking container status...")
    status = run_wsl_command("podman ps -a --filter name=resume-api")
    if status:
        print("Container status:")
        print(status)
    
    return None

def check_log_files():
    """Check if any log files were created in the logs directory."""
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        if log_files:
            print(f"📁 Found {len(log_files)} log files:")
            for log_file in log_files:
                print(f"   {log_file}")
                try:
                    with open(log_file, 'r') as f:
                        content = f.read()
                        print(f"📄 Content of {log_file}:")
                        print(content)
                except Exception as e:
                    print(f"❌ Error reading {log_file}: {e}")
        else:
            print("📁 No log files found in logs/ directory")
    else:
        print("📁 Logs directory doesn't exist")

def main():
    """Main function to get container logs."""
    print("🔍 Resume RAG Container Log Viewer")
    print("=" * 50)
    
    # Method 1: Try to get container logs
    logs = get_container_logs()
    if logs:
        print("\n📋 Container Logs:")
        print("=" * 50)
        print(logs)
        print("=" * 50)
    else:
        print("\n❌ Could not retrieve container logs via WSL")
    
    # Method 2: Check for log files in mounted directory
    print("\n📁 Checking mounted log files...")
    check_log_files()
    
    # Method 3: Try live monitoring if container is running
    if logs:
        choice = input("\n▶️  Monitor logs in real-time? (y/N): ").lower()
        if choice == 'y':
            print("📺 Monitoring logs (Ctrl+C to stop)...")
            try:
                while True:
                    new_logs = run_wsl_command("podman logs --tail 5 resume-api")
                    if new_logs:
                        print(f"\n[{time.strftime('%H:%M:%S')}] Latest logs:")
                        print(new_logs)
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n🛑 Stopped monitoring")

if __name__ == "__main__":
    main()