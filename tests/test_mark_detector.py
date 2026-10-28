import io
from pathlib import Path

import cv2
import pymupdf as fitz
import numpy as np
from PIL import Image

from core import markers
from core.mark_detector import detect_marks

SAMPLES = Path("tests/samples")


def _png_bytes(marker_id: int, module_px: int = 30) -> bytes:
    buf = io.BytesIO()
    markers.render_marker_png(marker_id, module_px=module_px).save(buf, format="PNG")
    return buf.getvalue()


def _digital_pdf(path: Path, placements):
    """placements: [(page_index, marker_id, x_pt, y_pt, width_pt), ...]"""
    SAMPLES.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    n_pages = max(p for p, *_ in placements) + 1
    for _ in range(n_pages):
        doc.new_page(width=595, height=842)
    for pidx, mid, x, y, s in placements:
        # PNGアスペクト比 横10:縦13。Pageは保持せず都度 doc[pidx] で取得する。
        doc[pidx].insert_image(
            fitz.Rect(x, y, x + s, y + s * 13 / 10), stream=_png_bytes(mid)
        )
    doc.save(path)
    doc.close()


def test_detect_digital_insert_matches_selected_id_only():
    path = SAMPLES / "aruco_digital.pdf"
    _digital_pdf(path, [(0, 2, 100, 100, 60), (1, 2, 300, 400, 60), (1, 0, 100, 100, 60)])
    doc = fitz.open(path)
    res = detect_marks(doc, 2)
    doc.close()
    assert len(res[0]) == 1
    assert len(res[1]) == 1  # ページ1の id0 は対象外
    x, y, w, h = res[0][0]
    cx = x + w / 2
    assert 100 < cx < 200  # 配置付近に中心がある


def test_detect_unknown_id_raises():
    import pytest
    doc = fitz.open()
    doc.new_page()
    try:
        with pytest.raises(ValueError):
            detect_marks(doc, 9)
    finally:
        doc.close()


def test_no_false_positive_on_text_and_other_ids():
    """文章＋別IDマーカーのページで、選択IDの検出が0件であること（誤検出ゼロ）。"""
    path = SAMPLES / "aruco_negative.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Contract Article 1 2 3 approve seal " * 6, fontsize=12)
    page.insert_image(fitz.Rect(400, 600, 460, 678), stream=_png_bytes(3))  # 別ID
    doc.save(path)
    doc.close()
    doc = fitz.open(path)
    res = detect_marks(doc, 0)  # id0 は存在しない
    doc.close()
    assert res[0] == []


def test_detect_scanned_image_pdf():
    """画像レイヤのみ（スキャン想定）のPDFでも検出できること。"""
    path = SAMPLES / "aruco_scanned.pdf"
    SAMPLES.mkdir(parents=True, exist_ok=True)
    page_img = Image.new("L", (1240, 1754), 255)  # A4 150dpi 相当
    page_img.paste(markers.render_marker_png(4, module_px=20), (300, 400))
    img_path = SAMPLES / "aruco_scanned.png"
    page_img.save(img_path)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=str(img_path))
    doc.save(path)
    doc.close()
    img_path.unlink()
    doc = fitz.open(path)
    res = detect_marks(doc, 4)
    doc.close()
    assert len(res[0]) >= 1


def test_rotated_page_returns_mediabox_coords():
    """A4横印刷を縦スキャン→/Rotate 90 補正したページでも mediabox 座標で返す。"""
    path = SAMPLES / "aruco_rotated.pdf"
    SAMPLES.mkdir(parents=True, exist_ok=True)
    upright = Image.new("L", (1754, 1240), 255)
    upright.paste(markers.render_marker_png(1, module_px=20), (250, 250))
    sideways = upright.rotate(90, expand=True)  # 縦向き・内容は横倒し
    img_path = path.with_suffix(".png")
    sideways.save(img_path)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=str(img_path))
    page.set_rotation(90)
    doc.save(path)
    doc.close()
    img_path.unlink()

    doc = fitz.open(path)
    res = detect_marks(doc, 1)
    page = doc[0]
    assert res[0], "回転PDFで検出0件 → 座標変換が効いていない"
    x, y, w, h = res[0][0]
    assert 0 <= x <= page.mediabox.width
    assert 0 <= y <= page.mediabox.height
    doc.close()
