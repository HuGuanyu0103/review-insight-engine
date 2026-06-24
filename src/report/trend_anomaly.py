"""Trend & Anomaly Detection report — dynamic monitoring for ops teams."""

from src.reduce.trend_detector import TrendResult, SpikeAlert
from src.models.report import TrendPoint, SpikeAlert as SpikeAlertModel, TrendAnomalyReport


def generate_trend_anomaly_report(trend: TrendResult) -> TrendAnomalyReport:
    """Generate the trend and anomaly section of the report.

    Includes: daily sentiment trend line and spike/outbreak alerts.
    """
    trend_data = [
        TrendPoint(
            date=td.date,
            positive_count=td.positive,
            negative_count=td.negative,
            neutral_count=td.neutral,
        )
        for td in trend.trend_data
    ]

    spike_alerts = [
        SpikeAlertModel(
            issue=s.issue,
            historical_ratio=s.historical_avg_pct,
            current_ratio=s.current_pct,
            severity=s.severity,
        )
        for s in trend.spikes
    ]

    return TrendAnomalyReport(
        trend_data=trend_data,
        spike_alerts=spike_alerts,
    )
