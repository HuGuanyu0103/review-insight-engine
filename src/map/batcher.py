"""Batch reviews into fixed-size chunks for LLM processing.

Adheres to the Chunk Size constraint: never more than 10 reviews per batch.
"""

from src.models.review import RawReview


def chunk_reviews(
    reviews: list[RawReview],
    chunk_size: int = 10,
) -> list[list[RawReview]]:
    """Split a list of reviews into chunks of at most chunk_size each.

    Args:
        reviews: List of parsed and filtered reviews.
        chunk_size: Maximum number of reviews per chunk (default 10, max 10).

    Returns:
        List of chunks, each containing up to chunk_size reviews.
    """
    if chunk_size > 10:
        raise ValueError(
            f"chunk_size must be ≤ 10 to prevent context-window "
            f"forgetting and data loss. Got {chunk_size}."
        )

    chunks = []
    for i in range(0, len(reviews), chunk_size):
        chunks.append(reviews[i : i + chunk_size])
    return chunks


def reviews_to_dicts(reviews: list[RawReview]) -> list[dict]:
    """Convert RawReview objects to plain dicts for the LLM prompt.

    Only includes the fields the LLM needs for extraction.
    """
    return [
        {
            "review_id": r.review_id,
            "review_content": r.review_content,
            "rating": r.rating,
        }
        for r in reviews
    ]
