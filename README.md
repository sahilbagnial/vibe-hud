# 🚦 Vibe HUD — Universal AI Agent Status Overlay for macOS

> **Real-time ambient status light for Claude Code, Cursor, Aider, Codex & more.**
> _Note: Currnetly only available for claude code,rest is work in progress_
> Stop staring at the terminal. Know instantly when your AI is thinking, done, or needs you.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Poetry](https://img.shields.io/badge/Poetry-Package%20Manager-60A5FA.svg?logo=poetry&logoColor=white)](https://python-poetry.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS-000000.svg?logo=apple&logoColor=white)](https://apple.com/macos)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-orange.svg)](https://claude.ai/code)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red.svg)](https://github.com/sahilbagnial/vibe-hud)

---

## 🤔 What is Vibe HUD?

**Vibe HUD** is a floating, always-on-top glassmorphic overlay for macOS that gives you **instant, glanceable feedback** about what your AI coding agent is doing — without switching windows, tabbing back to the terminal, or breaking your flow.

- 🔴 **Agent is working** → Red pulsing light + elapsed timer
- 🟢 **Agent finished** → Green flash + audio chime  
- 🟡 **Agent needs you** → Amber breathing alert + soft ping

It plugs directly into [Claude Code](https://claude.ai/code) via lifecycle hooks, requiring **zero polling** and **zero custom scripts**.

---

## ✨ Features

- **🔴 Red / Pulsing Radar**: Glowing indicator + live elapsed timer when your agent is thinking, running bash commands, or editing files.
- **🟢 Emerald Green**: Clear visual confirmation + subtle audio chime when the agent finishes its turn.
- **🟡 Amber Breathing**: Alerts you the exact millisecond the agent asks for human confirmation or permission.
- **🏝️ Floating Glassmorphic Pill**:
  - Transparent, frameless, and draggable anywhere across your screens.
  - Stays on top across full-screen desktops, IDEs, and browsers on macOS.
  - Expandable card showing the active prompt, tool badge (`BASH`, `EDIT`), and quick controls.
- **🎵 Procedural Audio Chimes**:
  - Synthesized Web Audio API sounds (pleasant marimba chord on completion, soft droplet on permission prompt).
  - Zero external WAV/MP3 files needed.
- **⚡ 1-Click Hook Setup**:
  - Automatically configures `~/.claude/settings.json` with safety backups.
  - Deterministic lifecycle execution (never polls, zero hallucination).

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/sahilbagnial/vibe-hud.git
cd vibe-hud
poetry install
```

### 2. Launch Vibe HUD

```bash
poetry run vibe-hud
```

### 3. Connect to Claude Code

Inside the expanded pill, click **⚡ Install Hooks**, or run:
```bash
poetry run vibe-hud install
```

That's it — Vibe HUD will now light up every time Claude Code starts working, needs your attention, or completes a task.

---

## 🧪 Testing & Simulation

Test all states without waiting for Claude:

```bash
# Run 10-second interactive simulation flow
poetry run vibe-hud simulate

# Or set direct states from terminal:
poetry run vibe-hud working "Writing tests..."
poetry run vibe-hud attention "Need confirmation"
poetry run vibe-hud complete
poetry run vibe-hud idle
```

---

## 🛠️ Architecture

```
Claude Code CLI (terminal)
     │
     ▼
~/.claude/settings.json hooks
     │
     ▼
vibe-hud hook (reads stdin JSON)
     │
     ├───► [Primary] HTTP POST http://127.0.0.1:28790/event
     │                     │
     └───► [Fallback] ~/.claude-hud/state.json
                           │
                           ▼
                 Python (pywebview)
                           │
                           ▼
     Floating Glassmorphic Capsule (Native WebKit)
```

**Key design decisions:**
- **Hook-driven, not polling** — Claude Code calls the hook binary at lifecycle boundaries; the HUD never polls Claude's state.
- **HTTP + file fallback** — The hook POSTs to a local HTTP server. If the server isn't running, it writes a state file as fallback.
- **Native WebKit rendering** — The UI is a single HTML/CSS/JS page rendered in a transparent `pywebview` window pinned above all other windows.

---

## 🗺️ Roadmap

Ideas being considered for the next round of work — PRs against any of these are very welcome:

- **Menu bar tray + native alerts**: a proper macOS menu-bar icon (show/hide/quit) plus a native OS notification when a session needs attention or finishes, so you're alerted even when the HUD is hidden behind another window.
- **Multi-agent adapters**: generalize the hook payload/CLI so Cursor, Aider, Codex, or OpenCode can push events too, so this stops being Claude-only and becomes the "universal" agent HUD the name promises.
- **Cross-platform parity**: always-on-top window pinning and click-to-focus currently rely on macOS-only AppKit calls; Windows/Linux equivalents are needed for real cross-platform support.
- **Session history + stale detection**: a History tab showing past turns per repo, and a visual flag when a session has been "working" with no event for an unusually long time (crashed hook, closed terminal, etc.).

---

## 🤝 Contributing

PRs and agent integrations (Cursor, Aider, Codex, Ollama, OpenCode) are very welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/agent-integration`)
3. Commit your changes (`git commit -am "Add Aider support"`)
4. Push to the branch (`git push origin feature/agent-integration`)
5. Open a Pull Request

---

## 🙏 Inspired By

Vibe HUD exists because of the broader community exploring **ambient AI awareness** — the idea that when you offload work to an AI agent, you need a lightweight peripheral signal to know when to pay attention again.

- **[u/wssssssh on r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1ue5inx/i_built_a_status_light_for_claude_code_do_you/)** — A viral Reddit post (3,600+ upvotes, 386 comments) where the creator built a **physical Raspberry Pi + LED status light** for Claude Code. That community discussion made it clear there's a widespread need for this kind of glanceable feedback, and inspired a fully-software, zero-hardware approach.

- **[open-vibe-island by Octane0411](https://github.com/Octane0411/open-vibe-island)** — An open-source macOS app providing ambient status for AI agents with the same core philosophy: keep AI status visible without interrupting your flow.

---

## 🔍 Keywords & Discoverability

<!-- SEO / GEO metadata — helps search engines and AI assistants surface this project -->

**Topics:** `claude-code` · `ai-agent` · `macos` · `status-overlay` · `hud` · `vibe-coding` · `pywebview` · `glassmorphism` · `developer-tools` · `llm-tools` · `agentic-coding` · `claude-hooks`

**Search terms this project answers:**
- How to get notified when Claude Code finishes
- Claude Code status indicator / monitor
- AI coding agent HUD overlay macOS
- Claude Code ambient feedback / peripheral status light
- Python floating overlay always-on-top macOS
- Claude Code hook integration
- AI pair programming status bar
- Vibe coding productivity tools

---

## 📄 License

MIT License © 2026 [sahilbagnial](https://github.com/sahilbagnial)
