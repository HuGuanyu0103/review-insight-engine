"""Retry handler and HITL (Human-In-The-Loop) queue management.

Handles automatic retry logic for JSON parse failures and maintains
a queue of low-confidence items for manual review.
"""

import csv
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class RetryHandler:
    """Manages retry attempts for failed extraction calls."""

    def __init__(self, max_retries: int = 3, hitl_threshold: float = 0.7):
        self.max_retries = max_retries
        self.hitl_threshold = hitl_threshold
        self.retry_count: dict[str, int] = {}

    def should_retry(self, review_id: str, attempt: int) -> bool:
        """Check if we should retry for this review."""
        return attempt < self.max_retries

    def is_low_confidence(self, confidence: float) -> bool:
        """Check if a confidence score falls below the HITL threshold."""
        return confidence < self.hitl_threshold


class HITLQueue:
    """Stores items that require manual review.

    Items end up here when:
    - LLM extraction confidence is below the threshold
    - JSON parsing fails after all retries
    - Pydantic validation fails
    """

    def __init__(self):
        self.items: list[dict] = []

    def add(self, review_id: str, review_content: str = "",
             reason: str = "", raw_output: str = "", retry_count: int = 0):
        """Add a single item to the HITL queue."""
        self.items.append({
            "review_id": review_id,
            "review_content": review_content[:200],
            "failure_reason": reason,
            "raw_llm_output": raw_output[:500] if raw_output else "",
            "retry_count": retry_count,
            "timestamp": datetime.now().isoformat(),
        })

    def add_batch(self, items: list[dict]):
        """Add multiple HITL items at once."""
        for item in items:
            self.items.append({
                "review_id": item.get("review_id", "unknown"),
                "review_content": item.get("review_content", "")[:200],
                "failure_reason": item.get("reason", ""),
                "raw_llm_output": str(item.get("raw_output", ""))[:500],
                "retry_count": item.get("retry_count", 0),
                "timestamp": datetime.now().isoformat(),
            })

    def save(self, output_path: str):
        """Persist the HITL queue to a CSV file for manual review."""
        if not self.items:
            logger.info("HITL queue is empty, nothing to save.")
            return

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "review_id", "review_content", "failure_reason",
            "raw_llm_output", "retry_count", "timestamp"
        ]

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in self.items:
                writer.writerow({k: item.get(k, "") for k in fieldnames})

        logger.info("HITL queue saved: %d items → %s", len(self.items), path)

    def clear(self):
        """Clear the HITL queue."""
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)
