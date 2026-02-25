# Session Guardian Protocol

## On Session Start

Check for prior state:
1. Call `session_state(operation="list_states")`
2. If files exist, call `session_state(operation="load_state")`
3. Summarize what was accomplished and what remains, then offer to resume

## At 60% Context (Soft Warning)

When you see `[Session Guardian: N% context — save progress...]`:
1. Call `session_state(operation="save_state")` with current progress
2. Briefly tell the user state has been saved
3. Continue working but be more concise — shorter explanations, less verbose code comments

## At 80% Context (Hard Warning)

When you see `[Session Guardian: N% context — HANDOFF REQUIRED...]`:
1. Immediately call `session_state(operation="save_state")` with final state
2. Tell the user: "Context is nearly full. I've saved our progress. Please start a new session to continue — I'll pick up where we left off."
3. Do not start new tasks

## Scope Discipline

When tangential work comes up mid-session, do not take it on. Instead, capture it as a "remaining" item in the next `save_state` call. Stay focused on the current objective.
