"""LLM-powered narrative generator — converts statistics into business prose.

IMPORTANT: The LLM here ONLY summarizes pre-computed statistics.
It NEVER invents numbers or performs calculations. This prevents
statistical hallucinations while still leveraging LLM language ability.
"""

import logging

from openai import OpenAI

from config.settings import get_settings
from src.reduce.aggregator import AggregationResult, SentimentDistribution, CategoryStat
from src.reduce.cross_analysis import CrossAnalysisResult
from src.reduce.trend_detector import TrendResult, SpikeAlert

logger = logging.getLogger(__name__)


def _get_client():
    settings = get_settings()
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


NARRATIVE_SYSTEM_PROMPT = """你是一个电商数据分析师。你的任务是将分析数据转化为业务视角的摘要。
关键规则：
1. 只使用给定的数据，绝对不要编造任何数字
2. 用中文输出，简洁专业
3. 聚焦在可行动的洞察上"""


def generate_executive_narrative(
    aggregation: AggregationResult,
    trend: TrendResult,
) -> str:
    """Generate the executive summary narrative from stats."""
    if aggregation.total_reviews == 0:
        return "暂无数据可供分析。"

    s = aggregation.sentiment_dist
    health = s.health_score

    # Build data summary for LLM
    data_summary = f"""## 数据概览
- 总评论数: {aggregation.total_reviews}
- 整体好评率: {health}%
- 正面: {s.positive}条 ({s.positive_pct:.1f}%)
- 负面: {s.negative}条 ({s.negative_pct:.1f}%)
- 中性: {s.neutral}条
- 混合: {s.mixed}条

## Top 问题分类
"""
    for i, cs in enumerate(aggregation.top_pain_categories[:3], 1):
        data_summary += f"{i}. {cs.category}: {cs.count}条 ({cs.percentage}%)\n"

    if trend.spikes:
        data_summary += "\n## 异常突增告警\n"
        for spike in trend.spikes:
            data_summary += (
                f"- {spike.issue}: 历史{spike.historical_avg_pct}% → "
                f"当期{spike.current_pct}% ({spike.multiplier}x)\n"
            )

    prompt = f"{data_summary}\n\n请基于以上数据，用一段话（80-120字）概括本期评论洞察的核心发现，包括整体健康度、最值得关注的问题、以及任何异常趋势。"

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=get_settings().deepseek_model,
            messages=[
                {"role": "system", "content": NARRATIVE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.warning("LLM narrative generation failed: %s", e)
        # Fallback: rule-based summary
        top_issue = aggregation.top_pain_categories[0] if aggregation.top_pain_categories else None
        parts = [
            f"本期共分析{aggregation.total_reviews}条评论，整体好评率{health}%。",
        ]
        if top_issue:
            parts.append(
                f"最突出问题为{top_issue.category}，占比{top_issue.percentage}%。"
            )
        if trend.spikes:
            parts.append(f"检测到{len(trend.spikes)}个异常突增点，建议重点关注。")
        return "".join(parts)


def generate_recommendations(
    aggregation: AggregationResult,
    cross: CrossAnalysisResult,
) -> list[str]:
    """Generate actionable AI recommendations based on the data."""
    if not aggregation.top_pain_categories:
        return []

    top = aggregation.top_pain_categories

    # Build structured data for LLM
    data = f"""## Top 3 问题分类
"""
    for i, cs in enumerate(top[:3], 1):
        data += f"{i}. {cs.category}: {cs.count}条差评 ({cs.percentage}%), 平均紧急度{cs.avg_urgency}\n"

    if cross.insights:
        data += "\n## 交叉分析发现\n"
        for ins in cross.insights[:5]:
            data += f"- [{ins.dimension}] {ins.slice_value}: {ins.value}\n"

    prompt = (
        f"{data}\n\n"
        "请基于以上数据，生成3条具体的、可执行的改进建议（Action Items）。"
        "每条建议必须包含：问题→具体措施→预期效果。用中文输出，每条不超过50字。"
        "格式：每条一行，以数字开头。"
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=get_settings().deepseek_model,
            messages=[
                {"role": "system", "content": NARRATIVE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=500,
        )
        text = response.choices[0].message.content or ""
        # Parse numbered lines
        lines = [l.strip() for l in text.split("\n") if l.strip() and l.strip()[0].isdigit()]
        return lines[:5]
    except Exception as e:
        logger.warning("LLM recommendation generation failed: %s", e)
        return [
            f"1. 针对{top[0].category}问题（占比{top[0].percentage}%），建议优先排查相关SKU并联系供应商。",
            f"2. 针对{top[1].category if len(top) > 1 else top[0].category}问题，建议监控退货率变化趋势。",
            f"3. 建议在详情页补充尺码/材质说明以降低预期落差。",
        ]
