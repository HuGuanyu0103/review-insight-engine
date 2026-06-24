"""CSV parser and schema validator for input reviews.

Validates that the input CSV has the required columns and data types,
then parses each row into a RawReview model.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from src.models.review import InputCSVSchema, RawReview


class CSVParseError(Exception):
    """Raised when CSV parsing or validation fails."""


def validate_columns(df: pd.DataFrame) -> list[str]:
    """Check that all required columns exist.

    Returns a list of missing column names (empty = valid).
    """
    schema = InputCSVSchema()
    existing = set(col.strip() for col in df.columns)
    missing = [c for c in schema.required_columns if c not in existing]
    return missing


def parse_csv(file_path: str | Path, column_mapping: dict | None = None) -> list[RawReview]:
    """Parse and validate an input CSV, returning a list of RawReview objects.

    Args:
        file_path: Path to the input CSV.
        column_mapping: Optional dict to rename columns before parsing.
            e.g. {"review_text": "review_content", "timestamp": "review_timestamp"}

    Returns:
        List of validated RawReview objects.

    Raises:
        CSVParseError: If required columns are missing or data types are invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise CSVParseError(f"File not found: {path}")

    # Read CSV — handle BOM, strip column names
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except (UnicodeDecodeError, csv.Error) as e:
        raise CSVParseError(f"Failed to read CSV: {e}")

    # Rename columns by stripping whitespace
    df.columns = [c.strip() for c in df.columns]

    # Apply column mapping
    if column_mapping:
        df = df.rename(columns=column_mapping)

    # Validate required columns
    missing = validate_columns(df)
    if missing:
        raise CSVParseError(
            f"Missing required columns: {missing}. "
            f"Required: {list(InputCSVSchema().required_columns)}"
        )

    reviews: list[RawReview] = []
    warnings: list[str] = []

    for idx, row in df.iterrows():
        try:
            review = RawReview(
                review_id=str(row["review_id"]).strip(),
                review_content=str(row["review_content"]).strip(),
                rating=_parse_rating(row.get("rating", "")),
                has_image_or_video=_parse_bool(row.get("has_image_or_video", False)),
                user_id=_parse_optional_str(row.get("user_id")),
                user_tier=_parse_optional_str(row.get("user_tier")),
                review_timestamp=_parse_optional_str(row.get("review_timestamp")),
                product_id=str(row.get("product_id", "")).strip(),
                product_name=_parse_optional_str(row.get("product_name")),
                product_category=_parse_optional_str(row.get("product_category")),
                order_price=_parse_float(row.get("order_price")),
            )
            reviews.append(review)
        except Exception as e:
            warnings.append(f"Row {idx}: skipped — {e}")

    if warnings:
        import logging
        logger = logging.getLogger(__name__)
        for w in warnings:
            logger.warning(w)
        logger.warning(
            f"Parsed {len(reviews)} reviews with {len(warnings)} skipped rows "
            f"(out of {len(df)} total)"
        )

    if not reviews:
        raise CSVParseError("No valid reviews found in input CSV")

    return reviews


def _parse_rating(value) -> int:
    """Parse star rating, must be 1-5."""
    try:
        r = int(float(str(value).strip()))
        if 1 <= r <= 5:
            return r
    except (ValueError, TypeError):
        pass
    raise ValueError(f"Invalid rating: {value}")


def _parse_bool(value) -> bool:
    """Parse boolean from various representations."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("true", "1", "yes", "y", "是")


def _parse_optional_str(value) -> str | None:
    """Parse optional string — None if empty/null/NaN."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    return s if s else None


def _parse_float(value) -> float | None:
    """Parse optional float."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None
