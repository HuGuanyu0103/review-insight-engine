"""ChromaDB vector store with metadata filtering support.

Stores review embeddings along with structured metadata
(sentiment, category, urgency, product_id, user_tier, etc.)
to enable metadata-filtered semantic search.
"""

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import get_settings
from src.rag.embeddings import embed_texts, build_searchable_text

logger = logging.getLogger(__name__)

COLLECTION_NAME = "review_insights"


class VectorStore:
    """ChromaDB-backed vector store for review embeddings.

    Each document stores:
    - The searchable text (summary + keywords + raw content)
    - Metadata: sentiment, primary_category, urgency_level, product_id,
      user_tier, review_timestamp, extracted_keywords, core_issue_summary
    """

    def __init__(self, persist_path: Optional[str] = None):
        settings = get_settings()
        self.persist_path = persist_path or settings.vectordb_path
        Path(self.persist_path).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_reviews(
        self,
        review_ids: list[str],
        review_contents: list[str],
        core_issue_summaries: list[str],
        extracted_keywords_list: list[list[str]],
        sentiments: list[str],
        categories: list[str],
        urgency_levels: list[int],
        product_ids: list[str],
        user_tiers: list[str],
        ratings: list[int],
        timestamps: list[str],
    ):
        """Add a batch of reviews to the vector store.

        Each review is stored with its embedding and all structured metadata.
        """
        if not review_ids:
            return

        # Build searchable text (semantic noise reduction)
        searchable_texts = [
            build_searchable_text(
                review_content=content,
                core_issue_summary=summary,
                extracted_keywords=keywords,
            )
            for content, summary, keywords in zip(
                review_contents, core_issue_summaries, extracted_keywords_list
            )
        ]

        # Generate embeddings
        embeddings = embed_texts(searchable_texts)

        # Build metadata
        metadatas = []
        for i in range(len(review_ids)):
            metadatas.append({
                "review_id": review_ids[i],
                "sentiment": sentiments[i] if i < len(sentiments) else "",
                "primary_category": categories[i] if i < len(categories) else "",
                "urgency_level": urgency_levels[i] if i < len(urgency_levels) else 0,
                "product_id": product_ids[i] if i < len(product_ids) else "",
                "user_tier": user_tiers[i] if i < len(user_tiers) else "",
                "rating": ratings[i] if i < len(ratings) else 0,
                "timestamp": str(timestamps[i]) if i < len(timestamps) else "",
                "core_issue_summary": core_issue_summaries[i] if i < len(core_issue_summaries) else "",
                "keywords": ",".join(extracted_keywords_list[i]) if i < len(extracted_keywords_list) else "",
                "raw_content": review_contents[i] if i < len(review_contents) else "",
            })

        # Insert into ChromaDB
        self.collection.add(
            ids=review_ids,
            embeddings=embeddings,
            documents=searchable_texts,
            metadatas=metadatas,
        )

        logger.info("Added %d reviews to vector store", len(review_ids))

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        where: Optional[dict] = None,
        include_metadata: bool = True,
        include_documents: bool = True,
    ) -> dict:
        """Query the vector store with optional metadata filtering.

        Args:
            query_text: Natural language query.
            n_results: Number of results to return.
            where: ChromaDB where clause for metadata filtering.
                   Example: {"sentiment": "负面"}
                   Example: {"$and": [{"sentiment": "负面"}, {"primary_category": "产品质量"}]}
            include_metadata: Include metadata in results.
            include_documents: Include document text in results.

        Returns:
            ChromaDB query result dict.
        """
        # Embed the query
        query_embedding = embed_texts([query_text])[0]

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["metadatas", "documents", "distances"] if include_metadata else ["documents"],
        )

    def count(self) -> int:
        """Return the total number of reviews in the store."""
        return self.collection.count()

    def delete_collection(self):
        """Delete the entire collection and recreate it."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store collection reset")

    def get_by_id(self, review_id: str) -> Optional[dict]:
        """Retrieve a single review by ID."""
        result = self.collection.get(
            ids=[review_id],
            include=["metadatas", "documents"],
        )
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "metadata": result["metadatas"][0] if result["metadatas"] else {},
                "document": result["documents"][0] if result["documents"] else "",
            }
        return None
