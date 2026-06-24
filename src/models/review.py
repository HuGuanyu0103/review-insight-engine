"""Raw input data models matching the CSV input schema."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RawReview(BaseModel):
    """A single raw review from the input CSV.

    Maps to the three-dimensional input schema:
    1. Core Feedback (The "What"): review_id, review_content, rating, has_image_or_video
    2. User & Context (The "Who & When"): user_id, user_tier, review_timestamp
    3. Product & Business (The "Where"): product_id, product_name, product_category, order_price
    """

    # --- Core Feedback ---
    review_id: str = Field(..., description="Unique review identifier")
    review_content: str = Field(..., min_length=1, description="Raw review text")
    rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    has_image_or_video: bool = Field(default=False, description="Whether review includes image/video")

    # --- User & Context ---
    user_id: Optional[str] = Field(default=None, description="User identifier")
    user_tier: Optional[str] = Field(default=None, description="User membership tier (e.g. Plus会员, 普通会员, 新用户)")
    review_timestamp: Optional[datetime] = Field(default=None, description="Review submission timestamp")

    # --- Product & Business ---
    product_id: str = Field(default="", description="Product/SKU identifier")
    product_name: Optional[str] = Field(default=None, description="Human-readable product name")
    product_category: Optional[str] = Field(default=None, description="Product category (e.g. 运动鞋)")
    order_price: Optional[float] = Field(default=None, ge=0, description="Order paid amount")

    @field_validator("review_timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        """Accept datetime or string; parse common date formats."""
        if v is None or isinstance(v, datetime):
            return v
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(str(v).strip(), fmt)
            except ValueError:
                continue
        return None  # fallback — won't block ingestion


class InputCSVSchema(BaseModel):
    """Validates that an input CSV has all required columns."""

    required_columns: tuple[str, ...] = (
        "review_id",
        "review_content",
        "rating",
        "review_timestamp",
        "product_id",
    )
    optional_columns: tuple[str, ...] = (
        "has_image_or_video",
        "user_id",
        "user_tier",
        "product_name",
        "product_category",
        "order_price",
    )
