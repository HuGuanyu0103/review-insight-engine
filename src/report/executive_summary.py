"""Executive Summary — the 1-minute read for business leads."""

from src.reduce.aggregator import AggregationResult
from src.reduce.trend_detector import TrendResult
from src.models.report import ExecutiveSummary


def generate_executive_summary(
    aggregation: AggregationResult,
    trend: TrendResult,
    narrative: str = "",
) -> ExecutiveSummary:
    """Generate the executive summary section of the report.

    Designed to answer: "What do I need to know right now?"
    """
    s = aggregation.sentiment_dist
    health = s.health_score

    # Red alerts — from top pain categories and spikes
    red_alerts = []
    for pc in aggregation.top_pain_categories[:2]:
        red_alerts.append(
            f"「{pc.category}」问题占比 {pc.percentage}%，共 {pc.count} 条"
        )

    for spike in trend.spikes[:2]:
        red_alerts.append(
            f"「{spike.issue}」异常突增：历史 {spike.historical_avg_pct}% → "
            f"当期 {spike.current_pct}%（{spike.multiplier}x）"
        )

    # Highlights — from positive reviews
    highlights = []
    if s.positive_pct > 60:
        highlights.append(f"整体好评率 {health}%，用户口碑良好")
    if s.positive > s.negative * 2:
        highlights.append(f"好评数({s.positive})远超差评数({s.negative})")

    return ExecutiveSummary(
        health_score=health,
        health_trend=f"共 {aggregation.total_reviews} 条评论，好评率 {health}%",
        red_alerts=red_alerts,
        highlights=highlights,
    )
