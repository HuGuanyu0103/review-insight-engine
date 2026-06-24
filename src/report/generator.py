"""Report generator orchestrator — assembles the 4-module report."""

import logging
from pathlib import Path
from datetime import datetime, timezone

from src.models.report import InsightReport
from src.models.extraction import ExtractedReview, Sentiment
from src.reduce.aggregator import aggregate, AggregationResult
from src.reduce.cross_analysis import cross_analyze, CrossAnalysisResult
from src.reduce.trend_detector import compute_trend, TrendResult
from src.reduce.narrative_gen import generate_executive_narrative, generate_recommendations as gen_recs
from src.report.executive_summary import generate_executive_summary
from src.report.pain_points import generate_pain_points_analysis
from src.report.trend_anomaly import generate_trend_anomaly_report
from src.report.recommendations import generate_recommendations

logger = logging.getLogger(__name__)


def extract_top_voc(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
    max_per_category: int = 3,
) -> dict[str, list[str]]:
    """Extract representative Voice of Customer quotes per pain category."""
    from src.reduce.aggregator import extractions_to_dataframe
    import pandas as pd

    df = extractions_to_dataframe(extractions)
    negative = df[df["sentiment"] == Sentiment.NEGATIVE.value]

    voc: dict[str, list[str]] = {}
    for category, group in negative.groupby("primary_category"):
        contents = []
        for _, row in group.head(max_per_category).iterrows():
            original = reviews_lookup.get(row["review_id"], {})
            content = original.get("review_content", row.get("core_issue_summary", ""))
            if isinstance(content, str) and len(content) > 5:
                contents.append(content[:150])
        voc[category] = contents

    return voc


def generate_report(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
    use_llm: bool = True,
) -> InsightReport:
    """Generate a complete 4-module insight report.

    Args:
        extractions: LLM-extracted review data.
        reviews_lookup: Original RawReview data keyed by review_id.
        use_llm: Whether to use LLM for narrative generation (True) or
                 fallback to rule-based (False).

    Returns:
        A complete InsightReport object.
    """
    if not extractions:
        return InsightReport(
            input_summary="无有效评论数据",
        )

    # Run all analyses
    logger.info("Starting report generation with %d extractions...", len(extractions))

    aggregation = aggregate(extractions)
    cross = cross_analyze(extractions, reviews_lookup)
    trend = compute_trend(extractions, reviews_lookup)
    top_voc = extract_top_voc(extractions, reviews_lookup)

    # Generate LLM-powered narratives (with fallback)
    exec_narrative = ""
    ai_suggestions = []
    if use_llm:
        exec_narrative = generate_executive_narrative(aggregation, trend)
        ai_suggestions = gen_recs(aggregation, cross)

    # Build report modules
    exec_summary = generate_executive_summary(aggregation, trend, exec_narrative)
    pain_points = generate_pain_points_analysis(aggregation, cross, top_voc)
    trend_anomaly = generate_trend_anomaly_report(trend)
    recommendations = generate_recommendations(aggregation, cross, ai_suggestions)

    # Build input summary
    date_range = trend.date_range or "N/A"
    input_summary = (
        f"共分析 {aggregation.total_reviews} 条评论"
        f"（时间范围: {date_range}）"
        f" | 健康度: {aggregation.sentiment_dist.health_score}%"
    )

    report = InsightReport(
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        input_summary=input_summary,
        executive_summary=exec_summary,
        pain_points=pain_points,
        trend_anomaly=trend_anomaly,
        recommendations=recommendations,
    )

    logger.info("Report generation complete.")
    return report
