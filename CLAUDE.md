# CLAUDE.md — Claude Code Context for Vibe HUD

This file is automatically injected into Claude Code's context at the start of
every session in this repository. It tells you (Claude) exactly what this project
is, how to work in it, and what rules to follow.

---

## What is this repo?

**Vibe HUD** — a floating macOS overlay that shows you (the AI agent) are working,
done, or waiting. It is the meta-irony project: an AI-status HUD *for* AI agents,
*built with* AI agents. The developer runs Claude Code in one terminal; Vibe HUD
watches Claude's hooks and shows a colored capsule on screen so the developer
doesn't have to keep switching back to check.

**Stack:** Python 3.10+, Poetry, pywebview (WebKit), vanilla HTML/CSS/JS  
**Entry points:** `vibe-hud` (overlay) · `vibe-hud-hook` (hook binary)

---

## Repository layout (read this before touching files)

```
vibe_hud/
  cli.py         vibe-hud and vibe-hud-hook CLI entry points
  core/          Session state machine, settings, HTTP server, hook install (OS-agnostic)
  platform/      One PlatformBackend per OS (macos.py, windows.py, linux.py)
  app.py         VibeHudApp/VibeHudApi — thin orchestrator wiring core + platform + pywebview
  ui/            WebKit overlay — HTML, CSS, JS
pyproject.toml  Poetry config — only place to add/remove dependencies
AGENTS.md       Full agent instructions (architecture, state machine, do-nots)
llms.txt        Machine-readable project summary for LLM crawlers
```

---

## How to run things

```bash
poetry install                              # install deps
poetry run vibe-hud                         # launch the HUD
poetry run vibe-hud install                 # write Claude hooks to ~/.claude/settings.json
poetry run vibe-hud simulate               # demo all states
poetry run vibe-hud working "message"       # set state directly
poetry run vibe-hud attention "message"
poetry run vibe-hud complete
poetry run vibe-hud idle
```

---

## Key rules (follow these always)

1. **Never add polling.** State only changes via HTTP events or file fallback.
2. **Port is a constant.** The default port lives in `vibe_hud/core/server.py`
   (`HudServer`) and `vibe_hud/cli.py` (`DEFAULT_PORT`) — never hardcode
   `28790` elsewhere.
3. **Poetry only.** No `requirements.txt`, no `pip install` suggestions.
4. **UI = WebKit.** The overlay is HTML/CSS/JS inside pywebview. Don't suggest
   tkinter, Qt, or other GUI toolkits.
5. **Hook binary stays thin.** `vibe-hud-hook` reads stdin JSON and forwards it.
   Logic goes in `server.py`, not the hook.

---

## State machine (quick reference)

| State       | Signal  | Trigger                        |
|-------------|---------|--------------------------------|
| `idle`      | none    | startup / after stop           |
| `working`   | 🔴 red  | PreToolUse (bash, edit, etc.)  |
| `attention` | 🟡 amber| awaiting human confirmation    |
| `complete`  | 🟢 green| Stop (agent finished turn)     |

---

## Event JSON format (hook → server)

```json
{ "state": "working", "message": "Editing foo.py", "tool": "EDIT" }
```

`tool` is optional and one of: `"BASH"`, `"EDIT"`, or `null`.

---

## What to work on next (roadmap)

See the Roadmap section in README.md. Short list:
- Menu bar tray icon (NSStatusBar)
- Cursor / Aider / OpenCode adapters
- Unit tests for server.py state machine
- Windows/Linux always-on-top fallback

---

## Inspiration

This project was sparked by a viral Reddit post where someone built a *physical*
LED status light for Claude Code:
https://www.reddit.com/r/ClaudeCode/comments/1ue5inx/i_built_a_status_light_for_claude_code_do_you/

And influenced by open-vibe-island:
https://github.com/Octane0411/open-vibe-island
