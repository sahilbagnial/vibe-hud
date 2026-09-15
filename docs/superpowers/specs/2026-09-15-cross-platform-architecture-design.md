# Cross-Platform, Modular Architecture for Vibe HUD

**Status:** Approved
**Date:** 2026-09-15

## Context

Vibe HUD started as a macOS-only proof of concept. All OS-integration logic
(window-level tricks, tray icon, terminal detection, click-to-focus) lives
directly inside `vibe_hud/window.py` (630 lines) and `vibe_hud/cli.py`, mixed
in with platform-agnostic app logic (session state machine, settings
persistence, CLI argument parsing) via ad-hoc `sys.platform == "darwin"`
branches. `cli.py`'s `detect_terminal_info()` shells out to macOS/Linux-only
`ps` and reads `__CFBundleIdentifier`, which doesn't exist on Windows.

Goals for this refactor:

1. Add real Windows and Ubuntu (Linux) support, not just macOS with guards.
2. Split the codebase into packages/classes with single, clear
   responsibilities, so an open-source contributor can add or fix one OS's
   behavior by touching one file, without reading or risking the other two.
3. Do this without changing the CLI commands, the hook JSON payload format,
   or the UI (`ui/`) — this is an internal restructuring plus new backend
   implementations, not a feature or protocol change.

The project will also ship packaged macOS and Windows apps via GitHub
Releases (PyInstaller/py2app-style). Platform-marker dependencies (Section 6)
mean each packaged build only bundles the OS-specific libraries it actually
needs. Linux stays a pip/poetry install for now — no packaged Linux app in
this pass.

## Non-goals

- No tray icon on Windows/Linux in this pass (macOS keeps its native
  `NSStatusBar` tray; Windows/Linux get none until a future pass — see
  Roadmap in README.md).
- No attempt to replicate "join all virtual desktops/workspaces" on
  Windows/Linux — out of scope, mark as a known limitation.
- No change to the hook event JSON schema, HTTP server protocol, or any
  `poetry run vibe-hud <command>` behavior.
- No UI/CSS changes.

## Package layout

```
vibe_hud/
  __init__.py
  __main__.py
  cli.py                     # argument parsing + dispatch only (thin)
  core/
    __init__.py
    settings.py              # Settings: defaults, load/save, geometry math
    session_store.py         # SessionStore: sessions dict, lock, state machine, dismiss sweep
    server.py                # HudServer (moved as-is, already OS-agnostic)
    hooks.py                 # HooksManager (moved as-is, already OS-agnostic)
  app.py                      # VibeHudApp + VibeHudApi: thin orchestrator
  platform/
    __init__.py               # get_backend() factory
    base.py                   # PlatformBackend ABC + shared IDE-CLI jump helper
    macos.py                  # AppKit window tricks, NSStatusBar tray, mac terminal detect/focus
    windows.py                  # pywin32 always-on-top/focus, terminal detect via psutil
    linux.py                    # best-effort always-on-top/focus (wmctrl/xdotool), terminal detect via psutil
  ui/                          # unchanged
```

Rule of thumb: platform-specific behavior lives only under `platform/`.
Everything under `core/` and `app.py` must run on any OS with no
`sys.platform` checks.

## Components

### `platform.base.PlatformBackend` (ABC)

```python
class PlatformBackend(ABC):
    def configure_window(self, window) -> None: ...
    def set_always_on_top(self, window, value: bool) -> None: ...
    def bring_to_front(self, window) -> None: ...
    def setup_tray(self, app) -> None: ...            # no-op outside macOS for now
    def detect_terminal_info(self) -> dict: ...
    def focus_session(self, session: dict) -> bool: ...
```

`platform/__init__.py`'s `get_backend()` picks the concrete class once, by
`sys.platform`, and both `app.py` (GUI process) and `cli.py`'s `hook()`
(short-lived hook subprocess) call through the same factory.

`focus_session` on every backend calls a **shared** helper,
`base.jump_via_ide_cli(session)`, first. That helper (today's
`_jump_via_ide_cli` in `window.py`) is OS-agnostic already — `code -r`,
`idea <path>`, `shutil.which()`, `subprocess.Popen()` all behave the same on
macOS/Windows/Linux — so it moves to `base.py` and is not duplicated per
backend. Each backend only implements what happens when no IDE CLI matches.

### `platform.macos.MacOSBackend`

Existing logic, relocated and wrapped in a class instead of free functions:
`NSWindowCollectionBehaviorCanJoinAllSpaces`, `on_top` /
`NSStatusWindowLevel` handling, `NSStatusBar` tray with the Show/Center/Quit
menu, and the terminal-focus fallback chain (`NSRunningApplication`
activation → `osascript` for iTerm/Terminal.app → `open -a Terminal <cwd>`).
`detect_terminal_info` keeps its `__CFBundleIdentifier` /
`ITERM_SESSION_ID` / `TERMINAL_EMULATOR` reads, but the ancestor-process walk
switches from manual `ps` subprocess parsing to `psutil`.

### `platform.windows.WindowsBackend`

New. `configure_window`/`bring_to_front` are best-effort using `pywin32`
(`SetForegroundWindow`, `ShowWindow`), gated by `try/except ImportError` —
same defensive pattern already used for AppKit imports, so a build without
`pywin32` installed degrades to "always-on-top via pywebview's own
`on_top=` flag only" rather than crashing. `setup_tray` is a no-op.
`detect_terminal_info` walks ancestors via `psutil` and reads `WT_SESSION`
(Windows Terminal) / `TERM_PROGRAM=vscode`; unlike macOS, the VS Code-family
fork is identified directly from the ancestor's executable name
(`Code.exe`, `Cursor.exe`, `Windsurf.exe`, ...) since Windows doesn't share
one generic host process across forks the way "Electron" does on macOS — no
bundle-id-style lookup table needed. `focus_session` falls back to
`SetForegroundWindow` on the matched `app_pid` if `pywin32` is available,
else no-ops.

### `platform.linux.LinuxBackend`

New. `configure_window`/`bring_to_front` are no-ops beyond pywebview's own
`on_top=` flag (X11/Wayland window-manager behavior varies too much for a
generic always-on-top hack without extra system deps). `setup_tray` is a
no-op. `detect_terminal_info` walks ancestors via `psutil` and reads
`VTE_VERSION` (gnome-terminal/tilix/etc.), `KONSOLE_VERSION`,
`TERM_PROGRAM=vscode` with fork identification by executable name, same as
Windows. `focus_session` shells out to `wmctrl -a` or `xdotool
windowactivate` by pid if either binary is present (`shutil.which()`-gated,
same "missing tool → skip silently" pattern as the existing IDE-CLI check);
otherwise no-op.

### `core.session_store.SessionStore`

Extracted from `VibeHudApp`: owns the `sessions` dict, its lock, and the
event-driven state machine currently split across
`handle_incoming_event`/`_apply_event` in `window.py`. Public surface:
`apply_event(payload) -> None`, `dismiss(session_id) -> None`,
`sweep_expired(auto_dismiss_sec) -> list[str]` (returns dismissed ids so the
caller can decide whether to broadcast), `to_state_data() -> dict` (today's
`broadcast_state` payload-building, minus the actual `evaluate_js` call).
Zero pywebview/AppKit imports — fully unit-testable with plain dicts.

### `core.settings.Settings`

Extracted from `VibeHudApp`: defaults dict, `load()`/`save()` against
`~/.vibe-hud/settings.json`, and the pure geometry helpers
(`collapsed_size`/`expanded_size`/`_scaled`, using the `SCALE_FACTORS`
table). No GUI imports.

### `app.VibeHudApp` / `app.VibeHudApi`

Thin orchestrator: constructs `Settings`, `SessionStore`, `get_backend()`,
`HudServer`; wires pywebview window creation/resizing; on incoming events,
calls `session_store.apply_event()` then pushes
`session_store.to_state_data()` via `window.evaluate_js`; delegates every
platform-forked call (`configure_window`, `set_always_on_top`,
`bring_to_front`, `setup_tray`, `focus_session`) to `self.backend`.
`VibeHudApi` (the `js_api` object exposed to the WebKit UI) is unchanged in
shape — it still just forwards to controller methods.

### `cli.py`

Unchanged commands/output. Only change: `hook()` calls
`platform.get_backend().detect_terminal_info()` instead of the standalone
macOS-flavored `detect_terminal_info()` function, which is deleted from
`cli.py`.

### `core.server.HudServer`, `core.hooks.HooksManager`

Moved from `vibe_hud/server.py` and `vibe_hud/hooks.py` to
`vibe_hud/core/server.py` and `vibe_hud/core/hooks.py` with no logic
changes — both are already OS-agnostic (`http.server`, `Path.home()`, JSON
file I/O all work identically on the three target OSes).

## Data flow (unchanged)

```
Claude Code hook → vibe-hud-hook (cli.hook()) → platform.get_backend().detect_terminal_info()
                                               → HTTP POST :28790/event (or file fallback)
                                               → HudServer → SessionStore.apply_event()
                                               → VibeHudApp.broadcast() → window.evaluate_js(updateState)
```

Click-to-focus:
```
UI click → VibeHudApi.focus_session(id) → VibeHudApp → backend.focus_session(session)
         → base.jump_via_ide_cli() first, then the backend's own native fallback
```

## Error handling

Every platform-specific call stays defensive the way `window.py` already is
today: optional imports (`pywin32`, `AppKit`) are wrapped in
`try/except ImportError`, external CLIs/binaries are gated by
`shutil.which()` before use, and any failure degrades to "do less" (skip the
tray, skip the focus fallback, fall back to plain app activation) rather
than raising out of the event-handling path. No new error-handling pattern
is introduced — this refactor relocates existing patterns, and applies the
same pattern to the two new backends.

## Testing

- `core/session_store.py` and `core/settings.py` become unit-testable in
  plain `pytest` with no GUI/OS dependency — first real test coverage this
  project will have (currently zero automated tests exist, per
  `README.md`'s roadmap item "Unit tests for server.py state machine").
- `platform/*.py` backends are integration-only / manually verified per OS
  (consistent with how the current macOS behavior has been verified
  throughout this project — live testing, not automated, since window
  focus/tray behavior isn't meaningfully unit-testable).
- No behavior change to `core/server.py`/`core/hooks.py` beyond their move;
  existing manual verification (hook install/remove, HTTP POST) still
  applies.

## Dependencies (`pyproject.toml`)

```toml
dependencies = [
    "pywebview (>=6.2.1,<7.0.0)",
    "psutil (>=6.0.0,<7.0.0)",
]

[tool.poetry.dependencies]
pywin32 = {version = "*", markers = "sys_platform == 'win32'"}
```

`psutil` replaces the current raw `ps` subprocess parsing everywhere,
including on macOS — a simplification, not just an addition, since `ps -o
comm=` has no Windows equivalent. `pyobjc`/`AppKit` stays an implicit
transitive dependency via pywebview's own macOS (`cocoa`) extra, as today —
no change there.

## Rollout

This spec covers the target architecture; the implementation plan (next
step, via the `writing-plans` skill) will sequence it roughly as:

1. Extract `core/` (SessionStore, Settings) and relocate `server.py`/
   `hooks.py` — pure refactor, no behavior change, verified against current
   macOS behavior.
2. Introduce `platform/base.py` + `platform/macos.py`, moving all existing
   AppKit/mac-specific code out of `window.py` verbatim into the new class,
   with `app.py` replacing `window.py` as the thin orchestrator.
3. Add `platform/windows.py` and `platform/linux.py` as new backends.
4. Update `pyproject.toml` dependencies and `README.md`/`AGENTS.md` platform
   claims.
