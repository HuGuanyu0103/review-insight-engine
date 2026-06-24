"""LLM extraction client — calls DeepSeek API with structured JSON output.

This is the core of the Map phase. Each call processes a batch of up to 10 reviews
and returns Pydantic-validated ExtractedReview objects.
"""

import json
import logging
import time
from typing import Optional

from openai import OpenAI

from config.settings import get_settings
from src.models.extraction import ExtractedReview, ExtractionBatch
from src.map.prompt_builder import build_system_prompt, build_user_prompt
from src.map.retry_handler import RetryHandler, HITLQueue

logger = logging.getLogger(__name__)


class LLMExtractor:
    """Wraps the DeepSeek API for structured review extraction."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.client = OpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
        )
        self.retry_handler = RetryHandler(
            max_retries=self.settings.max_retries,
            hitl_threshold=self.settings.hitl_confidence_threshold,
        )
        self.hitl_queue = HITLQueue()
        self._system_prompt = build_system_prompt()

    def extract_batch(
        self,
        reviews: list[dict],
        model: Optional[str] = None,
    ) -> list[ExtractedReview]:
        """Extract structured data from a batch of reviews.

        Args:
            reviews: List of dicts with review_id, review_content, rating.
            model: Model override (defaults to settings.deepseek_model).

        Returns:
            List of validated ExtractedReview objects.
        """
        if not reviews:
            return []

        user_prompt = build_user_prompt(reviews)
        model = model or self.settings.deepseek_model

        for attempt in range(1, self.settings.max_retries + 1):
            try:
                raw_output = self._call_api(model, user_prompt)
                parsed = self._parse_response(raw_output)

                # Validate each extraction
                extractions = []
                hitl_items = []

                # Build rating lookup for cross-validation
                rating_lookup = {
                    r.get("review_id"): int(r.get("rating", 0))
                    for r in reviews if r.get("rating")
                }

                for item in parsed:
                    try:
                        extraction = ExtractedReview(**item)

                        # --- HITL Gate 1: Low confidence ---
                        if extraction.confidence < self.settings.hitl_confidence_threshold:
                            hitl_items.append({
                                "review_id": extraction.review_id,
                                "extraction": extraction,
                                "reason": f"Low confidence ({extraction.confidence:.2f} < {self.settings.hitl_confidence_threshold})",
                            })
                            continue

                        # --- HITL Gate 2: 星级-情感交叉验证 ---
                        # 设计文档要求：用户给5星但LLM判负面 → 入人工复核池
                        # 真实评论中5星+负面往往是反讽或数据录入错误
                        rating = rating_lookup.get(extraction.review_id, 0)
                        if rating == 5 and extraction.sentiment.value == "负面":
                            if extraction.confidence < 0.90:
                                hitl_items.append({
                                    "review_id": extraction.review_id,
                                    "extraction": extraction,
                                    "reason": (
                                        f"星级-情感矛盾: {rating}星→判负面"
                                        f" (conf={extraction.confidence:.2f})"
                                    ),
                                })
                                continue

                        # --- HITL Gate 3: 1星→正面（同样可疑）---
                        if rating == 1 and extraction.sentiment.value == "正面":
                            hitl_items.append({
                                "review_id": extraction.review_id,
                                "extraction": extraction,
                                "reason": (
                                    f"星级-情感矛盾: {rating}星→判正面"
                                    f" (conf={extraction.confidence:.2f})"
                                ),
                            })
                            continue

                        extractions.append(extraction)
                    except Exception as e:
                        # Find the original review content for HITL
                        original = next(
                            (r for r in reviews if r.get("review_id") == item.get("review_id")),
                            None
                        )
                        hitl_items.append({
                            "review_id": item.get("review_id", "unknown"),
                            "review_content": original.get("review_content", "") if original else "",
                            "raw_output": json.dumps(item, ensure_ascii=False),
                            "reason": f"Pydantic validation failed: {e}",
                        })

                if hitl_items:
                    self.hitl_queue.add_batch(hitl_items)

                logger.info(
                    "Batch extraction: %d valid, %d → HITL queue",
                    len(extractions), len(hitl_items),
                )
                return extractions

            except Exception as e:
                logger.warning("Extraction attempt %d failed: %s", attempt, e)
                if attempt < self.settings.max_retries:
                    backoff = 2 ** attempt
                    logger.info("Retrying in %ds...", backoff)
                    time.sleep(backoff)
                else:
                    # All retries exhausted — send entire batch to HITL
                    logger.error("All %d retries exhausted for batch", self.settings.max_retries)
                    self.hitl_queue.add_batch([
                        {
                            "review_id": r.get("review_id", "unknown"),
                            "review_content": r.get("review_content", ""),
                            "reason": f"All {self.settings.max_retries} retries failed: {e}",
                        }
                        for r in reviews
                    ])
                    return []

    def _call_api(self, model: str, user_prompt: str) -> str:
        """Make a single API call and return the raw text."""
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for structured extraction
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def _parse_response(self, raw: str) -> list[dict]:
        """Parse the LLM's raw JSON response, stripping markdown fences if needed."""
        text = raw.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array within the text
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(text[start : end + 1])
            else:
                raise

        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")

        return parsed

    def get_hitl_queue(self) -> list[dict]:
        """Return the current HITL (Human-In-The-Loop) queue contents."""
        return self.hitl_queue.items

    def flush_hitl_queue(self, output_path: str):
        """Write the HITL queue to a CSV file for manual review."""
        self.hitl_queue.save(output_path)
