"""Trend detection and anomaly/spike detection on time-series sentiment data."""

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.models.extraction import ExtractedReview, Sentiment

logger = logging.getLogger(__name__)


@dataclass
class TrendPoint:
    """A single data point in the sentiment trend."""
    date: str
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    mixed: int = 0

    @property
    def total(self) -> int:
        return self.positive + self.negative + self.neutral + self.mixed

    @property
    def health_pct(self) -> float:
        return round(100 * (self.positive + self.neutral) / max(self.total, 1), 1)


@dataclass
class SpikeAlert:
    """An anomaly/spike detected in the data."""
    issue: str
    historical_avg_pct: float
    current_pct: float
    multiplier: float
    severity: str = "WARNING"


@dataclass
class TrendResult:
    """Complete trend analysis result."""
    trend_data: list[TrendPoint] = field(default_factory=list)
    spikes: list[SpikeAlert] = field(default_factory=list)
    date_range: str = ""


def compute_trend(
    extractions: list[ExtractedReview],
    reviews_lookup: dict[str, dict],
) -> TrendResult:
    """Compute daily sentiment trend from extraction results.

    Joins extraction data with original review timestamps to build
    a time series of sentiment counts per day.
    """
    if not extractions:
        return TrendResult()

    # Build records with dates
    records = []
    for e in extractions:
        original = reviews_lookup.get(e.review_id, {})
        ts = original.get("review_timestamp")

        if ts is None:
            continue

        if hasattr(ts, "strftime"):
            date_str = ts.strftime("%Y-%m-%d")
        else:
            date_str = str(ts)[:10]

        records.append({
            "date": date_str,
            "sentiment": e.sentiment.value,
            "primary_category": e.primary_category.value,
        })

    if not records:
        return TrendResult()

    df = pd.DataFrame(records)

    # Pivot: date × sentiment
    pivot = df.pivot_table(
        index="date",
        columns="sentiment",
        aggfunc="size",
        fill_value=0,
    )

    trend_data: list[TrendPoint] = []
    for date_idx in sorted(pivot.index):
        row = pivot.loc[date_idx]
        trend_data.append(TrendPoint(
            date=str(date_idx),
            positive=int(row.get(Sentiment.POSITIVE.value, 0)),
            negative=int(row.get(Sentiment.NEGATIVE.value, 0)),
            neutral=int(row.get(Sentiment.NEUTRAL.value, 0)),
            mixed=int(row.get(Sentiment.MIXED.value, 0)),
        ))

    # Spike detection
    spikes = detect_spikes(trend_data, df)

    date_range = ""
    if trend_data:
        date_range = f"{trend_data[0].date} ~ {trend_data[-1].date}"

    return TrendResult(
        trend_data=trend_data,
        spikes=spikes,
        date_range=date_range,
    )


def detect_spikes(
    trend_data: list[TrendPoint],
    detail_df: pd.DataFrame,
    threshold_multiplier: float = 2.0,
) -> list[SpikeAlert]:
    """Detect category spikes using a simple threshold method.

    Compares the current period's category proportion against
    the historical average. A spike is flagged when the current
    proportion exceeds threshold_multiplier × historical average.
    """
    if not trend_data or len(trend_data) < 2:
        return []

    # Split into historical (all but last day) and current (last day)
    historical_dates = [p.date for p in trend_data[:-1]]
    current_date = trend_data[-1].date

    hist_df = detail_df[detail_df["date"].isin(historical_dates)]
    curr_df = detail_df[detail_df["date"] == current_date]

    if hist_df.empty or curr_df.empty:
        return []

    spikes: list[SpikeAlert] = []

    for category in detail_df["primary_category"].unique():
        hist_total = max(len(hist_df), 1)
        curr_total = max(len(curr_df), 1)

        hist_count = len(hist_df[hist_df["primary_category"] == category])
        curr_count = len(curr_df[curr_df["primary_category"] == category])

        hist_pct = 100 * hist_count / hist_total
        curr_pct = 100 * curr_count / curr_total

        if hist_pct > 0 and curr_pct > threshold_multiplier * hist_pct:
            severity = "CRITICAL" if curr_pct > 3 * hist_pct else "WARNING"
            spikes.append(SpikeAlert(
                issue=category,
                historical_avg_pct=round(hist_pct, 1),
                current_pct=round(curr_pct, 1),
                multiplier=round(curr_pct / max(hist_pct, 0.01), 1),
                severity=severity,
            ))

    spikes.sort(key=lambda s: s.multiplier, reverse=True)
    return spikes


def detect_urgency_spikes(extractions: list[ExtractedReview]) -> list[str]:
    """Detect reviews with urgency level 3 — real-time alert candidates."""
    critical = [e for e in extractions if e.urgency_level == 3]
    if critical:
        logger.warning(
            "⚠️  %d critical (level-3) reviews detected — webhook trigger recommended",
            len(critical),
        )
        return [
            f"[{e.review_id}] {e.core_issue_summary}"
            for e in critical
        ]
    return []
