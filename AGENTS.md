# AGENTS.md — Instructions for AI Coding Agents

This file is automatically read by AI coding agents (Claude Code, Antigravity,
Codex, Cursor, Aider, etc.) when they open this repository. It describes the
project's purpose, conventions, and how an agent should behave when working here.

---

## Project Summary

**Vibe HUD** is a macOS desktop overlay that shows real-time status of AI coding
agents via a floating glassmorphic pill. It is written in Python (pywebview) and
uses Claude Code lifecycle hooks to receive events.

**Repo:** https://github.com/sahilbagnial/vibe-hud  
**Language:** Python 3.10+ (package manager: Poetry)  
**License:** MIT

---

## Package Layout

```
vibe_hud/
  cli.py        CLI entry points (vibe-hud, vibe-hud-hook)
  server.py     Local HTTP server (port 28790) that receives hook events
  ui/           HTML/CSS/JS for the WebKit overlay
pyproject.toml  Dependencies and scripts
README.md       User-facing documentation
llms.txt        Machine-readable project summary (llmstxt.org convention)
CLAUDE.md       Claude Code–specific context
```

---

## Development Conventions

### Running the project
```bash
poetry install
poetry run vibe-hud           # launch the overlay
poetry run vibe-hud install   # register Claude Code hooks
poetry run vibe-hud simulate  # cycle through all visual states
```

### Setting individual states (useful for UI development)
```bash
poetry run vibe-hud working "Editing main.py"
poetry run vibe-hud attention "Awaiting confirmation"
poetry run vibe-hud complete
poetry run vibe-hud idle
```

### Adding a dependency
```bash
poetry add <package>
```

---

## Architecture Rules

1. **No polling.** The HUD must never poll Claude's state. All state changes
   come from hook events (HTTP POST to `http://127.0.0.1:28790/event`) or the
   file fallback (`~/.claude-hud/state.json`).

2. **Hook binary is a thin shim.** `vibe-hud-hook` (registered in
   `~/.claude/settings.json`) should only read stdin, determine the event type,
   and forward it. All business logic lives in the server.

3. **UI is HTML/CSS/JS inside pywebview.** Do not import native UI frameworks
   other than pywebview. The overlay appearance is controlled entirely by the
   files in `vibe_hud/ui/`.

4. **macOS-first, but keep cross-platform in mind.** AppKit calls that enable
   always-on-top and click-through behavior are isolated so they can be swapped
   for Windows/Linux equivalents later.

---

## State Machine

```
idle ──► working ──► complete ──► idle
           │
           └──► attention ──► working (after user responds)
```

| State       | Color  | Audio           | Trigger hook event         |
|-------------|--------|-----------------|----------------------------|
| `idle`      | —      | —               | Initial / Stop (no work)   |
| `working`   | 🔴 Red  | —               | PreToolUse                 |
| `attention` | 🟡 Amber| Soft droplet    | awaiting human input       |
| `complete`  | 🟢 Green| Marimba chord   | Stop (work done)           |

---

## Event Payload Format

The hook posts JSON to `http://127.0.0.1:28790/event`:

```json
{
  "state": "working",           // "idle" | "working" | "attention" | "complete"
  "message": "Editing foo.py",  // optional human-readable description
  "tool": "EDIT"                // optional: "BASH" | "EDIT" | null
}
```

---

## What Agents Should NOT Do

- Do not add a requirements.txt alongside pyproject.toml — Poetry is the sole
  dependency manager.
- Do not hardcode the server port anywhere except `vibe_hud/server.py`; use the
  constant `HUD_PORT` imported from there.
- Do not add polling loops to check Claude's state.
- Do not modify `~/.claude/settings.json` directly in tests — use
  `poetry run vibe-hud install` or mock the file path in tests.

---

## Contribution Areas (Good First Issues for Agents)

- Add Aider / Cursor / OpenCode adapter (new CLI subcommand + hook docs)
- Add a macOS menu bar tray icon (NSStatusBar via pyobjc)
- Write unit tests for the state machine in `server.py`
- Add Windows always-on-top support via `win32gui` / `ctypes`

---

## Credits & Inspiration

- Reddit post by u/wssssssh:
  https://www.reddit.com/r/ClaudeCode/comments/1ue5inx/i_built_a_status_light_for_claude_code_do_you/
- open-vibe-island by Octane0411:
  https://github.com/Octane0411/open-vibe-island
