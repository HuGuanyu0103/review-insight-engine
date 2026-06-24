"""Metadata-filtered semantic retriever.

Implements the key insight from the design docs: filter by metadata FIRST,
then perform vector similarity search within the filtered pool.
This dramatically improves precision for queries like "负面反馈"
where the semantic signal is weak but the metadata signal is strong.
"""

import logging
import re
from typing import Optional

from src.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


# Mapping from Chinese query terms to metadata filter fields
SENTIMENT_KEYWORDS = {
    "正面": "正面", "好评": "正面", "满意": "正面", "好": "正面",
    "负面": "负面", "差评": "负面", "不满": "负面", "差": "负面",
    "吐槽": "负面", "投诉": "负面",
    "中性": "中性",
}

CATEGORY_KEYWORDS = {
    "质量": "产品质量", "品质": "产品质量", "材质": "产品质量",
    "物流": "物流配送", "快递": "物流配送", "发货": "物流配送", "配送": "物流配送",
    "客服": "服务态度", "售后": "服务态度", "服务": "服务态度",
    "价格": "价格争议", "性价比": "价格争议", "贵": "价格争议", "降价": "价格争议",
    "便宜": "价格争议",
}


def parse_query_filters(question: str) -> Optional[dict]:
    """Parse a natural language question and extract metadata filters.

    Examples:
        "今天有什么负面反馈？" → {"sentiment": "负面"}
        "物流问题多不多？" → {"primary_category": "物流配送"}
        "Plus会员对质量有哪些差评？" → {"$and": [{"user_tier": "Plus会员"}, {"primary_category": "产品质量"}, {"sentiment": "负面"}]}
    """
    filters = []

    # Check for sentiment keywords
    for kw, sentiment in SENTIMENT_KEYWORDS.items():
        if kw in question:
            filters.append({"sentiment": sentiment})
            break

    # Check for category keywords
    for kw, category in CATEGORY_KEYWORDS.items():
        if kw in question:
            filters.append({"primary_category": category})
            break

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]

    return {"$and": filters}


def retrieve(
    vector_store: VectorStore,
    question: str,
    n_results: int = 10,
    metadata_filter: Optional[dict] = None,
) -> list[dict]:
    """Retrieve relevant reviews with metadata-filtered semantic search.

    Args:
        vector_store: The vector store to query.
        question: User's natural language question.
        n_results: Number of results to return.
        metadata_filter: Optional explicit metadata filter (overrides auto-parsing).

    Returns:
        List of result dicts with id, content, metadata, and distance.
    """
    # Auto-parse metadata filters if not explicitly provided
    if metadata_filter is None:
        metadata_filter = parse_query_filters(question)

    logger.info(
        "Retrieving for: '%s' | Filter: %s | Top-%d",
        question, metadata_filter, n_results,
    )

    result = vector_store.query(
        query_text=question,
        n_results=n_results,
        where=metadata_filter,
    )

    # Flatten ChromaDB result into a list of dicts
    docs = []
    if result.get("ids") and result["ids"][0]:
        for i, doc_id in enumerate(result["ids"][0]):
            docs.append({
                "id": doc_id,
                "content": (
                    result["metadatas"][0][i].get("raw_content", "")
                    if result.get("metadatas") and result["metadatas"][0]
                    else ""
                ),
                "metadata": (
                    result["metadatas"][0][i]
                    if result.get("metadatas") and result["metadatas"][0]
                    else {}
                ),
                "distance": (
                    result["distances"][0][i]
                    if result.get("distances") and result["distances"][0]
                    else 0.0
                ),
            })

    return docs
