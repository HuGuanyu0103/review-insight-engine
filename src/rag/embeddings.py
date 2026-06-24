"""Embedding generation for review content.

Supports both local models (sentence-transformers) and a lightweight
hash-based fallback for offline/testing scenarios.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

import numpy as np

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Default embedding dimension (must match across all calls for ChromaDB consistency)
EMBEDDING_DIM = 768  # matches BAAI/bge-large-zh-v1.5 output dim

_EMBEDDING_MODEL = None  # lazily loaded SentenceTransformer or None
_MODEL_LOAD_FAILED = False
_MODEL_LOAD_ATTEMPTED = False


def _try_load_sentence_transformer(model_name: str):
    """Attempt to load a sentence-transformers model.

    Only attempts if USE_SENTENCE_TRANSFORMERS env var is set to '1' or 'true'.
    Otherwise skips directly to hash-based fallback (no network calls).
    """
    global _EMBEDDING_MODEL, _MODEL_LOAD_FAILED, _MODEL_LOAD_ATTEMPTED

    if _MODEL_LOAD_ATTEMPTED:
        return

    _MODEL_LOAD_ATTEMPTED = True

    # Check if user explicitly enabled sentence-transformers
    import os
    if os.environ.get("USE_SENTENCE_TRANSFORMERS", "").lower() not in ("1", "true"):
        _MODEL_LOAD_FAILED = True
        logger.info(
            "USE_SENTENCE_TRANSFORMERS not set — using hash-based embeddings. "
            "Set USE_SENTENCE_TRANSFORMERS=1 to enable semantic embeddings "
            "(requires network to download model on first use)."
        )
        return

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s (first use downloads ~1.3GB)...", model_name)
        _EMBEDDING_MODEL = SentenceTransformer(model_name)
        logger.info("Embedding model loaded successfully.")
    except Exception as e:
        _MODEL_LOAD_FAILED = True
        logger.warning(
            "Cannot load sentence-transformers model '%s': %s. "
            "Falling back to hash-based embeddings.",
            model_name, e,
        )


def _hash_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic hash-based embedding — zero-dependency offline fallback.

    Uses salted MD5 hashes to project text into a fixed-dimension pseudo-random
    vector, then L2-normalizes. Not semantically meaningful, but sufficient for
    pipeline testing and basic keyword overlap retrieval.
    """
    vec = np.zeros(dim, dtype=np.float32)
    text_bytes = text.encode("utf-8", errors="replace")
    for i in range(dim):
        h = hashlib.md5(text_bytes + f":{i}".encode()).digest()
        # Map to [-1, 1]
        vec[i] = (int.from_bytes(h[:4], "big") / 0x7FFFFFFF) - 1.0
    norm = np.linalg.norm(vec)
    if norm > 1e-8:
        vec = vec / norm
    return vec.tolist()


def embed_texts(
    texts: list[str],
    model: Optional[object] = None,
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Uses sentence-transformers if available, otherwise falls back to
    hash-based pseudo-embeddings.

    Args:
        texts: List of text strings to embed.
        model: Optional pre-loaded SentenceTransformer.

    Returns:
        List of embedding vectors (list[float] of length EMBEDDING_DIM).
    """
    if not texts:
        return []

    # Try to load the real model if not already attempted
    if _EMBEDDING_MODEL is None and not _MODEL_LOAD_FAILED:
        settings = get_settings()
        _try_load_sentence_transformer(settings.embedding_model)

    # Use real model if available
    m = model or _EMBEDDING_MODEL
    if m is not None:
        try:
            embeddings = m.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.warning("Sentence-transformer encode failed: %s. Using fallback.", e)

    # Hash-based fallback
    logger.debug("Using hash-based embeddings for %d texts", len(texts))
    return [_hash_embed(t) for t in texts]


def build_searchable_text(
    review_content: str,
    core_issue_summary: str = "",
    extracted_keywords: list[str] | None = None,
) -> str:
    """Build a dense, high-signal text for embedding.

    Strategy: concatenate the LLM-extracted summary and keywords with the
    original text, giving higher weight to the extracted signal. This
    "semantic noise reduction" drastically improves RAG hit rate.

    The summary and keywords are duplicated (appear twice) relative to
    the raw content, effectively up-weighting the extracted signal in
    the embedding space.
    """
    parts = []

    # Extracted signal (high density — appears twice for weighting)
    if core_issue_summary:
        parts.append(core_issue_summary)
        parts.append(core_issue_summary)  # weight boost

    if extracted_keywords:
        parts.append(" ".join(extracted_keywords))
        parts.append(" ".join(extracted_keywords))  # weight boost

    # Raw content (lower density)
    parts.append(review_content)

    return " | ".join(parts)
