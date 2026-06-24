"""Pain Points Analysis — the problem list for product/QA teams."""

from __future__ import annotations

from src.reduce.aggregator import AggregationResult
from src.reduce.cross_analysis import CrossAnalysisResult
from src.models.report import PainPoint, PainPointsAnalysis


def generate_pain_points_analysis(
    aggregation: AggregationResult,
    cross: CrossAnalysisResult,
    top_voc: dict[str, list[str]] | None = None,
) -> PainPointsAnalysis:
    """Generate the pain points section of the report.

    Includes: Top-N problem categories, cross-dimensional insights,
    and typical Voice of Customer excerpts.
    """
    top_voc = top_voc or {}

    pain_points = []
    for cs in aggregation.top_pain_categories:
        # Find cross-dimensional insight for this category
        sku_info = ""
        user_info = ""
        for ins in cross.insights:
            if cs.category in ins.metric or cs.category in ins.value:
                if ins.dimension == "SKU":
                    sku_info = f"最集中SKU: {ins.slice_value}"
                elif ins.dimension == "用户等级":
                    user_info = f"影响用户: {ins.slice_value}"

        voc_excerpts = top_voc.get(cs.category, [])

        pain_points.append(PainPoint(
            category=cs.category,
            count=cs.count,
            percentage=cs.percentage,
            top_sku=sku_info or None,
            top_user_segment=user_info or None,
            typical_voc=voc_excerpts[:3],
        ))

    # Build cross-dimension insight strings
    cross_insights = [
        f"[{ins.dimension}] {ins.slice_value}: {ins.value}"
        for ins in cross.insights[:5]
    ]

    return PainPointsAnalysis(
        top_pain_points=pain_points,
        cross_dimension_insights=cross_insights,
    )
