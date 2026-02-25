# amplifier-bundle-session-guardian

Automatic session scope management for [Amplifier](https://github.com/robotdad/amplifier).

Tracks token pressure in real time, saves session state proactively, and enables clean handoff between sessions. Compose into any bundle — runs invisibly until it matters.

## Install

Add to your bundle's `includes`:

```yaml
includes:
  - bundle: git+https://github.com/cpark4x/amplifier-bundle-session-guardian@main
```

## What It Does

| Context Usage | Behavior |
|---|---|
| 0-59% | Silent — lightweight status injected into system context |
| 60-79% | Saves progress automatically, warns you, continues concisely |
| 80%+ | Saves final state, tells you to start a new session |
| New session | Detects saved state and offers to resume |

## Components

- **Token Tracking Hook** — monitors `provider:response` events for token usage, injects budget warnings into `provider:request`
- **Session State Tool** — `session_state` tool with `save_state`, `load_state`, `list_states` operations
- **Protocol Context** — teaches the AI when and how to save/load state

## Configuration

Override defaults in the behavior YAML:

```yaml
hooks:
  - module: session-guardian
    source: session-guardian:modules/session-guardian
    config:
      context_window: 200000    # model's context window size
      soft_threshold: 0.60      # trigger save + concise mode
      hard_threshold: 0.80      # trigger handoff
```

## State Files

Session state is saved to `.session-state/` in the working directory as timestamped JSON files. Files older than 7 days are pruned automatically.

## License

MIT
