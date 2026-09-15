# 🚦 Vibe HUD

> **Universal ambient status light for AI coding agents.**
> Eliminating terminal staring anxiety with glanceable peripheral feedback.

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Poetry](https://img.shields.io/badge/Poetry-Package%20Manager-60A5FA.svg?logo=poetry&logoColor=white)](https://python-poetry.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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

---

## 🤝 Contributing

PRs and agent integrations (Cursor, Aider, Codex, Ollama) are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/agent-integration`)
3. Commit your changes (`git commit -am "Add Aider support"`)
4. Push to the branch (`git push origin feature/agent-integration`)
5. Open a Pull Request

---

## 📄 License

MIT License © 2026 sahilbagnial
