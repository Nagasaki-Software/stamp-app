"""円形3分割スタンプPNG生成。

レイアウト：上=名前 / 中=日付 / 下=所属。背景透明、朱色固定。
名前と所属はフォントサイズ倍率・上下位置補正を手動で設定できる。
"""
from math import sqrt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VERMILLION = (230, 0, 51, 255)  # #E60033
DPI = 600
MM_TO_INCH = 1 / 25.4
PT_TO_PX = DPI / 72

TEXT_HEIGHT_RATIO = 0.18
TEXT_DIVIDER_GAP_RATIO = 0.02
CHORD_SAFETY = 0.78


def _parse_color(color) -> tuple:
    """色指定を RGBA タプルに正規化する。

    対応: '#RRGGBB' / 'RRGGBB' / (r, g, b) / (r, g, b, a)。
    不正な値のときは既定の朱色（VERMILLION）を返す。
    """
    if isinstance(color, (tuple, list)):
        if len(color) == 3:
            return (int(color[0]), int(color[1]), int(color[2]), 255)
        if len(color) >= 4:
            return (int(color[0]), int(color[1]), int(color[2]), int(color[3]))
        return VERMILLION
    s = str(color).strip().lstrip("#")
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
        except ValueError:
            return VERMILLION
    return VERMILLION


def _mm_to_px(mm: float) -> int:
    return int(round(mm * MM_TO_INCH * DPI))


def _fit_font_size(
    text: str, max_width: int, max_height: int, font_path: Path
) -> int:
    """テキストが max_width × max_height に収まる最大フォント「ピクセルサイズ」を返す。"""
    size = max(max_height, 8)
    while size > 4:
        font = ImageFont.truetype(str(font_path), size)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_width and h <= max_height:
            return size
        size -= 1
    return 4


def _chord_at(inner_r: float, cy: float, y: float) -> float:
    dy = y - cy
    if abs(dy) >= inner_r:
        return 0.0
    return 2 * sqrt(inner_r * inner_r - dy * dy)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: float,
    cy: float,
    font: ImageFont.FreeTypeFont,
    color: tuple,
):
    """テキストの実bbox中心を (cx, cy) に厳密に合わせて描画。"""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1]
    draw.text((tx, ty), text, fill=color, font=font)


def _auto_font_size(
    text: str,
    cy_auto: float,
    target_h: int,
    inner_r: float,
    center_y: float,
    font_path: Path,
) -> int:
    """自動位置 cy_auto・基本高さ target_h での自動フィット結果サイズ（補正前）。"""
    chord_top = _chord_at(inner_r, center_y, cy_auto - target_h / 2)
    chord_bot = _chord_at(inner_r, center_y, cy_auto + target_h / 2)
    chord_mid = _chord_at(inner_r, center_y, cy_auto)
    chord = min(chord_top, chord_bot, chord_mid)
    if chord <= 0:
        return 4
    max_w = int(chord * CHORD_SAFETY)
    return _fit_font_size(text, max_w, target_h, font_path)


def generate_stamp(
    name: str,
    date_str: str,
    affiliation: str,
    diameter_mm: float,
    line_width_pt: float,
    font_path: Path,
    name_size_scale: float = 1.0,
    name_y_offset_mm: float = 0.0,
    aff_size_scale: float = 1.0,
    aff_y_offset_mm: float = 0.0,
    color=VERMILLION,
) -> Image.Image:
    """円形3分割スタンプを RGBA PIL Image で返す。

    動作:
        1. 各テキストの「自動位置」での最適フォントサイズを算出
        2. そのサイズに size_scale を掛けて最終サイズを決定
        3. 自動位置 + 上下オフセットの位置に bbox中心を合わせて描画
        size_scale や位置オフセットは互いに独立に作用する。
    """
    size = _mm_to_px(diameter_mm)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ink = _parse_color(color)

    line_w = max(1, int(round(line_width_pt * PT_TO_PX)))
    outer_radius = (size - line_w) / 2
    cx, cy = size / 2, size / 2
    inner_r = outer_radius - line_w / 2

    # 外周円
    draw.ellipse(
        [cx - outer_radius, cy - outer_radius, cx + outer_radius, cy + outer_radius],
        outline=ink,
        width=line_w,
    )

    # 区切り線
    y1 = size * 1 / 3
    y2 = size * 2 / 3
    for y in (y1, y2):
        chord = _chord_at(inner_r, cy, y)
        if chord <= 0:
            continue
        half_chord = chord / 2
        draw.line(
            [(cx - half_chord, y), (cx + half_chord, y)],
            fill=ink,
            width=line_w,
        )

    base_target_h = int(size * TEXT_HEIGHT_RATIO)
    gap = max(int(size * TEXT_DIVIDER_GAP_RATIO), line_w + 1)

    # 自動位置（補正前）
    name_cy_auto = y1 - gap - base_target_h / 2
    aff_cy_auto = y2 + gap + base_target_h / 2
    date_cy = (y1 + y2) / 2

    # 自動フォントサイズ算出（補正前）
    auto_size_name = (
        _auto_font_size(name, name_cy_auto, base_target_h, inner_r, cy, font_path)
        if name else 0
    )
    auto_size_date = (
        _auto_font_size(date_str, date_cy, base_target_h, inner_r, cy, font_path)
        if date_str else 0
    )
    auto_size_aff = (
        _auto_font_size(affiliation, aff_cy_auto, base_target_h, inner_r, cy, font_path)
        if affiliation else 0
    )

    # スケール適用と描画位置
    bands = [
        # (テキスト, 描画y中心, 最終フォントサイズ)
        (
            name,
            name_cy_auto + _mm_to_px(name_y_offset_mm),
            max(4, int(round(auto_size_name * name_size_scale))),
        ),
        (date_str, date_cy, auto_size_date),
        (
            affiliation,
            aff_cy_auto + _mm_to_px(aff_y_offset_mm),
            max(4, int(round(auto_size_aff * aff_size_scale))),
        ),
    ]
    for text, ty, font_size in bands:
        if not text or font_size <= 0:
            continue
        font = ImageFont.truetype(str(font_path), font_size)
        _draw_centered_text(draw, text, cx, ty, font, ink)

    return img
