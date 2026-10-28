from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw

from core.pdf_stamper import stamp_pdf_in_place


def _make_stamp_image() -> Image.Image:
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, 89, 89], fill=(200, 16, 46, 255))
    return img


def test_stamps_only_specified_pages_and_overwrites(tmp_path):
    path = tmp_path / "stamper_test.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()

    detections = {
        0: [],
        1: [(200.0, 300.0, 20.0, 20.0)],
        2: [(100.0, 100.0, 20.0, 20.0), (300.0, 500.0, 20.0, 20.0)],
    }
    pages_stamped = stamp_pdf_in_place(
        pdf_path=path,
        detections=detections,
        stamp_image=_make_stamp_image(),
        stamp_diameter_pt=42.5,  # 15mm
    )
    assert pages_stamped == [2, 3]

    doc = fitz.open(path)
    assert len(doc[0].get_images()) == 0
    assert len(doc[1].get_images()) >= 1
    assert len(doc[2].get_images()) >= 2
    doc.close()


def test_no_detections_means_no_change(tmp_path):
    path = tmp_path / "nochange.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()
    original_bytes = path.read_bytes()

    pages_stamped = stamp_pdf_in_place(
        pdf_path=path,
        detections={0: []},
        stamp_image=_make_stamp_image(),
        stamp_diameter_pt=42.5,
    )
    assert pages_stamped == []
    # 何も検出されていない場合でも上書き保存自体は実行されるが、ページ内容は変わらない
    doc = fitz.open(path)
    assert len(doc[0].get_images()) == 0
    doc.close()


def test_overwrite_failure_keeps_original_intact(tmp_path):
    """置き換えに失敗しても元PDFが失われないこと（Acrobat等で開いたまま押印した場合）。"""
    path = tmp_path / "locked.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()
    before = path.read_bytes()

    with path.open("rb"):  # 他アプリが開いている状態を再現
        with pytest.raises(OSError):
            stamp_pdf_in_place(
                pdf_path=path,
                detections={0: [(200.0, 300.0, 20.0, 20.0)]},
                stamp_image=_make_stamp_image(),
                stamp_diameter_pt=42.5,
            )
    assert path.exists()
    assert path.read_bytes() == before                # 元PDFは無傷
    assert not path.with_suffix(".tmp.pdf").exists()  # 一時ファイルも残らない
