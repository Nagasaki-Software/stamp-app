"""ArUcoマーカーの定義と生成（6×6行列 / PNG / SVG / 印刷PDF）。

検出は core/mark_detector.py が担う。本モジュールは「マーカーを作る」責務のみ。
"""
import io
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw

# 4×4の大きなマス。5種に十分な容量があり、低画質スキャン・小サイズ印刷に強い。
ARUCO_DICT_ID = cv2.aruco.DICT_4X4_50
MARKER_IDS = [0, 1, 2, 3, 4]
MARKER_LABELS = {0: "No.1", 1: "No.2", 2: "No.3", 3: "No.4", 4: "No.5"}

# 1マーカー = 6×6モジュール（データ4×4 + 黒枠1モジュール）
_MODULES = 6


def get_dictionary():
    return cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)


def marker_matrix(marker_id: int) -> np.ndarray:
    """6×6 のモジュール行列を返す（1=黒, 0=白）。"""
    if marker_id not in MARKER_IDS:
        raise ValueError(f"未対応のマーカーID: {marker_id}")
    img = cv2.aruco.generateImageMarker(get_dictionary(), marker_id, _MODULES)
    return (img == 0).astype(np.uint8)


def render_marker_png(marker_id: int, module_px: int = 200, quiet_modules: int = 2) -> Image.Image:
    """白い余白（クワイエットゾーン）付きの正方形マーカーPNGを返す。

    画像サイズ（モジュール換算）：6 + 2*quiet（既定 quiet=2 で 10×10 モジュール）。
    番号ラベルは焼き込まない（押印で消去できず残ってしまうため）。識別はファイル名で行う。
    """
    mat = marker_matrix(marker_id)
    pat = _MODULES * module_px
    quiet = quiet_modules * module_px
    side = pat + 2 * quiet

    img = Image.new("L", (side, side), 255)
    draw = ImageDraw.Draw(img)
    for r in range(_MODULES):
        for c in range(_MODULES):
            if mat[r, c]:
                x0 = quiet + c * module_px
                y0 = quiet + r * module_px
                draw.rectangle([x0, y0, x0 + module_px - 1, y0 + module_px - 1], fill=0)
    return img


def render_marker_svg(marker_id: int, marker_mm: float = 10.0, quiet_modules: int = 2) -> str:
    """ベクターSVG文字列を返す。パターン本体が marker_mm 四方になるよう実寸指定。

    番号ラベルは付けない（押印で消去できず残ってしまうため）。識別はファイル名で行う。
    """
    mat = marker_matrix(marker_id)
    vb = _MODULES + 2 * quiet_modules            # 既定10
    mm_per_module = marker_mm / _MODULES
    size_mm = vb * mm_per_module

    rects = []
    for r in range(_MODULES):
        for c in range(_MODULES):
            if mat[r, c]:
                rects.append(
                    f'<rect x="{quiet_modules + c}" y="{quiet_modules + r}" '
                    f'width="1" height="1" fill="#000"/>'
                )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size_mm:.3f}mm" height="{size_mm:.3f}mm" '
        f'viewBox="0 0 {vb} {vb}">'
        f'<rect x="0" y="0" width="{vb}" height="{vb}" fill="#fff"/>'
        + "".join(rects)
        + "</svg>"
    )


def build_printable_pdf(out_path: Path, marker_mm: float = 10.0) -> None:
    """A4 1枚に5種マーカーを実寸配置した印刷用PDFを作る。

    PyMuPDF既定フォントは日本語を描画できないため、シート上の注記は英語にする
    （日本語の詳しい手順は 使い方.txt 側に記載）。マーカーのラベル「No.1」等は
    PNG内に焼き込み済み。
    """
    mm = 72 / 25.4  # 1mm = 約2.835pt
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    page.insert_text((40, 50), "StampApp - ArUco marker sheet", fontsize=14)
    page.insert_text(
        (40, 72),
        f"Recommended size: approx {marker_mm:.0f} mm square (pattern). "
        "Keep aspect ratio. Do not skew/rotate.",
        fontsize=9,
    )
    side_mm = marker_mm * 10 / 6   # PNG全体（パターン+余白、正方形）
    side = side_mm * mm
    x_left, y_top = 60, 100
    col_gap, row_gap = 240, side + 50
    for i, mid in enumerate(MARKER_IDS):
        col, row = i % 2, i // 2
        x = x_left + col * col_gap
        y = y_top + row * row_gap
        png = render_marker_png(mid, module_px=60)
        buf = io.BytesIO()
        png.save(buf, format="PNG")
        page.insert_image(fitz.Rect(x, y, x + side, y + side), stream=buf.getvalue())
        # 番号はマーカーの外（シート上）に記載。マーカーを切り出せば押印対象には入らない。
        page.insert_text((x, y + side + 14), MARKER_LABELS[mid], fontsize=11)
    doc.save(out_path)
    doc.close()


def export_all(out_dir) -> list:
    """PNG×5・SVG×5・印刷PDF×1 を out_dir に書き出し、生成パス一覧を返す。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list = []
    for mid in MARKER_IDS:
        name = MARKER_LABELS[mid].replace(".", "").lower()  # "no1"
        png_path = out_dir / f"marker_{name}.png"
        render_marker_png(mid).save(png_path)
        written.append(png_path)
        svg_path = out_dir / f"marker_{name}.svg"
        svg_path.write_text(render_marker_svg(mid), encoding="utf-8")
        written.append(svg_path)
    pdf_path = out_dir / "markers_print.pdf"
    build_printable_pdf(pdf_path)
    written.append(pdf_path)
    return written
