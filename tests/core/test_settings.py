import json
from vibe_hud.core.settings import Settings, DEFAULT_SETTINGS


def test_defaults_when_no_file(tmp_path):
    s = Settings(tmp_path / "settings.json")
    assert s.data == DEFAULT_SETTINGS


def test_load_merges_with_defaults(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"theme": "light", "scale": "large"}))
    s = Settings(f)
    assert s.data["theme"] == "light"
    assert s.data["scale"] == "large"
    assert s.data["autoDismissSec"] == DEFAULT_SETTINGS["autoDismissSec"]


def test_update_persists_to_disk(tmp_path):
    f = tmp_path / "settings.json"
    s = Settings(f)
    s.update({"alwaysOnTop": False})
    assert s.data["alwaysOnTop"] is False
    reloaded = Settings(f)
    assert reloaded.data["alwaysOnTop"] is False


def test_get_returns_default_for_missing_key(tmp_path):
    s = Settings(tmp_path / "settings.json")
    assert s.get("nope", "fallback") == "fallback"


def test_collapsed_size_horizontal_medium(tmp_path):
    s = Settings(tmp_path / "settings.json")
    assert s.collapsed_size("horizontal") == (336, 100)


def test_collapsed_size_vertical_medium(tmp_path):
    s = Settings(tmp_path / "settings.json")
    assert s.collapsed_size("vertical") == (68, 260)


def test_expanded_size_scales_with_large(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"scale": "large"}))
    s = Settings(f)
    w, h = s.expanded_size("horizontal")
    assert (w, h) == (int(420 * 1.15), int(440 * 1.15))
