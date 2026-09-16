import os
import shutil
import subprocess
from abc import ABC, abstractmethod

import psutil


class PlatformBackend(ABC):
    """One implementation per OS. All sys.platform branching in the app
    lives behind this interface — core/ and app.py never check sys.platform
    directly."""

    @abstractmethod
    def configure_window(self, window) -> None:
        """Post-load, OS-specific window tweaks (e.g. macOS collection behavior)."""

    @abstractmethod
    def set_always_on_top(self, window, value: bool) -> None:
        ...

    @abstractmethod
    def bring_to_front(self, window) -> None:
        ...

    @abstractmethod
    def setup_tray(self, app) -> None:
        """Menu bar / system tray icon. No-op on platforms without one yet."""

    @abstractmethod
    def detect_terminal_info(self) -> dict:
        """Called from the short-lived hook subprocess to identify the
        calling terminal/IDE. Returns a flat dict merged into the hook payload."""

    @abstractmethod
    def focus_session(self, session: dict) -> bool:
        """Jump to the window backing this session. Returns True if a jump
        was attempted."""


def jump_via_ide_cli(session: dict, resolve_cli) -> bool:
    """Reopen the session's cwd via the IDE's own CLI (`code -r`, `idea`,
    etc.) so an already-open window for that project gets focused directly,
    instead of just activating the app and landing on whatever window it
    last had up. `resolve_cli(session)` returns the CLI executable name for
    this session's IDE, or None if unknown — OS-specific backends supply
    their own resolver (bundle id on macOS, executable name on
    Windows/Linux) since that lookup differs per OS, but the actual
    subprocess launch is identical everywhere. Returns True if a jump was
    attempted."""
    cwd = session.get("cwd")
    if not cwd or not os.path.exists(cwd):
        return False
    # Reuse-window matching is a string comparison against however the IDE
    # has the folder open internally; resolve symlinks/relative bits so a
    # session's raw cwd is as likely as possible to match exactly.
    cwd = os.path.realpath(cwd)

    cli = resolve_cli(session)
    if not cli or not shutil.which(cli):
        return False

    terminal_emulator = session.get("terminal_emulator") or ""
    args = [cwd] if terminal_emulator == "JetBrains-JediTerm" else ["-r", cwd]

    try:
        subprocess.Popen([cli, *args])
        return True
    except Exception as e:
        print(f"[vibe-hud] IDE CLI jump error ({cli}): {e}")
        return False


def walk_ancestor_processes(max_depth: int = 12):
    """Return the chain of ancestor processes starting at the immediate
    parent of the current process (the shell that ran the hook), walking
    upward. Stops after max_depth hops or when a parent can no longer be
    resolved. Used by Windows/Linux backends to find the terminal/IDE
    process by executable name (macOS uses its own dedicated walk to match
    its existing, already-verified "child of launchd" logic)."""
    chain = []
    try:
        curr = psutil.Process(os.getppid())
    except Exception:
        return chain
    for _ in range(max_depth):
        chain.append(curr)
        try:
            parent = curr.parent()
        except Exception:
            break
        if parent is None or parent.pid == curr.pid:
            break
        curr = parent
    return chain


def build_tray_menu(app):
    """Pure factory for the tray menu shared by pystray-based backends
    (Windows/Linux). macOS doesn't use this — its NSStatusBar/NSMenu
    implementation predates this helper and already works, so it's left
    alone rather than migrated for the sake of one shared code path."""
    import pystray

    return pystray.Menu(
        pystray.MenuItem("Show / Bring to Front", lambda icon, item: app.bring_to_front()),
        pystray.MenuItem("Center on Screen", lambda icon, item: app.center_window()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Vibe HUD", lambda icon, item: app.quit_app()),
    )


def setup_pystray_tray(app, icon_path: str) -> None:
    """Shared Windows/Linux tray setup: loads the icon image and runs a
    pystray.Icon with the standard Show/Center/Quit menu in a background
    thread, so it never blocks pywebview's own main loop."""
    try:
        import threading

        import pystray
        from PIL import Image

        image = Image.open(icon_path)
        icon = pystray.Icon("vibe-hud", image, "Vibe HUD", menu=build_tray_menu(app))
        threading.Thread(target=icon.run, daemon=True).start()
    except Exception as e:
        print(f"[vibe-hud] Warning setting up tray: {e}")
