---
bundle:
  name: session-guardian
  version: 1.0.0
  description: Automatic session scope management — tracks token pressure, persists state, enables clean handoff

includes:
  - bundle: session-guardian:behaviors/session-guardian
---

# Session Guardian

Automatic session scope management for Amplifier.

Tracks token pressure, saves session state proactively, and enables clean handoff between sessions. Compose into any bundle — runs invisibly.

## Quick Start

Add to your bundle:
```yaml
includes:
  - bundle: git+https://github.com/cpark4x/amplifier-bundle-session-guardian@main
```

## How It Works

- **0-59% context**: Runs silently
- **60%**: Saves progress, warns you, continues working concisely
- **80%**: Saves final state, tells you to start a new session
- **New session**: Detects saved state, offers seamless resume
