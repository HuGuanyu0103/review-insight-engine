"""AI Recommendations — LLM-generated action items from data."""

from __future__ import annotations

from src.reduce.aggregator import AggregationResult
from src.reduce.cross_analysis import CrossAnalysisResult
from src.models.report import Recommendation


def generate_recommendations(
    aggregation: AggregationResult,
    cross: CrossAnalysisResult,
    ai_suggestions: list[str] | None = None,
) -> list[Recommendation]:
    """Generate the AI recommendations section.

    Transforms LLM-generated suggestions into structured Recommendation objects.
    """
    if not ai_suggestions:
        # Rule-based fallback (empty list or None)
        ai_suggestions = _rule_based_recommendations(aggregation)

    recommendations = []
    for i, suggestion in enumerate(ai_suggestions[:5]):
        priority = 1 if i == 0 else (2 if i < 3 else 3)

        # Infer category from suggestion text
        category = "GENERAL"
        for cat_keyword in ["质量", "品质", "产品"]:
            if cat_keyword in suggestion:
                category = "产品质量"
                break
        for cat_keyword in ["物流", "快递", "发货"]:
            if cat_keyword in suggestion:
                category = "物流配送"
                break
        for cat_keyword in ["客服", "服务", "售后"]:
            if cat_keyword in suggestion:
                category = "服务态度"
                break
        for cat_keyword in ["价格", "性价比", "降价"]:
            if cat_keyword in suggestion:
                category = "价格争议"
                break

        recommendations.append(Recommendation(
            priority=priority,
            category=category,
            suggestion=suggestion.lstrip("0123456789.、 ") if suggestion else "",
            evidence=f"基于 {aggregation.total_reviews} 条评论分析",
        ))

    return recommendations


def _rule_based_recommendations(aggregation: AggregationResult) -> list[str]:
    """Fallback rule-based recommendations when LLM is unavailable."""
    suggestions = []
    for i, pc in enumerate(aggregation.top_pain_categories[:3]):
        priority_tag = "【紧急】" if pc.avg_urgency >= 2.5 else ""
        suggestions.append(
            f"{priority_tag}针对{pc.category}问题（占比{pc.percentage}%），"
            f"建议优先排查相关SKU并与供应商沟通改进方案，"
            f"监控未来一周内差评率变化趋势。"
        )
    return suggestions
