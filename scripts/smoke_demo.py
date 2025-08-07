#!/usr/bin/env python3
"""
End-to-end smoke test for Resume RAG API.

This script tests the complete pipeline:
1. Health check
2. Resume upload (using sample_resume.txt)
3. Resume tailoring to job description (using sample_jd.txt)
4. Prints tailored bullets
5. Saves complete tailored resume to samples/output/

Usage: 
    python scripts/smoke_demo.py

Output:
    - Console output showing test progress and results
    - File saved to: samples/output/tailored_resume_YYYYMMDD_HHMMSS.txt

Prerequisites:
    - API server running at http://localhost:8000
    - PostgreSQL database with pgvector extension
    - OpenAI API key set in environment (OPENAI_API_KEY)
    - Sample files: samples/sample_resume.txt and samples/sample_jd.txt
"""

import requests
import json
import time
import sys
import os
from typing import Dict, Any
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 30

def load_sample_data():
    """Load sample resume and job description from files."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    samples_dir = os.path.join(project_root, "samples")
    
    resume_file = os.path.join(samples_dir, "sample_resume.txt")
    jd_file = os.path.join(samples_dir, "sample_jd.txt")
    
    try:
        with open(resume_file, 'r', encoding='utf-8') as f:
            resume_content = f.read().strip()
        
        with open(jd_file, 'r', encoding='utf-8') as f:
            jd_content = f.read().strip()
            
        return resume_content, jd_content
    except FileNotFoundError as e:
        print_error(f"Sample file not found: {e}")
        print("Please ensure sample_resume.txt and sample_jd.txt exist in the samples/ folder")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error reading sample files: {e}")
        sys.exit(1)

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_step(step: str, status: str = ""):
    """Print a formatted step."""
    status_part = f" [{status}]" if status else ""
    print(f"\n🔄 {step}{status_part}")

def print_success(message: str):
    """Print a success message."""
    print(f"✅ {message}")

def print_error(message: str):
    """Print an error message."""
    print(f"❌ {message}")

def make_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make HTTP request with error handling."""
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        return response
    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        sys.exit(1)

def test_health_check() -> bool:
    """Test the health endpoint."""
    print_step("Testing health endpoint")
    
    response = make_request("GET", f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "ok":
            print_success(f"Health check passed: {data}")
            return True
        else:
            print_error(f"Unexpected health response: {data}")
            return False
    else:
        print_error(f"Health check failed: {response.status_code} - {response.text}")
        return False

def upload_resume(resume_content: str) -> int:
    """Upload the sample resume and return resume ID."""
    print_step("Uploading sample resume")
    
    # Create a temporary text file in memory
    files = {
        'file': ('sample_resume.txt', resume_content, 'text/plain')
    }
    
    response = make_request("POST", f"{BASE_URL}/resume/", files=files)
    
    if response.status_code == 200:
        data = response.json()
        resume_id = data.get("id")
        print_success(f"Resume uploaded successfully!")
        print(f"   Resume ID: {resume_id}")
        print(f"   Text length: {data.get('text_length')} characters")
        print(f"   Chunks created: {data.get('chunk_count')}")
        return resume_id
    else:
        print_error(f"Resume upload failed: {response.status_code} - {response.text}")
        sys.exit(1)

def tailor_resume(resume_id: int, job_description: str) -> Dict[str, Any]:
    """Tailor the resume to the job description."""
    print_step("Tailoring resume to job description")
    
    payload = {
        "resume_id": resume_id,
        "jd_text": job_description
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = make_request("POST", f"{BASE_URL}/tailor/", 
                          json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print_success("Resume tailoring completed!")
        return data
    else:
        print_error(f"Resume tailoring failed: {response.status_code} - {response.text}")
        sys.exit(1)

def save_output_resume(results: Dict[str, Any], original_resume: str, job_description: str) -> str:
    """Save the tailored resume to an output file."""
    # Create output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, "samples", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for unique filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"tailored_resume_{timestamp}.txt")
    
    bullets = results.get("tailored_bullets", [])
    cited_chunks = results.get("cited_chunks", [])
    
    # Create the output content
    output_content = f"""TAILORED RESUME - Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*80}

JOB DESCRIPTION USED:
{'-'*40}
{job_description}

TAILORED RESUME BULLETS:
{'-'*40}
"""
    
    for i, bullet in enumerate(bullets, 1):
        output_content += f"{i}. {bullet}\n"
    
    output_content += f"""
CITED RESUME CHUNKS:
{'-'*40}
"""
    
    # Deduplicate chunks by ID to avoid repetition
    seen_chunks = {}
    for chunk in cited_chunks:
        # Handle both dict format and integer format
        if isinstance(chunk, dict):
            chunk_id = chunk.get("id")
            chunk_text = chunk.get("text", "")
        else:
            # If chunk is just an integer ID
            chunk_id = chunk
            chunk_text = f"Chunk {chunk_id} (referenced)"
        
        # Only add if we haven't seen this chunk ID before
        if chunk_id not in seen_chunks:
            seen_chunks[chunk_id] = chunk_text
    
    # Write deduplicated chunks
    for chunk_id, chunk_text in seen_chunks.items():
        output_content += f"[Chunk {chunk_id}]: {chunk_text}\n\n"
    
    output_content += f"""
ORIGINAL RESUME (FOR REFERENCE):
{'-'*40}
{original_resume}

{'='*80}
Generated by Resume RAG API - End-to-End Smoke Test
"""
    
    # Write to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_content)
        return output_file
    except Exception as e:
        print_error(f"Failed to save output file: {e}")
        return ""

def display_results(results: Dict[str, Any]):
    """Display the tailored resume results."""
    print_section("TAILORED RESUME BULLETS")
    
    bullets = results.get("tailored_bullets", [])
    cited_chunks = results.get("cited_chunks", [])
    
    print(f"\n📝 Generated {len(bullets)} tailored bullet points:\n")
    
    for i, bullet in enumerate(bullets, 1):
        print(f"{i}. {bullet}")
    
    print_section("CITED RESUME CHUNKS")
    
    # Deduplicate chunks by ID for display
    seen_chunks = {}
    for chunk in cited_chunks:
        # Handle both dict format and integer format
        if isinstance(chunk, dict):
            chunk_id = chunk.get("id")
            chunk_text = chunk.get("text", "")
        else:
            # If chunk is just an integer ID
            chunk_id = chunk
            chunk_text = f"Chunk {chunk_id} (referenced)"
        
        # Only add if we haven't seen this chunk ID before
        if chunk_id not in seen_chunks:
            seen_chunks[chunk_id] = chunk_text
    
    print(f"\n📚 {len(seen_chunks)} unique chunks were cited:\n")
    
    for i, (chunk_id, chunk_text) in enumerate(seen_chunks.items(), 1):
        # Truncate long chunks for display
        display_text = chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text
        print(f"{i}. [Chunk {chunk_id}]: {display_text}")

def load_env_file():
    """Load environment variables from .env file."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key and value:
                            os.environ[key] = value
            print(f"✅ Loaded environment variables from {env_file}")
        except Exception as e:
            print(f"⚠️ Warning: Could not load .env file: {e}")
    else:
        print("⚠️ No .env file found")

def verify_environment():
    """Verify that required environment variables are set."""
    print_step("Verifying environment")
    
    # Load .env file first
    load_env_file()
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print_error("OPENAI_API_KEY environment variable not set!")
        print("   Please set your OpenAI API key:")
        print("   export OPENAI_API_KEY='your-api-key-here'")
        return False
    
    print_success("Environment variables verified")
    return True

def main():
    """Run the complete end-to-end smoke test."""
    print_section("RESUME RAG API - SMOKE TEST")
    print(f"Testing API at: {BASE_URL}")
    
    # Load sample data from files
    print_step("Loading sample data from files")
    resume_content, job_description = load_sample_data()
    print_success(f"Loaded resume ({len(resume_content)} chars) and job description ({len(job_description)} chars)")
    
    # Verify environment
    if not verify_environment():
        sys.exit(1)
    
    try:
        # Step 1: Health check
        if not test_health_check():
            sys.exit(1)
        
        # Step 2: Upload resume
        resume_id = upload_resume(resume_content)
        
        # Step 3: Tailor resume
        results = tailor_resume(resume_id, job_description)
        
        # Step 4: Display results
        display_results(results)
        
        # Step 5: Save output resume file
        print_step("Saving tailored resume to output file")
        output_file = save_output_resume(results, resume_content, job_description)
        if output_file:
            print_success(f"Tailored resume saved to: {output_file}")
        
        print_section("SMOKE TEST COMPLETED SUCCESSFULLY! 🎉")
        print("\n✅ All endpoints working correctly")
        print("✅ End-to-end RAG pipeline functional")
        print("✅ Resume successfully tailored to job description")
        print("✅ Sample data loaded from files in samples/ folder")
        if output_file:
            print("✅ Output resume saved to samples/output/ folder")
        
    except KeyboardInterrupt:
        print_error("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()