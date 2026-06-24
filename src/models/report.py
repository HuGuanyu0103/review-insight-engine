"""Report data models for the four-module insight report."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExecutiveSummary(BaseModel):
    """结论摘要 — 给业务负责人的一句话总结."""
    health_score: float = Field(..., description="整体好评率百分比")
    health_trend: str = Field(default="", description="环比变化描述")
    red_alerts: list[str] = Field(default_factory=list, description="核心警报列表")
    highlights: list[str] = Field(default_factory=list, description="高光亮点列表")


class PainPoint(BaseModel):
    """单个痛点条目."""
    category: str = Field(..., description="问题分类")
    count: int = Field(..., ge=0, description="提及次数")
    percentage: float = Field(..., ge=0, le=100, description="占比百分比")
    top_sku: Optional[str] = Field(default=None, description="问题最集中的SKU")
    top_user_segment: Optional[str] = Field(default=None, description="问题最集中的用户群")
    typical_voc: list[str] = Field(default_factory=list, description="典型用户原声 2-3条")


class PainPointsAnalysis(BaseModel):
    """吐槽重灾区分析 — Top 3 负面标签 + 交叉下钻."""
    top_pain_points: list[PainPoint] = Field(default_factory=list)
    cross_dimension_insights: list[str] = Field(default_factory=list)


class TrendPoint(BaseModel):
    """单个时间点的情感数据."""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0


class SpikeAlert(BaseModel):
    """突增异常告警."""
    issue: str = Field(..., description="异常问题描述")
    historical_ratio: float = Field(..., description="历史占比(%)")
    current_ratio: float = Field(..., description="当前占比(%)")
    severity: str = Field(default="WARNING", description="严重级别")


class TrendAnomalyReport(BaseModel):
    """趋势与异动监控."""
    trend_data: list[TrendPoint] = Field(default_factory=list)
    spike_alerts: list[SpikeAlert] = Field(default_factory=list)


class Recommendation(BaseModel):
    """AI 改进建议."""
    priority: int = Field(..., ge=1, le=3, description="优先级 1=最高")
    category: str = Field(..., description="关联的问题分类")
    suggestion: str = Field(..., description="具体可执行的建议")
    evidence: str = Field(default="", description="支撑数据")


class InsightReport(BaseModel):
    """完整的商品评论洞察报告."""
    generated_at: datetime = Field(default_factory=datetime.now)
    input_summary: str = Field(default="", description="数据源概览（评论总数、时间范围等）")
    executive_summary: ExecutiveSummary = Field(default_factory=lambda: ExecutiveSummary(health_score=0.0))
    pain_points: PainPointsAnalysis = Field(default_factory=PainPointsAnalysis)
    trend_anomaly: TrendAnomalyReport = Field(default_factory=TrendAnomalyReport)
    recommendations: list[Recommendation] = Field(default_factory=list)
