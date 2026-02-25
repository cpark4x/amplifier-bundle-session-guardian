"""Session Guardian — token tracking hook module.

Registers two hooks:
1. provider:response — tracks token usage per turn
2. provider:request  — injects context budget warnings
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from amplifier_core.models import HookResult

logger = logging.getLogger(__name__)


class TokenTracker:
    """Tracks token usage across a session."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.context_window: int = config.get("context_window", 200_000)
        self.soft_threshold: float = config.get("soft_threshold", 0.60)
        self.hard_threshold: float = config.get("hard_threshold", 0.80)

        # Latest input_tokens from most recent response — NOT cumulative.
        # Each request sends the full context, so latest == current window usage.
        self.latest_input_tokens: int = 0
        self.cumulative_output_tokens: int = 0
        self.turn_count: int = 0

    @property
    def usage_pct(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return self.latest_input_tokens / self.context_window


def _extract_tokens(usage: Any) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from dict or Usage model."""
    if usage is None:
        return 0, 0
    try:
        if isinstance(usage, dict):
            return (
                usage.get("input_tokens", 0) or 0,
                usage.get("output_tokens", 0) or 0,
            )
        # Pydantic Usage model
        return (
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
        )
    except Exception:
        return 0, 0


async def _handle_response(tracker: TokenTracker, data: dict[str, Any]) -> HookResult:
    """provider:response — record token usage from the model response."""
    try:
        usage = data.get("usage")
        input_tokens, output_tokens = _extract_tokens(usage)

        if input_tokens > 0:
            tracker.latest_input_tokens = input_tokens
        tracker.cumulative_output_tokens += output_tokens
        tracker.turn_count += 1

        logger.debug(
            "guardian_tracker: turn=%d input=%d cumulative_output=%d pct=%.1f%%",
            tracker.turn_count,
            tracker.latest_input_tokens,
            tracker.cumulative_output_tokens,
            tracker.usage_pct * 100,
        )
    except Exception:
        logger.debug("guardian_tracker: failed to extract usage", exc_info=True)

    return HookResult(action="continue")


async def _handle_request(tracker: TokenTracker, data: dict[str, Any]) -> HookResult:
    """provider:request — inject context budget status into the prompt."""
    try:
        pct = tracker.usage_pct
        pct_int = int(pct * 100)
        turn = tracker.turn_count

        if pct < tracker.soft_threshold:
            # Silent — lightweight status only
            msg = f"[Session Guardian: {pct_int}% context used, turn {turn}]"
            return HookResult(
                action="inject_context",
                context_injection=msg,
                context_injection_role="system",
                ephemeral=True,
            )

        if pct < tracker.hard_threshold:
            # Soft warning — save progress
            msg = (
                f"[Session Guardian: {pct_int}% context — save progress with "
                f"session_state tool now. Continue working but be concise.]"
            )
            return HookResult(
                action="inject_context",
                context_injection=msg,
                context_injection_role="system",
                ephemeral=True,
                user_message=f"Session Guardian: {pct_int}% context used — saving progress recommended",
                user_message_level="warning",
            )

        # Hard warning — handoff required
        msg = (
            f"[Session Guardian: {pct_int}% context — HANDOFF REQUIRED. "
            f"Save state immediately and tell the user to start a new session.]"
        )
        return HookResult(
            action="inject_context",
            context_injection=msg,
            context_injection_role="system",
            ephemeral=True,
            user_message=f"Session Guardian: {pct_int}% context used — handoff required!",
            user_message_level="error",
        )
    except Exception:
        logger.debug("guardian_injector: injection failed", exc_info=True)
        return HookResult(action="continue")


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> Callable[[], None]:
    """Mount the session guardian hooks. Returns a cleanup callable."""
    config = config or {}
    tracker = TokenTracker(config)

    unreg_response = coordinator.hooks.register(
        "provider:response",
        lambda data: _handle_response(tracker, data),
        priority=10,
        name="guardian_tracker",
    )
    unreg_request = coordinator.hooks.register(
        "provider:request",
        lambda data: _handle_request(tracker, data),
        priority=5,
        name="guardian_injector",
    )

    def cleanup() -> None:
        unreg_response()
        unreg_request()

    logger.info(
        "Session Guardian mounted (window=%d, soft=%.0f%%, hard=%.0f%%)",
        tracker.context_window,
        tracker.soft_threshold * 100,
        tracker.hard_threshold * 100,
    )
    return cleanup
