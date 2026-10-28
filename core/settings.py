"""ユーザー設定の永続化（JSON、Documents/StampApp/settings.json）。"""
import json
from pathlib import Path

from core.edition import DATA_NAME

DEFAULT_SETTINGS = {
    "name": "山田 太郎",
    "affiliation": "営業部",
    "diameter_mm": 15.0,
    "line_width_pt": 1.0,
    "font_key": "Noto Sans JP Regular",
    "selected_mark": 0,
    "stamp_color": "#E60033",
    # 詳細設定（手動補正）
    "name_size_scale": 1.0,
    "name_y_offset_mm": 0.0,
    "aff_size_scale": 1.0,
    "aff_y_offset_mm": 0.0,
}


def settings_path() -> Path:
    return Path.home() / "Documents" / DATA_NAME / "settings.json"


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        # 旧形式（文字マーク）や不正値は既定のマーカーID(0)へ補正する
        if merged.get("selected_mark") not in (0, 1, 2, 3, 4):
            merged["selected_mark"] = 0
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)


def save_settings(values: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    to_save = {k: values.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}
    with path.open("w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)
