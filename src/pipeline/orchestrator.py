"""Pipeline orchestrator — wires the full Map-Reduce-RAG-Report flow.

Sole entry point for end-to-end execution:
  parse → filter → map (LLM extract) → reduce (stats) → rag (vector store) → report
"""

import json
import logging
from pathlib import Path
from typing import Optional

from src.pipeline.state import PipelineState, StageStatus
from src.input.csv_parser import parse_csv
from src.input.filters import filter_reviews
from src.map.batcher import chunk_reviews, reviews_to_dicts
from src.map.llm_extractor import LLMExtractor
from src.rag.vector_store import VectorStore
from src.report.generator import generate_report
from src.models.extraction import ExtractedReview

logger = logging.getLogger(__name__)


def _simple_keyword_extract(text: str) -> list[str]:
    """Simple keyword extraction for no-LLM mode — splits text and returns top words."""
    import re
    # Extract 2-4 char Chinese phrases
    words = re.findall(r"[一-鿿]{2,4}", text)
    # Filter common stop words
    stop = {"的是", "还是", "这个", "那个", "一个", "不是", "就是", "可以", "没有", "什么"}
    words = [w for w in words if w not in stop]
    # Deduplicate and take top 3
    seen = set()
    result = []
    for w in words:
        if w not in seen:
            seen.add(w)
            result.append(w)
        if len(result) >= 3:
            break
    return result if result else ["评论文本"]


class Pipeline:
    """Orchestrates the full comment insight pipeline."""

    def __init__(self, input_path: str, output_dir: str = "./outputs/",
                 use_llm: bool = True, state_path: Optional[str] = None,
                 column_mapping: Optional[dict] = None):
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.use_llm = use_llm
        self.column_mapping = column_mapping or {}
        self.state = PipelineState()
        self.state_path = state_path or str(self.output_dir / "pipeline_state.json")

        # Ensure output directories exist
        for sub in ("structured", "reports", "vectordb", "hitl"):
            (self.output_dir / sub).mkdir(parents=True, exist_ok=True)

    def run(self) -> dict:
        """Execute the full pipeline end-to-end.

        Returns a summary dict with key metrics from each stage.
        """
        self.state.start(str(self.input_path))
        summary = {}

        # ---- Stage 1: Parse ----
        logger.info("=" * 60)
        logger.info("Stage 1/5: Parsing CSV input...")
        self.state.parse_status = StageStatus.RUNNING
        try:
            raw_reviews = parse_csv(str(self.input_path), column_mapping=self.column_mapping)
            self.state.parse_count = len(raw_reviews)
            self.state.parse_status = StageStatus.COMPLETED
            summary["parsed"] = len(raw_reviews)
            logger.info("Parsed %d reviews", len(raw_reviews))
        except Exception as e:
            self.state.parse_status = StageStatus.FAILED
            logger.error("Parse failed: %s", e)
            raise

        # ---- Stage 2: Filter ----
        logger.info("Stage 2/5: Filtering low-quality reviews...")
        self.state.filter_status = StageStatus.RUNNING
        kept_reviews, filtered_log = filter_reviews(raw_reviews)
        self.state.filter_kept = len(kept_reviews)
        self.state.filter_dropped = len(filtered_log)
        self.state.filter_status = StageStatus.COMPLETED
        summary["kept"] = len(kept_reviews)
        summary["filtered"] = len(filtered_log)
        logger.info(
            "Filtered: %d kept, %d removed (%.1f%% pass rate)",
            len(kept_reviews), len(filtered_log),
            100 * len(kept_reviews) / max(len(raw_reviews), 1),
        )

        # Save filter log
        with open(self.output_dir / "structured" / "filter_log.json", "w", encoding="utf-8") as f:
            json.dump(filtered_log, f, ensure_ascii=False, indent=2)

        # ---- Stage 3: Map (LLM Extraction) ----
        logger.info("Stage 3/5: Map phase — LLM structured extraction...")
        self.state.map_status = StageStatus.RUNNING

        chunks = chunk_reviews(kept_reviews, chunk_size=10)
        self.state.map_batches = len(chunks)

        all_extractions: list[ExtractedReview] = []
        extractor = LLMExtractor() if self.use_llm else None

        if extractor and self.use_llm:
            for i, chunk in enumerate(chunks, 1):
                logger.info("Processing batch %d/%d (%d reviews)...", i, len(chunks), len(chunk))
                dicts = reviews_to_dicts(chunk)
                batch_results = extractor.extract_batch(dicts)
                all_extractions.extend(batch_results)
                logger.info("Batch %d: %d extracted", i, len(batch_results))

            # Save HITL queue
            hitl_path = str(self.output_dir / "hitl" / "hitl_queue.csv")
            extractor.flush_hitl_queue(hitl_path)
            self.state.map_hitl = len(extractor.get_hitl_queue())
        else:
            # No-LLM mode: rule-based extraction for testing
            logger.info("LLM disabled — using rule-based extraction for testing")
            for chunk in chunks:
                for r in chunk:
                    from src.models.extraction import Sentiment, PrimaryCategory

                    # Sentiment from rating
                    if r.rating >= 4:
                        sentiment = Sentiment.POSITIVE
                    elif r.rating <= 2:
                        sentiment = Sentiment.NEGATIVE
                    else:
                        sentiment = Sentiment.NEUTRAL

                    # Category from keyword matching
                    content = r.review_content
                    if any(kw in content for kw in ["物流", "快递", "发货", "配送"]):
                        cat = PrimaryCategory.LOGISTICS
                    elif any(kw in content for kw in ["客服", "售后", "服务"]):
                        cat = PrimaryCategory.CUSTOMER_SERVICE
                    elif any(kw in content for kw in ["价格", "贵", "性价比", "降价", "便宜"]):
                        cat = PrimaryCategory.PRICE_VALUE
                    else:
                        cat = PrimaryCategory.PRODUCT_QUALITY

                    # Urgency from rating and keywords
                    urgency = 1
                    if r.rating <= 2:
                        urgency = 2
                    if any(kw in content for kw in ["爆炸", "有毒", "过敏", "受伤", "欺诈"]):
                        urgency = 3

                    all_extractions.append(ExtractedReview(
                        review_id=r.review_id,
                        sentiment=sentiment,
                        primary_category=cat,
                        urgency_level=urgency,
                        core_issue_summary=content[:15],
                        extracted_keywords=_simple_keyword_extract(content),
                        confidence=0.6,
                    ))

        self.state.map_extracted = len(all_extractions)
        self.state.map_status = StageStatus.COMPLETED
        summary["extracted"] = len(all_extractions)
        summary["hitl"] = self.state.map_hitl
        logger.info("Map phase complete: %d extractions, %d in HITL", len(all_extractions), self.state.map_hitl)

        # Save structured results
        structured_path = self.output_dir / "structured" / "extracted.json"
        with open(structured_path, "w", encoding="utf-8") as f:
            json.dump(
                [e.model_dump() for e in all_extractions],
                f, ensure_ascii=False, indent=2, default=str,
            )
        logger.info("Structured results saved: %s", structured_path)

        # Build reviews_lookup from original reviews for cross-analysis
        reviews_lookup = {}
        for r in kept_reviews:
            reviews_lookup[r.review_id] = {
                "product_id": r.product_id,
                "product_name": r.product_name,
                "user_tier": r.user_tier,
                "review_timestamp": r.review_timestamp,
                "order_price": r.order_price,
                "review_content": r.review_content,
                "rating": r.rating,
            }

        # ---- Stage 4: Reduce + Report ----
        logger.info("Stage 4/5: Reduce phase + Report generation...")
        self.state.reduce_status = StageStatus.RUNNING

        report = generate_report(all_extractions, reviews_lookup, use_llm=self.use_llm)
        summary["report"] = report.input_summary

        self.state.reduce_status = StageStatus.COMPLETED
        self.state.report_status = StageStatus.COMPLETED

        # Save report
        report_path = self.output_dir / "reports" / "insight_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, ensure_ascii=False, indent=2, default=str)
        logger.info("Report saved: %s", report_path)

        # ---- Stage 5: RAG ----
        logger.info("Stage 5/5: RAG vector store construction...")
        self.state.rag_status = StageStatus.RUNNING

        vector_store = VectorStore(persist_path=str(self.output_dir / "vectordb"))
        vector_store.delete_collection()

        # Collect data for vector store ingestion
        rag_ids = []
        rag_contents = []
        rag_summaries = []
        rag_keywords = []
        rag_sentiments = []
        rag_categories = []
        rag_urg = []
        rag_products = []
        rag_tiers = []
        rag_ratings = []
        rag_timestamps = []

        for e in all_extractions:
            lookup = reviews_lookup.get(e.review_id, {})
            rag_ids.append(e.review_id)
            rag_contents.append(lookup.get("review_content", ""))
            rag_summaries.append(e.core_issue_summary)
            rag_keywords.append(e.extracted_keywords)
            rag_sentiments.append(e.sentiment.value)
            rag_categories.append(e.primary_category.value)
            rag_urg.append(e.urgency_level)
            rag_products.append(lookup.get("product_id", ""))
            rag_tiers.append(lookup.get("user_tier") or "")
            rag_ratings.append(lookup.get("rating", 0))
            ts = lookup.get("review_timestamp")
            rag_timestamps.append(str(ts) if ts else "")

        if rag_ids:
            vector_store.add_reviews(
                review_ids=rag_ids,
                review_contents=rag_contents,
                core_issue_summaries=rag_summaries,
                extracted_keywords_list=rag_keywords,
                sentiments=rag_sentiments,
                categories=rag_categories,
                urgency_levels=rag_urg,
                product_ids=rag_products,
                user_tiers=rag_tiers,
                ratings=rag_ratings,
                timestamps=rag_timestamps,
            )

        self.state.rag_doc_count = vector_store.count()
        self.state.rag_status = StageStatus.COMPLETED
        summary["rag_docs"] = self.state.rag_doc_count
        logger.info("RAG store: %d documents indexed", self.state.rag_doc_count)

        # ---- Finalize ----
        self.state.save(self.state_path)
        logger.info("Pipeline complete! Summary: %s", summary)

        return summary
