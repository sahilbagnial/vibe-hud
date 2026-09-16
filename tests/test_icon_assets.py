# tests/test_icon_assets.py
from pathlib import Path
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_briefcase_icon_files_exist_and_are_valid_images():
    # .icns is excluded here since it's macOS-only (built via iconutil) and
    # is covered separately by Briefcase's macOS-only consumer in Task 5.
    # .ico is NOT platform-gated (produced unconditionally by generate_icon.py
    # on every OS), so it belongs in this regression check.
    for name in ("vibe-hud-1024.png", "vibe-hud-512.png", "vibe-hud.ico"):
        path = REPO_ROOT / "assets" / "icon" / name
        assert path.exists(), f"missing {path}"
        with Image.open(path) as img:
            img.verify()


def test_tray_icon_files_exist_inside_the_package():
    for name in ("tray-icon-32.png", "tray-icon-64.png"):
        path = REPO_ROOT / "vibe_hud" / "assets" / name
        assert path.exists(), f"missing {path}"
        with Image.open(path) as img:
            img.verify()
