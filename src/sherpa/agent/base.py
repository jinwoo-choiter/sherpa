"""ReviewAgent contract + config-driven selection (review-inference: pluggable
review-agent abstraction).

A ReviewAgent takes a prepared ReviewTask and returns (ReviewResult, Trajectory).
Adapters register a factory by name. The active agent is the configured default
unless overridden per run; adding an agent never touches the callers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from sherpa.agent.schema import ReviewResult, ReviewTask, Trajectory


class AgentError(RuntimeError):
    """Raised when an adapter fails to run or parse its agent."""


@runtime_checkable
class ReviewAgent(Protocol):
    name: str

    def review(self, task: ReviewTask) -> tuple[ReviewResult, Trajectory]: ...


_REGISTRY: dict[str, Callable[[], ReviewAgent]] = {}


def register(name: str, factory: Callable[[], ReviewAgent]) -> None:
    _REGISTRY[name] = factory


def available() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def select(name: str) -> ReviewAgent:
    factory = _REGISTRY.get(name)
    if factory is None:
        raise ValueError(f"unknown review agent {name!r}; available: {available()}")
    return factory()


def resolve(default: str, override: str | None = None) -> ReviewAgent:
    """Pick the per-run agent: the override if given, else the configured default."""
    return select(override or default)
