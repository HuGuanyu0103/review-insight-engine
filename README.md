# 商品评论洞察引擎 (User Voice AI)

AI-powered e-commerce review insight engine. Turn thousands of user reviews into actionable business insights in minutes.

## 核心能力

- **智能提取**：LLM 自动从评论文本中提取情感、问题分类、紧急度、关键词
- **统计分析**：Pandas 驱动的精确聚合分析（零统计幻觉）
- **交叉下钻**：按 SKU、用户等级、价格带多维度切片分析
- **趋势监控**：时间序列趋势 + 异常突增检测
- **语义检索**：Metadata 过滤 + 向量相似度匹配，支持自然语言下钻追问
- **AI 报告**：4 模块 Actionable 报告（结论摘要 + 槽点分析 + 趋势监控 + 改进建议）

## 快速开始

### 1. 安装

```bash
# 安装 uv（如果没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
cd 评论洞察引擎
uv pip install -e .
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

### 3. 运行

```bash
# 端到端运行（需要 API Key）
uv run uvoice run --input data/samples/sample_reviews.csv

# 无 LLM 模式（规则提取，用于测试）
uv run uvoice run --input data/samples/sample_reviews.csv --no-llm

# RAG 问答
uv run uvoice ask --question "鞋子掉色问题主要集中在什么颜色？"

# 启动 API 服务
uv run uvoice serve --port 8000
```

## 架构

```
CSV 输入 → 过滤清洗 → Map (LLM提取/批10条) → Reduce (Pandas统计)
                ↓                                    ↓
         RAG 向量库 (ChromaDB)                   Actionable 报告
                ↓
          语义问答 (Metadata过滤 + 向量检索)
```

## 项目结构

```
src/
├── models/      Pydantic 数据模型（枚举约束 + 文本总结）
├── input/       CSV 解析 + 低质量过滤
├── map/         LLM 提取链路（prompt → batch → extract → retry/HITL）
├── reduce/      Pandas 聚合 + 交叉分析 + 趋势检测 + LLM 叙事
├── rag/         Embedding + ChromaDB + 检索 + QA 引擎
├── report/      4 模块报告生成
├── pipeline/    端到端编排器
└── delivery/    CLI (Rich) + FastAPI
```

## API 端点

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/upload` | 上传 CSV，触发分析 |
| GET | `/api/status/{job_id}` | 查询任务状态 |
| GET | `/api/report/{job_id}` | 获取报告 |
| POST | `/api/ask` | RAG 问答 |
| GET | `/api/hitl/{job_id}` | 查看人工复核队列 |

启动后访问 `http://localhost:8000/docs` 查看完整 API 文档。
