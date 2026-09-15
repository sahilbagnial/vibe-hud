import sys


def get_backend():
    """Picks the concrete PlatformBackend for the running OS. Imported
    lazily inside the branch so a build only needs the OS-specific module
    (and its optional imports like AppKit/pywin32) for its own platform."""
    if sys.platform == "darwin":
        from vibe_hud.platform.macos import MacOSBackend
        return MacOSBackend()
    if sys.platform.startswith("win"):
        from vibe_hud.platform.windows import WindowsBackend
        return WindowsBackend()
    from vibe_hud.platform.linux import LinuxBackend
    return LinuxBackend()
