"""Cross-dimensional analysis — slice & dice by SKU, user tier, time, and price."""

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.models.extraction import ExtractedReview, Sentiment, PrimaryCategory

logger = logging.getLogger(__name__)


@dataclass
class DimInsight:
    """A single cross-dimensional insight."""
    dimension: str          # e.g. "SKU", "user_tier", "price_tier"
    slice_value: str        # e.g. "XL码", "Plus会员"
    metric: str             # e.g. "负面占比", "投诉数"
    value: str              # Human-readable value
    detail: str = ""        # Extended context


@dataclass
class CrossAnalysisResult:
    """Results from cross-dimensional slicing."""
    insights: list[DimInsight] = field(default_factory=list)
    sku_breakdown: list[dict] = field(default_factory=list)
    user_tier_breakdown: list[dict] = field(default_factory=list)


def analyze_by_sku(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
    top_n: int = 5,
) -> list[dict]:
    """Analyze which SKUs have the most negative reviews.

    Needs the original reviews for SKU/product_id information since
    ExtractedReview doesn't carry it natively — we join on review_id.
    """
    # Build a df joining extraction results with original product metadata
    records = []
    for e in extractions:
        original = reviews_lookup.get(e.review_id, {})
        product_id = original.get("product_id", "unknown")
        product_name = original.get("product_name", product_id)
        records.append({
            "review_id": e.review_id,
            "product_id": product_id,
            "product_name": product_name,
            "sentiment": e.sentiment.value,
            "primary_category": e.primary_category.value,
        })

    if not records:
        return []

    df = pd.DataFrame(records)
    negative = df[df["sentiment"] == Sentiment.NEGATIVE.value]

    results = []
    for sku, group in negative.groupby("product_id"):
        total_reviews_for_sku = len(df[df["product_id"] == sku])
        neg_count = len(group)
        neg_pct = 100 * neg_count / max(total_reviews_for_sku, 1)
        top_issue = group["primary_category"].mode()
        product_name = group["product_name"].iloc[0] if len(group) > 0 else sku

        results.append({
            "sku": sku,
            "product_name": product_name,
            "negative_count": neg_count,
            "negative_pct": round(neg_pct, 1),
            "total_reviews": total_reviews_for_sku,
            "top_issue": top_issue.iloc[0] if len(top_issue) > 0 else "N/A",
        })

    results.sort(key=lambda x: x["negative_count"], reverse=True)
    return results[:top_n]


def analyze_by_user_tier(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
) -> list[dict]:
    """Analyze sentiment distribution by user membership tier."""
    records = []
    for e in extractions:
        original = reviews_lookup.get(e.review_id, {})
        user_tier = original.get("user_tier", "未知")
        records.append({
            "review_id": e.review_id,
            "user_tier": user_tier,
            "sentiment": e.sentiment.value,
            "primary_category": e.primary_category.value,
            "urgency_level": e.urgency_level,
        })

    if not records:
        return []

    df = pd.DataFrame(records)
    results = []

    for tier, group in df.groupby("user_tier"):
        total = len(group)
        neg_count = len(group[group["sentiment"] == Sentiment.NEGATIVE.value])
        high_urgency = len(group[group["urgency_level"] == 3])
        results.append({
            "user_tier": tier,
            "total_reviews": total,
            "negative_count": neg_count,
            "negative_pct": round(100 * neg_count / max(total, 1), 1),
            "high_urgency_count": high_urgency,
        })

    results.sort(key=lambda x: x["negative_pct"], reverse=True)
    return results


def analyze_by_price_tier(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
) -> list[dict]:
    """Analyze sentiment by price tier."""
    records = []
    for e in extractions:
        original = reviews_lookup.get(e.review_id, {})
        price = original.get("order_price")
        if price is None:
            continue

        # Bucket into price tiers
        if price < 100:
            tier_label = "低价 (<100)"
        elif price < 300:
            tier_label = "中价 (100-300)"
        elif price < 600:
            tier_label = "高价 (300-600)"
        else:
            tier_label = "超高价 (>600)"

        records.append({
            "review_id": e.review_id,
            "price_tier": tier_label,
            "sentiment": e.sentiment.value,
        })

    if not records:
        return []

    df = pd.DataFrame(records)
    results = []
    for tier, group in df.groupby("price_tier"):
        total = len(group)
        neg = len(group[group["sentiment"] == Sentiment.NEGATIVE.value])
        results.append({
            "price_tier": tier,
            "total_reviews": total,
            "negative_count": neg,
            "negative_pct": round(100 * neg / max(total, 1), 1),
        })

    return results


def cross_analyze(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
) -> CrossAnalysisResult:
    """Run all cross-dimensional analyses."""
    sku = analyze_by_sku(extractions, reviews_lookup)
    tier = analyze_by_user_tier(extractions, reviews_lookup)
    price = analyze_by_price_tier(extractions, reviews_lookup)

    insights: list[DimInsight] = []

    # Generate human-readable insights
    for s in sku[:3]:
        insights.append(DimInsight(
            dimension="SKU",
            slice_value=s["product_name"],
            metric="差评集中度",
            value=f"{s['negative_count']}条差评（{s['negative_pct']}%），主要问题：{s['top_issue']}",
        ))

    for t in tier:
        if t["negative_pct"] > 30:
            insights.append(DimInsight(
                dimension="用户等级",
                slice_value=t["user_tier"],
                metric="差评率",
                value=f"{t['negative_pct']}%（{t['negative_count']}/{t['total_reviews']}）",
                detail=f"其中{t['high_urgency_count']}条高优先级",
            ))

    return CrossAnalysisResult(
        insights=insights,
        sku_breakdown=sku,
        user_tier_breakdown=tier,
    )
