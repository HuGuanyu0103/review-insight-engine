"""Low-quality review filter.

Filters out reviews that are too short, meaningless, or purely
auto-generated (e.g. "好评", "默认好评", pure emoji), saving API tokens
and preventing statistical noise.
"""

import re
import logging
from dataclasses import dataclass

from src.models.review import RawReview

logger = logging.getLogger(__name__)

# ---- Patterns for meaningless content ----

# Emoji Unicode ranges — carefully scoped to NOT include CJK ideographs
_EMOJI_RANGES = (
    "\U0001F600-\U0001F64F"   # Emoticons (😀-🙏)
    "\U0001F300-\U0001F5FF"   # Miscellaneous Symbols & Pictographs (🌀-🗿)
    "\U0001F680-\U0001F6FF"   # Transport & Map Symbols (🚀-🛿)
    "\U0001F1E0-\U0001F1FF"   # Regional Indicator Symbols (🇦-🇿)
    "\U0001F900-\U0001F9FF"   # Supplemental Symbols & Pictographs (🤀-🧿)
    "\U0001FA00-\U0001FA6F"   # Chess Symbols
    "\U0001FA70-\U0001FAFF"   # Symbols & Pictographs Extended-A (🩰-🫿)
    "\U00002702-\U000027B0"   # Dingbats (✂-➰)
    "\U000024C2-\U000024C2"   # Circled M (Ⓜ)
    "\U00002300-\U000023FF"   # Miscellaneous Technical
    "\U00002500-\U000025FF"   # Geometric Shapes (■-◿)
    "\U00002600-\U000026FF"   # Miscellaneous Symbols (☀-⛿)
    "\U00002B50-\U00002B55"   # Stars
    "\U0000FE00-\U0000FE0F"   # Variation Selectors
    "\U0000200D"              # Zero Width Joiner
    "\U000020E3"              # Combining Enclosing Keycap
)
EMOJI_PATTERN = re.compile(f"[{_EMOJI_RANGES}]+")

# Auto-generated / default praise patterns
MEANINGLESS_PATTERNS = [
    "好评", "默认好评", "好评好评", "好好好",
    "此用户没有填写评价", "此用户没有填写评论",
    "评价方未及时做出评价", "系统默认好评",
    "用户未填写评价内容", "默认评价",
    "懒得写", "不想写", "没什么好说的",
    "还行吧", "就这样", "一般般吧",
    "。。。。。。", "......",
]

# Pure-repetition pattern: same character repeated ≥ 5 times
REPETITION_PATTERN = re.compile(r"^(.)\1{4,}$")


@dataclass
class FilterResult:
    """Result of filtering a single review."""

    kept: bool
    reason: str = ""


def _is_pure_emoji(text: str) -> bool:
    """Check if the text is purely emoji with no semantic content."""
    cleaned = EMOJI_PATTERN.sub("", text).strip()
    return len(cleaned) == 0


def _is_meaningless(text: str) -> bool:
    """Check if the text matches known meaningless patterns.

    For short patterns (≤3 chars), use exact match only.
    For longer patterns, allow substring match.
    """
    stripped = text.strip()
    for pattern in MEANINGLESS_PATTERNS:
        if pattern == stripped:
            return True
        # Only substring-match longer patterns to avoid false matches
        if len(pattern) > 3 and pattern in stripped:
            return True
    return False


def _is_repetition(text: str) -> bool:
    """Check if the text is just a single repeated character."""
    stripped = text.strip()
    return bool(REPETITION_PATTERN.match(stripped))


def _has_substantive_content(text: str) -> bool:
    """Check if the text contains at least some Chinese characters or alphabetic words."""
    # At least 2 Chinese characters OR 3 alphabetic words
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    alpha_words = len(re.findall(r"[a-zA-Z]{2,}", text))
    return chinese_chars >= 2 or alpha_words >= 3


def filter_review(review: RawReview, min_length: int = 5) -> FilterResult:
    """Apply heuristic filters to a single review.

    Returns FilterResult with kept=True if the review should be processed.
    """
    text = review.review_content.strip()

    # 1. Length filter
    if len(text) < min_length:
        return FilterResult(kept=False, reason=f"Too short ({len(text)} chars, min {min_length})")

    # 2. Pure emoji check
    if _is_pure_emoji(text):
        return FilterResult(kept=False, reason="Pure emoji / no semantic content")

    # 3. Meaningless pattern check
    if _is_meaningless(text):
        return FilterResult(kept=False, reason="Matches known meaningless pattern")

    # 4. Repetition check
    if _is_repetition(text):
        return FilterResult(kept=False, reason="Single repeated character")

    # 5. Substantive content check
    if not _has_substantive_content(text):
        return FilterResult(kept=False, reason="No substantive content (Chinese/alphanumeric)")

    return FilterResult(kept=True)


def filter_reviews(reviews: list[RawReview], min_length: int = 5) -> tuple[list[RawReview], list[dict]]:
    """Apply all heuristic filters to a list of reviews.

    Returns:
        (kept_reviews, filtered_log) — tuple of reviews that passed and a log
        of what was filtered and why.
    """
    kept: list[RawReview] = []
    filtered_log: list[dict] = []

    for review in reviews:
        result = filter_review(review, min_length=min_length)
        if result.kept:
            kept.append(review)
        else:
            filtered_log.append({
                "review_id": review.review_id,
                "review_content": review.review_content[:80],
                "reason": result.reason,
            })

    logger.info(
        "Filter result: %d kept, %d filtered (%.1f%% pass rate)",
        len(kept), len(filtered_log),
        100 * len(kept) / max(len(kept) + len(filtered_log), 1)
    )

    return kept, filtered_log
