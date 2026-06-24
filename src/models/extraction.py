"""LLM structured extraction output models.

These models define the contract between the Map phase (LLM extraction)
and the Reduce/RAG phases. The enum fields guarantee statistical convergence;
the summary fields improve RAG retrieval density.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---- 分类枚举类 (Enum-constrained — 统计用，零容忍幻觉) ----


class Sentiment(str, Enum):
    """情感极性 — 用于情感健康度监控和 RAG metadata 过滤."""
    POSITIVE = "正面"
    NEGATIVE = "负面"
    NEUTRAL = "中性"
    MIXED = "混合"


class PrimaryCategory(str, Enum):
    """一级问题模块 — 用于宏观报表 Top-N 和 RAG metadata 过滤."""
    PRODUCT_QUALITY = "产品质量"
    LOGISTICS = "物流配送"
    CUSTOMER_SERVICE = "服务态度"
    PRICE_VALUE = "价格争议"
    IRRELEVANT = "无效评论"


class UrgencyLevel(int, Enum):
    """紧急程度 — 用于阈值报警和优先级排序."""
    LOW = 1       # 低优（颜色偏好等）
    MEDIUM = 2    # 中优（发货慢等）
    HIGH = 3      # 高优/红线（安全问题等）


# ---- 核心提取模型 ----


class ExtractedReview(BaseModel):
    """A single review after LLM structured extraction.

    Fields are split into:
    - Enum-constrained fields: for deterministic Pandas groupby and RAG metadata filters
    - Text-summary fields: for semantic noise reduction and improved RAG hit rate
    """

    review_id: str = Field(..., description="Maps back to the original review")

    # Enum-constrained fields
    sentiment: Sentiment = Field(..., description="情感极性 (POSITIVE/NEGATIVE/NEUTRAL/MIXED)")
    primary_category: PrimaryCategory = Field(
        ..., description="一级问题模块 (PRODUCT_QUALITY/LOGISTICS/CUSTOMER_SERVICE/PRICE_VALUE/IRRELEVANT)"
    )
    urgency_level: int = Field(
        ..., ge=1, le=3, description="紧急程度: 1=低优, 2=中优, 3=高优/红线"
    )

    # Text-summary fields
    core_issue_summary: str = Field(
        ..., max_length=15, description="一句话核心痛点（≤15中文字符）"
    )
    extracted_keywords: list[str] = Field(
        ..., min_length=1, max_length=5, description="实体关键词池（1-5个核心词）"
    )

    # Confidence
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="LLM 自评置信度 (0.0-1.0)"
    )

    @field_validator("urgency_level")
    @classmethod
    def validate_urgency(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError(f"urgency_level must be 1, 2, or 3, got {v}")
        return v


class ExtractionBatch(BaseModel):
    """A batch of extractions returned by the LLM for one chunk of reviews."""

    extractions: list[ExtractedReview] = Field(..., min_length=1)

    @field_validator("extractions")
    @classmethod
    def validate_unique_ids(cls, v: list[ExtractedReview]) -> list[ExtractedReview]:
        ids = [e.review_id for e in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate review_id in extraction batch")
        return v


class HITLItem(BaseModel):
    """A single item in the Human-In-The-Loop review queue."""

    review_id: str
    review_content: str
    raw_llm_output: Optional[str] = None
    failure_reason: str
    retry_count: int = 0
