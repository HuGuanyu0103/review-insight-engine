"""RAG Q&A engine — natural language question answering with citations.

Key design principles (from the design doc):
1. Answer ONLY based on the retrieved reviews
2. If the answer is not in the reviews, honestly say "未在评论中找到相关反馈"
3. Attach numbered citations [1][2]... linking back to original reviews
4. Return the top matched review excerpts for traceability
"""

import logging
from typing import Optional

from openai import OpenAI

from config.settings import get_settings
from src.rag.vector_store import VectorStore
from src.rag.retriever import retrieve

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """你是一个电商评论数据分析助手。你的回答必须严格遵守以下规则：

1. **只基于提供的评论原文回答问题**。如果答案不在给定的评论中，你必须诚实地说"未在评论中找到相关反馈"，绝对不要编造。
2. **在回答中使用引用标记**。引用某条评论时，在句末标注 [1]、[2] 等编号。
3. **归纳而非罗列**。不要逐条复述评论，而是总结出共性的结论。
4. **保留可溯源性**。回答末尾列出引用的评论原文摘要。
5. 用简洁的中文回答。"""


class QAEngine:
    """RAG-based question answering engine."""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()
        settings = get_settings()
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model

    def ask(self, question: str, n_results: int = 10) -> dict:
        """Answer a natural language question using RAG.

        Args:
            question: User's natural language question.
            n_results: Number of reviews to retrieve.

        Returns:
            Dict with:
            - answer: The generated answer with citations
            - citations: List of cited review excerpts
            - retrieved_count: Number of reviews retrieved
        """
        # Step 1: Retrieve relevant reviews
        docs = retrieve(
            vector_store=self.vector_store,
            question=question,
            n_results=n_results,
        )

        if not docs:
            return {
                "answer": "未在评论中找到相关反馈。请确认向量库中已导入评论数据。",
                "citations": [],
                "retrieved_count": 0,
            }

        # Step 2: Build context from retrieved reviews
        context_parts = []
        for i, doc in enumerate(docs, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            context_parts.append(
                f"[{i}] (情感:{metadata.get('sentiment', '?')} | "
                f"分类:{metadata.get('primary_category', '?')} | "
                f"评分:{metadata.get('rating', '?')}星)\n"
                f"{content}"
            )

        context = "\n\n".join(context_parts)

        # Step 3: Generate answer with LLM
        user_prompt = f"""## 用户问题
{question}

## 检索到的相关评论（共{len(docs)}条）
{context}

请基于以上评论回答问题。如果评论中没有相关信息，请诚实地说"未在评论中找到相关反馈"。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": QA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=800,
            )
            answer = response.choices[0].message.content or ""
        except Exception as e:
            logger.error("QA LLM call failed: %s", e)
            answer = f"抱歉，生成回答时出现错误：{e}"

        # Step 4: Build citation list
        citations = []
        for i, doc in enumerate(docs, 1):
            citations.append({
                "index": i,
                "review_id": doc.get("id", ""),
                "content": doc.get("content", "")[:200],
                "sentiment": doc.get("metadata", {}).get("sentiment", ""),
                "category": doc.get("metadata", {}).get("primary_category", ""),
            })

        return {
            "answer": answer,
            "citations": citations,
            "retrieved_count": len(docs),
        }
