"""Build structured prompts for the Map-phase LLM extraction.

Loads the taxonomy from config/taxonomy.yaml and constructs a system prompt
with CO-STAR inspired framework + Few-shot examples for edge cases
(sarcasm, mixed sentiment, meaningless content).
"""

from __future__ import annotations

import yaml
from pathlib import Path

from config.settings import get_settings

_TAXONOMY_CACHE: dict | None = None


def load_taxonomy() -> dict:
    """Load taxonomy from config/taxonomy.yaml, with in-memory cache."""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE

    settings = get_settings()
    path = Path(settings.taxonomy_path)
    if not path.exists():
        path = Path(__file__).parent.parent.parent / "config" / "taxonomy.yaml"

    with open(path, encoding="utf-8") as f:
        _TAXONOMY_CACHE = yaml.safe_load(f)

    return _TAXONOMY_CACHE


def get_sentiment_options() -> list[str]:
    return load_taxonomy()["sentiment"]


def get_category_options() -> list[str]:
    return load_taxonomy()["primary_category"]


def get_urgency_descriptions() -> dict:
    return load_taxonomy()["urgency_level"]


def get_extraction_constraints() -> dict:
    return load_taxonomy()["extraction_constraints"]


def build_system_prompt() -> str:
    """Build the system prompt with CO-STAR inspired framework + Few-shot.

    The prompt enforces:
    - Closed-set classification (taxonomy-only selection)
    - Strict JSON array output format
    - Keyword and summary length constraints
    - Sarcasm and mixed-sentiment handling via Few-shot
    """
    taxonomy = load_taxonomy()
    sentences = taxonomy["sentiment"]
    categories = taxonomy["primary_category"]
    urgency = taxonomy["urgency_level"]
    constraints = taxonomy["extraction_constraints"]

    sentiment_list = "、".join(sentences)
    category_list = "、".join(categories)
    urgency_desc = "\n".join(f"  {k} = {v}" for k, v in urgency.items())

    prompt = f"""# 角色
你是一个资深电商数据分析师，负责从用户评论中提取结构化信息。

# 任务
分析给定的用户评论，为每条评论输出一个 JSON 对象。

# 约束

## 分类维度（必须从以下枚举中单选）

- **sentiment**（情感极性）：{sentiment_list}
- **primary_category**（问题分类）：{category_list}
- **urgency_level**（紧急程度）：
{urgency_desc}

## 输出字段约束

- core_issue_summary：{constraints['summary_max_chars']} 个中文字符以内，提炼核心问题
- extracted_keywords：{constraints['keyword_min_count']}-{constraints['keyword_max_count']} 个核心实体词，提取具体问题词而非泛词
- confidence：0.0-1.0 的置信度（遇到反讽、歧义时降低至 0.6-0.7）

## 分类指南

- **产品质量**：开胶、掉色、破损、材质差、尺码偏差、气味、舒适度等
- **物流配送**：发货慢、包装破损、丢件、快递员态度、暴力运输等
- **服务态度**：客服回复慢、态度差、推脱责任、退换货流程繁琐等
- **价格争议**：太贵、降价太快、性价比低、不值这个价等
- **无效评论**：纯表情、刷单水军、无意义内容（如"好"、"不错"）、重复字符

## 特殊场景识别

- **反讽/阴阳怪气**：如"真是买了个祖宗回来" → 真实情感为负面。识别语气反转。
- **混合评价**：如"鞋子好看但磨脚" → 情感标注为"混合"
- **明贬暗褒**：如"太浮夸了，不过本仙女就是喜欢" → 真实情感为正面
- **无实质内容**：如纯数字"1111"、纯表情"😂" → 分类为"无效评论"

## 输出格式

只输出纯 JSON 数组，不要包裹在 markdown 代码块中。

---

# 示例（Few-shot）

**示例 1 — 反讽识别**
评论: "真是买了个活爹回来，供着吧不能穿"
输出:
```json
[{{
  "review_id": "S001",
  "sentiment": "负面",
  "primary_category": "产品质量",
  "urgency_level": 2,
  "core_issue_summary": "鞋子质量极差无法穿着",
  "extracted_keywords": ["质量差", "无法穿"],
  "confidence": 0.75
}}]
```

**示例 2 — 无意义内容**
评论: "111111"
输出:
```json
[{{
  "review_id": "S002",
  "sentiment": "中性",
  "primary_category": "无效评论",
  "urgency_level": 1,
  "core_issue_summary": "无实质内容",
  "extracted_keywords": ["无意义"],
  "confidence": 0.98
}}]
```

**示例 3 — 明贬暗褒**
评论: "太浮夸了，不过本仙女就是喜欢这种全场焦点的感觉！"
输出:
```json
[{{
  "review_id": "S003",
  "sentiment": "正面",
  "primary_category": "产品质量",
  "urgency_level": 1,
  "core_issue_summary": "外观设计出众用户满意",
  "extracted_keywords": ["外观", "设计感", "满意"],
  "confidence": 0.80
}}]
```

**示例 4 — 混合情感**
评论: "质量不错穿着舒服但价格有点贵性价比不高"
输出:
```json
[{{
  "review_id": "S004",
  "sentiment": "混合",
  "primary_category": "价格争议",
  "urgency_level": 1,
  "core_issue_summary": "质量好但价格偏贵",
  "extracted_keywords": ["质量好", "价格贵", "性价比低"],
  "confidence": 0.92
}}]
```

**示例 5 — 纯正面**
评论: "鞋子质量很好穿着很舒服透气性也不错"
输出:
```json
[{{
  "review_id": "S005",
  "sentiment": "正面",
  "primary_category": "产品质量",
  "urgency_level": 1,
  "core_issue_summary": "质量好做工扎实透气",
  "extracted_keywords": ["质量好", "舒适", "透气"],
  "confidence": 0.95
}}]
```

---

现在开始分析以下评论。记住：只从给定枚举中选择，输出纯 JSON 数组。"""

    return prompt


def build_user_prompt(reviews: list[dict]) -> str:
    """Build the user prompt containing the batch of reviews to analyze.

    Args:
        reviews: List of dicts with review_id and review_content.
    """
    lines = ["请分析以下用户评论：\n"]
    for i, r in enumerate(reviews, 1):
        review_id = r.get("review_id", f"R{i}")
        content = r.get("review_content", "")
        rating = r.get("rating", "")
        rating_hint = f" [评分: {rating}星]" if rating else ""
        lines.append(f"{i}. [{review_id}]{rating_hint} {content}")

    lines.append("\n请为以上每一条评论输出一个 JSON 对象，以 JSON 数组形式返回。")
    return "\n".join(lines)
