"""Verify session-guardian is correctly classified as a hook module.

This test proves:
1. The naming heuristic WOULD misclassify "session-guardian" as "tool"
2. The __amplifier_module_type__ attribute overrides the heuristic
3. The hook actually mounts and registers handlers on a coordinator
"""
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest


def test_naming_heuristic_would_misclassify():
    """Without __amplifier_module_type__, the loader would guess 'tool'."""
    # Reproduce the exact logic from amplifier_core/loader.py:431-465
    type_mapping = {
        "orchestrat": ("orchestrator", "orchestrator"),
        "loop":       ("orchestrator", "orchestrator"),
        "provider":   ("provider",     "providers"),
        "tool":       ("tool",         "tools"),
        "hook":       ("hook",         "hooks"),
        "context":    ("context",      "context"),
    }

    module_id = "session-guardian"
    module_id_lower = module_id.lower()

    matched = None
    for keyword, (mod_type, mount_pt) in type_mapping.items():
        if keyword in module_id_lower:
            matched = (mod_type, mount_pt)
            break

    # This is the bug: no keyword matches, so loader defaults to ("tool", "tools")
    assert matched is None, (
        f"Expected no keyword match for '{module_id}', but matched: {matched}"
    )


def test_module_declares_hook_type():
    """The module MUST declare __amplifier_module_type__ = 'hook'."""
    module_dir = Path(__file__).parent.parent / "modules" / "session-guardian"
    sys.path.insert(0, str(module_dir))
    try:
        mod_name = "amplifier_module_session_guardian"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        module = importlib.import_module(mod_name)
        module_type = getattr(module, "__amplifier_module_type__", None)

        assert module_type is not None, (
            "Missing __amplifier_module_type__! "
            "The loader will fall through to _guess_from_naming() "
            "which returns ('tool', 'tools') for 'session-guardian'. "
            "The hook will silently fail to mount."
        )
        assert module_type == "hook", (
            f"Expected __amplifier_module_type__ = 'hook', got '{module_type}'"
        )
    finally:
        sys.path.remove(str(module_dir))


@pytest.mark.asyncio
async def test_hook_mounts_and_registers_handlers():
    """mount() must register two hooks on the coordinator."""
    module_dir = Path(__file__).parent.parent / "modules" / "session-guardian"
    sys.path.insert(0, str(module_dir))
    try:
        mod_name = "amplifier_module_session_guardian"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        module = importlib.import_module(mod_name)

        # Build a mock coordinator with a hooks registry
        coordinator = MagicMock()
        registered = {}

        def mock_register(event, handler, priority=0, name=None):
            registered[name or event] = {"event": event, "handler": handler, "priority": priority}
            return MagicMock()  # unregister callable

        coordinator.hooks.register = mock_register

        config = {"context_window": 200000, "soft_threshold": 0.60, "hard_threshold": 0.80}
        cleanup = await module.mount(coordinator, config)

        # Verify both hooks registered
        assert "guardian_tracker" in registered, "guardian_tracker hook not registered"
        assert "guardian_injector" in registered, "guardian_injector hook not registered"
        assert registered["guardian_tracker"]["event"] == "provider:response"
        assert registered["guardian_injector"]["event"] == "provider:request"

        # Verify cleanup callable returned
        assert callable(cleanup), "mount() must return a cleanup callable"
    finally:
        sys.path.remove(str(module_dir))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
