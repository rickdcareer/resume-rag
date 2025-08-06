"""HuggingFace sentence-transformers embedder using configurable model."""

from sentence_transformers import SentenceTransformer
import torch
from typing import List
import logging
from config import config

# Set up logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Model configuration from config
MODEL_NAME = config.EMBEDDING_MODEL
EMBEDDING_DIM = config.EMBEDDING_DIM

class HuggingFaceEmbedder:
    """Local embedder using sentence-transformers MiniLM model."""
    
    def __init__(self, model_name: str = MODEL_NAME):
        """Initialize the embedder with the specified model."""
        logger.info(f"Loading sentence transformer model: {model_name}")
        
        # Load the model
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.embedding_dim = EMBEDDING_DIM
        
        logger.info(f"✅ Model loaded successfully. Embedding dimension: {self.embedding_dim}")
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        if not texts:
            return []
        
        # Convert to embeddings
        embeddings = self.model.encode(texts, convert_to_tensor=False, normalize_embeddings=True)
        
        # Convert numpy arrays to lists for JSON serialization
        if hasattr(embeddings, 'tolist'):
            embeddings = embeddings.tolist()
        
        # Ensure we return a list of lists
        if len(texts) == 1 and not isinstance(embeddings[0], list):
            embeddings = [embeddings]
        
        logger.info(f"Encoded {len(texts)} texts into {len(embeddings)} embeddings")
        return embeddings
    
    def encode_single(self, text: str) -> List[float]:
        """
        Encode a single text into an embedding.
        
        Args:
            text: Text string to encode
            
        Returns:
            Single embedding as a list of floats
        """
        return self.encode([text])[0]


# Global embedder instance
logger.info("Initializing global embedder instance...")
embedder = HuggingFaceEmbedder()
logger.info("✅ Global embedder ready")
