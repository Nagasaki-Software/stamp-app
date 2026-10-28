import json

from core import settings


def test_default_selected_mark_is_zero():
    assert settings.DEFAULT_SETTINGS["selected_mark"] == 0


def test_load_coerces_legacy_string_mark_to_zero(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"selected_mark": "㊎", "name": "X"}), encoding="utf-8")
    monkeypatch.setattr(settings, "settings_path", lambda: p)
    s = settings.load_settings()
    assert s["selected_mark"] == 0
    assert s["name"] == "X"


def test_load_keeps_valid_int_mark(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"selected_mark": 3}), encoding="utf-8")
    monkeypatch.setattr(settings, "settings_path", lambda: p)
    assert settings.load_settings()["selected_mark"] == 3
