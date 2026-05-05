"""Single SQL surface for Sherpa. Other modules MUST NOT construct raw SQL.

Spec pr-data-ingestion / D9: schema access goes through this module.
"""

from sherpa.db.repo import (
    SCHEMA_PATH,
    classify_role,
    connect,
    init_schema,
    upsert_code_diff,
    upsert_comment_outcome,
    upsert_learning_label,
    upsert_pr,
    upsert_review_comment,
)

__all__ = [
    "SCHEMA_PATH",
    "classify_role",
    "connect",
    "init_schema",
    "upsert_code_diff",
    "upsert_comment_outcome",
    "upsert_learning_label",
    "upsert_pr",
    "upsert_review_comment",
]
