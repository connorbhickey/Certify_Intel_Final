"""
Certify Intel - Local Embedding Model
======================================
Free embeddings using sentence-transformers all-MiniLM-L6-v2.
384-dimension vectors, <22ms per embedding, runs on CPU.

Config:
    USE_LOCAL_EMBEDDINGS=false (default OFF, uses OpenAI)
"""

import os
import logging
from typing import List

logger = logging.getLogger(__name__)

USE_LOCAL_EMBEDDINGS = os.getenv("USE_LOCAL_EMBEDDINGS", "false").lower() == "true"

_model = None
_model_name = "all-MiniLM-L6-v2"


def _get_model():
    """Lazy-load the embedding model (only when first called)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local embedding model: {_model_name}")
            _model = SentenceTransformer(_model_name)
            logger.info(f"Local embedding model loaded ({_model_name})")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            raise
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a single text string. Returns 384-dim vector."""
    model = _get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Returns list of 384-dim vectors."""
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, batch_size=32)
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """Return the embedding dimension (384 for all-MiniLM-L6-v2)."""
    return 384


def is_available() -> bool:
    """Check if local embeddings are enabled and model can load."""
    if not USE_LOCAL_EMBEDDINGS:
        return False
    try:
        _get_model()
        return True
    except Exception:
        return False
