"""Session State Tool — save/load/list session state for clean handoff.

State files are persisted to `.session-state/` in the current working directory.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from amplifier_core import ToolResult

logger = logging.getLogger(__name__)

STATE_DIR = ".session-state"
SCHEMA_VERSION = 1
PRUNE_DAYS = 7

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["save_state", "load_state", "list_states"],
            "description": "Operation to perform.",
        },
        "summary": {
            "type": "string",
            "description": "Brief summary of what was accomplished this session (save_state).",
        },
        "accomplished": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of completed items (save_state).",
        },
        "remaining": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of items still to do (save_state).",
        },
        "decisions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key decisions made this session (save_state, optional).",
        },
        "context": {
            "type": "object",
            "properties": {
                "branch": {"type": "string"},
                "files_changed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "working_directory": {"type": "string"},
            },
            "description": "Additional context (save_state, optional).",
        },
    },
    "required": ["operation"],
}


class SessionStateTool:
    """Persist and retrieve session state for cross-session handoff."""

    def __init__(self, config: dict[str, Any], coordinator: Any) -> None:
        self._config = config
        self._coordinator = coordinator

    # -- Tool protocol ---------------------------------------------------------

    @property
    def name(self) -> str:
        return "session_state"

    @property
    def description(self) -> str:
        return "Save and load session state for clean handoff between sessions."

    @property
    def input_schema(self) -> dict[str, Any]:
        return INPUT_SCHEMA

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        operation = input.get("operation")
        try:
            if operation == "save_state":
                return await self._save_state(input)
            if operation == "load_state":
                return await self._load_state()
            if operation == "list_states":
                return await self._list_states()
            return ToolResult(
                error=f"Unknown operation: {operation}. Use save_state, load_state, or list_states."
            )
        except Exception as exc:
            logger.error("session_state %s failed: %s", operation, exc, exc_info=True)
            return ToolResult(error=f"session_state {operation} failed: {exc}")

    # -- Operations ------------------------------------------------------------

    async def _save_state(self, input: dict[str, Any]) -> ToolResult:
        # Validate required fields
        missing = [f for f in ("summary", "accomplished", "remaining") if not input.get(f)]
        if missing:
            return ToolResult(
                error=f"save_state requires: {', '.join(missing)}"
            )

        state_dir = Path(STATE_DIR)
        state_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        filename = now.strftime("%Y-%m-%dT%H-%M-%S") + ".json"

        # Build state document
        state: dict[str, Any] = {
            "version": SCHEMA_VERSION,
            "timestamp": now.isoformat(),
            "summary": input["summary"],
            "accomplished": input["accomplished"],
            "remaining": input["remaining"],
        }

        if input.get("decisions"):
            state["decisions"] = input["decisions"]
        if input.get("context"):
            state["context"] = input["context"]

        # Include session_id from coordinator if available
        session_id = self._get_session_id()
        if session_id:
            state["session_id"] = session_id

        filepath = state_dir / filename
        filepath.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        # Prune old files
        pruned = self._prune_old_states(state_dir, now)

        msg = f"State saved to {filepath}"
        if pruned:
            msg += f" (pruned {pruned} old file{'s' if pruned != 1 else ''})"

        logger.info("session_state: saved %s", filepath)
        return ToolResult(output=msg)

    async def _load_state(self) -> ToolResult:
        state_dir = Path(STATE_DIR)
        if not state_dir.is_dir():
            return ToolResult(output="No session state directory found. This appears to be a fresh session.")

        files = sorted(state_dir.glob("*.json"), reverse=True)
        if not files:
            return ToolResult(output="No state files found. This appears to be a fresh session.")

        latest = files[0]
        try:
            content = json.loads(latest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return ToolResult(error=f"Failed to read {latest}: {exc}")

        logger.info("session_state: loaded %s", latest)
        return ToolResult(output=json.dumps(content, indent=2))

    async def _list_states(self) -> ToolResult:
        state_dir = Path(STATE_DIR)
        if not state_dir.is_dir():
            return ToolResult(output="No session state directory found.")

        files = sorted(state_dir.glob("*.json"), reverse=True)
        if not files:
            return ToolResult(output="No state files found.")

        entries: list[str] = []
        for f in files:
            size = f.stat().st_size
            entries.append(f"{f.name} ({size} bytes)")

        return ToolResult(output=f"Found {len(files)} state file(s):\n" + "\n".join(entries))

    # -- Helpers ---------------------------------------------------------------

    def _get_session_id(self) -> str | None:
        """Try to extract session_id from coordinator config."""
        try:
            if hasattr(self._coordinator, "config"):
                cfg = self._coordinator.config
                if isinstance(cfg, dict):
                    return cfg.get("session_id")
                return getattr(cfg, "session_id", None)
        except Exception:
            pass
        return None

    @staticmethod
    def _prune_old_states(state_dir: Path, now: datetime) -> int:
        """Remove state files older than PRUNE_DAYS. Returns count pruned."""
        cutoff = now - timedelta(days=PRUNE_DAYS)
        pruned = 0
        for f in state_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    f.unlink()
                    pruned += 1
            except Exception:
                pass
        return pruned


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> None:
    """Mount the session_state tool."""
    config = config or {}
    tool = SessionStateTool(config, coordinator)
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info("session_state tool mounted")
