"""利用可能フォントの一覧管理。assets/fonts/ 配下の .otf/.ttf を表示名→パスで返す。"""
from pathlib import Path

# 既知ファイル名 → 表示名の対応。未登録は basename をそのまま使用。
KNOWN_DISPLAY_NAMES = {
    "NotoSansJP-Regular.otf": "Noto Sans JP Regular",
    "NotoSansJP-Bold.otf": "Noto Sans JP Bold",
    "NotoSerifJP-Regular.otf": "Noto Serif JP Regular",
}


def list_fonts(fonts_dir: Path) -> dict[str, Path]:
    """フォントディレクトリ内のフォント一覧を {表示名: パス} で返す。"""
    if not fonts_dir.exists():
        return {}
    result: dict[str, Path] = {}
    for p in sorted(fonts_dir.iterdir()):
        if p.suffix.lower() not in (".otf", ".ttf"):
            continue
        display = KNOWN_DISPLAY_NAMES.get(p.name, p.stem)
        result[display] = p
    return result


def resolve_font(fonts_dir: Path, font_key: str) -> Path:
    """表示名からパス解決。未知の場合は最初のフォントにフォールバック。"""
    fonts = list_fonts(fonts_dir)
    if not fonts:
        raise FileNotFoundError(f"フォントが見つかりません: {fonts_dir}")
    if font_key in fonts:
        return fonts[font_key]
    return next(iter(fonts.values()))
