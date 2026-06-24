"""Pandas-based statistical aggregator — the "Reduce" phase.

Computes all aggregate statistics using Pandas (never LLM) to guarantee
zero hallucination in numbers. Outputs are fed to the report generator.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.models.extraction import ExtractedReview, Sentiment, PrimaryCategory

logger = logging.getLogger(__name__)


@dataclass
class SentimentDistribution:
    """Sentiment polarity distribution."""
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    mixed: int = 0

    @property
    def total(self) -> int:
        return self.positive + self.negative + self.neutral + self.mixed

    @property
    def positive_pct(self) -> float:
        return 100 * self.positive / max(self.total, 1)

    @property
    def negative_pct(self) -> float:
        return 100 * self.negative / max(self.total, 1)

    @property
    def health_score(self) -> float:
        """Health score = positive% + neutral% (approximate 好评率)."""
        return round(self.positive_pct + (100 * self.neutral / max(self.total, 1)), 1)


@dataclass
class CategoryStat:
    """Statistics for a single category."""
    category: str = ""
    count: int = 0
    percentage: float = 0.0
    avg_urgency: float = 0.0


@dataclass
class AggregationResult:
    """Complete aggregation results from the Reduce phase."""
    total_reviews: int = 0
    sentiment_dist: SentimentDistribution = field(default_factory=SentimentDistribution)
    category_stats: list[CategoryStat] = field(default_factory=list)
    urgency_dist: dict[int, int] = field(default_factory=dict)
    top_pain_categories: list[CategoryStat] = field(default_factory=list)


def extractions_to_dataframe(extractions: list[ExtractedReview]) -> pd.DataFrame:
    """Convert a list of ExtractedReview objects to a Pandas DataFrame."""
    records = []
    for e in extractions:
        records.append({
            "review_id": e.review_id,
            "sentiment": e.sentiment.value,
            "primary_category": e.primary_category.value,
            "urgency_level": e.urgency_level,
            "core_issue_summary": e.core_issue_summary,
            "extracted_keywords": ",".join(e.extracted_keywords),
            "confidence": e.confidence,
        })
    return pd.DataFrame(records)


def compute_sentiment_distribution(df: pd.DataFrame) -> SentimentDistribution:
    """Compute sentiment polarity counts and percentages."""
    if "sentiment" not in df.columns or df.empty:
        return SentimentDistribution()

    counts = df["sentiment"].value_counts()
    return SentimentDistribution(
        positive=int(counts.get(Sentiment.POSITIVE.value, 0)),
        negative=int(counts.get(Sentiment.NEGATIVE.value, 0)),
        neutral=int(counts.get(Sentiment.NEUTRAL.value, 0)),
        mixed=int(counts.get(Sentiment.MIXED.value, 0)),
    )


def compute_category_distribution(df: pd.DataFrame) -> list[CategoryStat]:
    """Compute category distribution, excluding IRRELEVANT."""
    if "primary_category" not in df.columns or df.empty:
        return []

    # Exclude IRRELEVANT from stats
    relevant = df[df["primary_category"] != PrimaryCategory.IRRELEVANT.value]
    total = max(len(relevant), 1)
    counts = relevant["primary_category"].value_counts()

    stats = []
    for cat, count in counts.items():
        avg_urgency = (
            relevant[relevant["primary_category"] == cat]["urgency_level"].mean()
            if "urgency_level" in df.columns else 0
        )
        stats.append(CategoryStat(
            category=cat,
            count=int(count),
            percentage=round(100 * int(count) / total, 1),
            avg_urgency=round(avg_urgency, 2),
        ))

    # Sort by count descending
    stats.sort(key=lambda x: x.count, reverse=True)
    return stats


def compute_top_pain_points(df: pd.DataFrame, top_n: int = 3) -> list[CategoryStat]:
    """Get the Top-N negative problem categories."""
    if "primary_category" not in df.columns or "sentiment" not in df.columns or df.empty:
        return []

    negative = df[df["sentiment"] == Sentiment.NEGATIVE.value]
    negative = negative[negative["primary_category"] != PrimaryCategory.IRRELEVANT.value]

    total_neg = max(len(negative), 1)
    counts = negative["primary_category"].value_counts()

    result = []
    for cat, count in counts.head(top_n).items():
        result.append(CategoryStat(
            category=cat,
            count=int(count),
            percentage=round(100 * int(count) / total_neg, 1),
        ))
    return result


def compute_urgency_distribution(df: pd.DataFrame) -> dict[int, int]:
    """Compute urgency level distribution."""
    if "urgency_level" not in df.columns or df.empty:
        return {}
    counts = df["urgency_level"].value_counts().to_dict()
    return {int(k): int(v) for k, v in counts.items()}


def aggregate(extractions: list[ExtractedReview]) -> AggregationResult:
    """Run all aggregations on the extraction results.

    This is the main entry point for the Reduce phase.
    """
    if not extractions:
        logger.warning("No extractions to aggregate — returning empty result")
        return AggregationResult()

    df = extractions_to_dataframe(extractions)
    sentiment = compute_sentiment_distribution(df)
    category_stats = compute_category_distribution(df)
    top_pain = compute_top_pain_points(df)
    urgency = compute_urgency_distribution(df)

    logger.info(
        "Aggregation complete: %d reviews, health score %.1f%%, %d categories",
        len(extractions), sentiment.health_score, len(category_stats),
    )

    return AggregationResult(
        total_reviews=len(extractions),
        sentiment_dist=sentiment,
        category_stats=category_stats,
        urgency_dist=urgency,
        top_pain_categories=top_pain,
    )
