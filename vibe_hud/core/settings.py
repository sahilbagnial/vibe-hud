import json
from pathlib import Path

SCALE_FACTORS = {"small": 0.88, "medium": 1.0, "large": 1.15}

DEFAULT_SETTINGS = {
    "theme": "dark-glass",
    "orientation": "horizontal",
    "scale": "medium",
    "soundEnabled": True,
    "soundStyle": "marimba",
    "soundVolume": 0.8,
    "autoDismissSec": 60,
    "alwaysOnTop": True,
    "colorblindMode": False,
}


class Settings:
    """Loads/persists ~/.vibe-hud/settings.json and holds the pure geometry
    math for window sizing. No GUI or OS-specific imports."""

    def __init__(self, settings_file: Path):
        self.settings_file = settings_file
        self.data = self._load()

    def _load(self) -> dict:
        data = dict(DEFAULT_SETTINGS)
        if self.settings_file.exists():
            try:
                data.update(json.loads(self.settings_file.read_text(encoding="utf-8")))
            except Exception:
                pass
        return data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, new_data: dict) -> None:
        self.data.update(new_data)
        self._save()

    def _save(self) -> None:
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            self.settings_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[vibe-hud] Error saving settings: {e}")

    def collapsed_size(self, orientation: str) -> tuple:
        # Must match the body / body[data-orientation="vertical"] base sizes
        # in ui/style.css.
        base = (68, 260) if orientation == "vertical" else (336, 100)
        return self._scaled(base)

    def expanded_size(self, orientation: str) -> tuple:
        # Must match the body[data-orientation="vertical"][data-expanded="true"]
        # and body[data-expanded="true"] base sizes in ui/style.css.
        base = (396, 420) if orientation == "vertical" else (420, 440)
        return self._scaled(base)

    def _scaled(self, size: tuple) -> tuple:
        factor = SCALE_FACTORS.get(self.data.get("scale", "medium"), 1.0)
        w, h = size
        return int(w * factor), int(h * factor)
