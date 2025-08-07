#!/usr/bin/env python3
"""
Database cleanup utility for Resume RAG.

This script clears all data from the database to start fresh.
Useful when you've made changes to chunking algorithms or data models
and want to remove old/stale data.

Usage:
    python scripts/clear_database.py [--confirm]

Options:
    --confirm    Skip the confirmation prompt (use with caution!)

What gets cleared:
    - All resume records
    - All resume chunks (embedded text pieces)
    - All embeddings
    - Resets auto-increment counters

Note: This is IRREVERSIBLE! Make sure you have backups if needed.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to Python path so we can import our modules
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

try:
    from sqlalchemy import text
    from app.database import SessionLocal, engine
    from app.models.tables import Resume, ResumeChunk, Base
    import logging
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root and all dependencies are installed.")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def print_header():
    """Print script header."""
    print("=" * 60)
    print("  RESUME RAG DATABASE CLEANUP UTILITY")
    print("=" * 60)
    print()

def print_warning():
    """Print warning about data loss."""
    print("⚠️  WARNING: This will permanently delete ALL data:")
    print("   • All uploaded resumes")
    print("   • All resume chunks and embeddings")
    print("   • All tailoring history")
    print()
    print("💡 This is useful when:")
    print("   • You've updated the chunking algorithm")
    print("   • You want to start fresh with new test data")
    print("   • You're cleaning up after development/testing")
    print()

def confirm_deletion() -> bool:
    """Ask user to confirm the deletion."""
    response = input("Are you sure you want to clear the database? (type 'yes' to confirm): ")
    return response.lower() == 'yes'

def get_table_counts(db) -> dict:
    """Get current record counts for all tables."""
    try:
        resume_count = db.query(Resume).count()
        chunk_count = db.query(ResumeChunk).count()
        
        return {
            'resumes': resume_count,
            'chunks': chunk_count
        }
    except Exception as e:
        logger.warning(f"Could not get table counts: {e}")
        return {'resumes': '?', 'chunks': '?'}

def clear_database():
    """Clear all data from the database."""
    db = SessionLocal()
    
    try:
        # Get counts before deletion
        print("📊 Current database state:")
        counts = get_table_counts(db)
        print(f"   • Resumes: {counts['resumes']}")
        print(f"   • Resume chunks: {counts['chunks']}")
        print()
        
        if counts['resumes'] == 0 and counts['chunks'] == 0:
            print("✅ Database is already empty!")
            return True
        
        print("🗑️  Clearing database...")
        
        # Delete in correct order (chunks first due to foreign key constraints)
        chunk_count = db.query(ResumeChunk).count()
        db.query(ResumeChunk).delete()
        print(f"   ✅ Deleted {chunk_count} resume chunks")
        
        resume_count = db.query(Resume).count() 
        db.query(Resume).delete()
        print(f"   ✅ Deleted {resume_count} resumes")
        
        # Reset auto-increment sequences (SQLite)
        try:
            db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('resumes', 'resume_chunks')"))
            print("   ✅ Reset auto-increment counters")
        except Exception as e:
            logger.warning(f"Could not reset auto-increment: {e}")
        
        # Commit all changes
        db.commit()
        
        # Verify cleanup
        final_counts = get_table_counts(db)
        print()
        print("📊 Database state after cleanup:")
        print(f"   • Resumes: {final_counts['resumes']}")
        print(f"   • Resume chunks: {final_counts['chunks']}")
        
        if final_counts['resumes'] == 0 and final_counts['chunks'] == 0:
            print()
            print("🎉 Database successfully cleared!")
            print("   You can now upload resumes with the improved chunking algorithm.")
            return True
        else:
            print()
            print("⚠️  Database may not be completely cleared. Check the counts above.")
            return False
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error clearing database: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def main():
    """Main script function."""
    parser = argparse.ArgumentParser(description="Clear Resume RAG database")
    parser.add_argument('--confirm', action='store_true', 
                       help='Skip confirmation prompt (use with caution!)')
    args = parser.parse_args()
    
    print_header()
    print_warning()
    
    # Confirm deletion unless --confirm flag is used
    if not args.confirm:
        if not confirm_deletion():
            print("❌ Operation cancelled.")
            return
    else:
        print("🤖 Auto-confirmed via --confirm flag")
    
    print()
    
    # Perform the cleanup
    success = clear_database()
    
    print()
    if success:
        print("✅ Database cleanup completed successfully!")
        print("💡 Next steps:")
        print("   1. Run your smoke test: python scripts/smoke_demo.py")
        print("   2. Check that new resumes are chunked properly")
    else:
        print("❌ Database cleanup failed. Check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()