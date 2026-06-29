"""Pluggable review-agent abstraction (review-inference).

Importing this package registers the built-in adapters (claude, codex, ollama)
and exposes the contract + selection helpers.
"""

from sherpa.agent import adapters  # noqa: F401  (registers built-in adapters by name)
from sherpa.agent.base import (
    AgentError,
    ReviewAgent,
    available,
    register,
    resolve,
    select,
)
from sherpa.agent.schema import (
    Finding,
    ReviewResult,
    ReviewTask,
    Trajectory,
    build_prompt,
    parse_review_result,
    result_to_dict,
)

__all__ = [
    "AgentError",
    "Finding",
    "ReviewAgent",
    "ReviewResult",
    "ReviewTask",
    "Trajectory",
    "available",
    "build_prompt",
    "parse_review_result",
    "register",
    "resolve",
    "result_to_dict",
    "select",
]
