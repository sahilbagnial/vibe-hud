# assets/icon/generate_icon.py
"""Regenerates every vibe-hud icon asset from one drawing routine.
Run with: poetry run python assets/icon/generate_icon.py
Requires `iconutil` (macOS-only, ships with Xcode command line tools) to
produce the .icns file — run this on a Mac.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIEFCASE_ICON_DIR = REPO_ROOT / "assets" / "icon"
PACKAGE_ASSET_DIR = REPO_ROOT / "vibe_hud" / "assets"

# Colors match the existing HUD status palette (see ui/style.css) so the
# tray icon reads as "the same app" as the floating pill.
BG = (30, 30, 34, 255)
RED = (239, 68, 68, 255)
AMBER = (245, 158, 11, 255)
GREEN = (34, 197, 94, 255)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = size * 0.08
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=size * 0.22,
        fill=BG,
    )
    dot_r = size * 0.12
    cx = size / 2
    for i, color in enumerate((RED, AMBER, GREEN)):
        cy = size * 0.28 + i * size * 0.22
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=color)
    return img


def main():
    BRIEFCASE_ICON_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_ASSET_DIR.mkdir(parents=True, exist_ok=True)

    master = draw_icon(1024)
    master.save(BRIEFCASE_ICON_DIR / "vibe-hud-1024.png")
    draw_icon(512).save(BRIEFCASE_ICON_DIR / "vibe-hud-512.png")

    master.save(BRIEFCASE_ICON_DIR / "vibe-hud.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])

    draw_icon(32).save(PACKAGE_ASSET_DIR / "tray-icon-32.png")
    draw_icon(64).save(PACKAGE_ASSET_DIR / "tray-icon-64.png")

    if sys.platform == "darwin":
        _build_icns(master)
    else:
        print("[generate_icon] Skipping .icns (needs macOS + iconutil) — "
              "run this script on a Mac to produce assets/icon/vibe-hud.icns")


def _build_icns(master: Image.Image):
    iconset_dir = BRIEFCASE_ICON_DIR / "vibe-hud.iconset"
    iconset_dir.mkdir(exist_ok=True)
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        master.resize((size, size), Image.LANCZOS).save(iconset_dir / f"icon_{size}x{size}.png")
        if size <= 512:
            master.resize((size * 2, size * 2), Image.LANCZOS).save(iconset_dir / f"icon_{size}x{size}@2x.png")
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(BRIEFCASE_ICON_DIR / "vibe-hud.icns")],
        check=True,
    )
    for f in iconset_dir.glob("*"):
        f.unlink()
    iconset_dir.rmdir()


if __name__ == "__main__":
    main()
