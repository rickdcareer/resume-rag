"""
Configuration settings for Resume RAG API.

Loads configuration from config.json and allows environment variable overrides.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

class Config:
    """Central configuration class for Resume RAG API."""
    
    def __init__(self):
        """Load configuration from JSON file and environment variables."""
        self._load_config()
    
    def _load_config(self):
        """Load configuration from config.json with environment variable overrides."""
        # Get the directory where this script is located
        config_dir = Path(__file__).parent
        
        # Determine which config file to use based on ENVIRONMENT variable
        environment = os.getenv("ENVIRONMENT", "").lower()
        
        if environment in ["development", "dev"]:
            config_file = config_dir / "config.development.json"
        elif environment in ["production", "prod"]:
            config_file = config_dir / "config.production.json"
        else:
            config_file = config_dir / "config.json"
        
        # Load JSON configuration
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            print(f"📄 Loaded config from: {config_file.name}")
        except FileNotFoundError:
            print(f"⚠️  Config file not found: {config_file}")
            
            # Try fallback to default config.json
            fallback_file = config_dir / "config.json"
            try:
                with open(fallback_file, 'r') as f:
                    config_data = json.load(f)
                print(f"📄 Using fallback config: {fallback_file.name}")
            except FileNotFoundError:
                print("Using built-in default configuration...")
                config_data = self._get_default_config()
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in config file: {e}")
            raise
        
        # Extract configuration with environment variable overrides
        self._set_database_config(config_data)
        self._set_openai_config(config_data)
        self._set_embedding_config(config_data)
        self._set_processing_config(config_data)
        self._set_retrieval_config(config_data)
        self._set_api_config(config_data)
        self._set_logging_config(config_data)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if JSON file is missing."""
        return {
            "database": {"url": "postgresql://postgres:postgres@localhost:5432/resume_rag"},
            "openai": {"model": "gpt-4o", "temperature": 0.7, "max_tokens": 1000, "timeout": 30},
            "embedding": {"model": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384},
            "processing": {"chunk_max_words": 200, "retrieval_limit": 12},
            "retrieval": {"similarity_metric": "cosine", "distance_threshold": 0.5},
            "api": {"host": "127.0.0.1", "port": 8000, "max_upload_size": 10485760},
            "logging": {"level": "INFO"}
        }
    
    def _set_database_config(self, config_data: Dict[str, Any]):
        """Set database configuration."""
        db_config = config_data.get("database", {})
        self.DATABASE_URL = os.getenv("DB_URL", db_config.get("url", "postgresql://postgres:postgres@localhost:5432/resume_rag"))
    
    def _set_openai_config(self, config_data: Dict[str, Any]):
        """Set OpenAI configuration."""
        openai_config = config_data.get("openai", {})
        
        # API key is always from environment (for security)
        self.OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
        
        # Other settings can be overridden by environment
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", openai_config.get("model", "gpt-4o"))
        self.OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", str(openai_config.get("temperature", 0.7))))
        self.OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", str(openai_config.get("max_tokens", 1000))))
        self.OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", str(openai_config.get("timeout", 30))))
    
    def _set_embedding_config(self, config_data: Dict[str, Any]):
        """Set embedding configuration."""
        embedding_config = config_data.get("embedding", {})
        
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", embedding_config.get("model", "sentence-transformers/all-MiniLM-L6-v2"))
        self.EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", str(embedding_config.get("dimension", 384))))
    
    def _set_processing_config(self, config_data: Dict[str, Any]):
        """Set resume processing configuration."""
        processing_config = config_data.get("processing", {})
        
        self.CHUNK_MAX_WORDS = int(os.getenv("CHUNK_MAX_WORDS", str(processing_config.get("chunk_max_words", 200))))
        self.RETRIEVAL_LIMIT = int(os.getenv("RETRIEVAL_LIMIT", str(processing_config.get("retrieval_limit", 12))))
    
    def _set_retrieval_config(self, config_data: Dict[str, Any]):
        """Set retrieval/similarity configuration."""
        retrieval_config = config_data.get("retrieval", {})
        
        self.SIMILARITY_METRIC = os.getenv("SIMILARITY_METRIC", retrieval_config.get("similarity_metric", "cosine"))
        self.DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", str(retrieval_config.get("distance_threshold", 0.5))))
    
    def _set_api_config(self, config_data: Dict[str, Any]):
        """Set API configuration."""
        api_config = config_data.get("api", {})
        
        self.API_HOST = os.getenv("API_HOST", api_config.get("host", "127.0.0.1"))
        self.API_PORT = int(os.getenv("API_PORT", str(api_config.get("port", 8000))))
        self.MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(api_config.get("max_upload_size", 10485760))))
    
    def _set_logging_config(self, config_data: Dict[str, Any]):
        """Set logging configuration."""
        logging_config = config_data.get("logging", {})
        
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", logging_config.get("level", "INFO"))
    
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present."""
        errors = []
        
        if not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY environment variable is required")
        
        if self.EMBEDDING_DIM != 384 and self.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2":
            errors.append("EMBEDDING_DIM must be 384 for all-MiniLM-L6-v2 model")
        
        if errors:
            print("❌ Configuration errors:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        return True
    
    def print_config_summary(self) -> None:
        """Print a summary of current configuration (without sensitive data)."""
        print("📋 Resume RAG API Configuration:")
        print(f"   Config source: config.json + environment variables")
        print(f"   Database: {self.DATABASE_URL.split('@')[-1] if '@' in self.DATABASE_URL else self.DATABASE_URL}")
        print(f"   OpenAI Model: {self.OPENAI_MODEL}")
        print(f"   Embedding Model: {self.EMBEDDING_MODEL}")
        print(f"   Embedding Dimension: {self.EMBEDDING_DIM}")
        print(f"   Chunk Size: {self.CHUNK_MAX_WORDS} words")
        print(f"   Retrieval Limit: {self.RETRIEVAL_LIMIT} chunks")
        print(f"   Similarity Metric: {self.SIMILARITY_METRIC}")
        print(f"   Distance Threshold: {self.DISTANCE_THRESHOLD}")
        print(f"   API: {self.API_HOST}:{self.API_PORT}")
        print(f"   Log Level: {self.LOG_LEVEL}")
        api_key_status = "✅ Set" if self.OPENAI_API_KEY else "❌ Missing"
        print(f"   OpenAI API Key: {api_key_status}")

# Create a global config instance
config = Config()

# Validate configuration on import
if __name__ == "__main__":
    config.print_config_summary()
    if config.validate_required_settings():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration has errors")