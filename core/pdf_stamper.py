"""マーク領域の白塗り＋スタンプ画像挿入＋上書き保存＋メタデータ埋込。"""
import io
from pathlib import Path
from typing import Optional

import pymupdf as fitz
from PIL import Image

MASK_PADDING_PT = 2.0
META_MARKER = "[StampApp]"


def _stamp_bytes_for_rotation(stamp_image: Image.Image, page_rotation: int) -> bytes:
    """ページの /Rotate 値に応じて、表示時に正立して見えるようスタンプを事前回転。

    PDF /Rotate は時計回り。PIL.rotate は反時計回り。同じ角度を渡すと
    両者がキャンセルして、表示は元のスタンプ画像通り（正立）になる。
    """
    if page_rotation:
        rotated = stamp_image.rotate(page_rotation, expand=True)
    else:
        rotated = stamp_image
    buf = io.BytesIO()
    rotated.save(buf, format="PNG")
    return buf.getvalue()


def stamp_pdf_in_place(
    pdf_path: Path,
    detections: dict[int, list[tuple[float, float, float, float]]],
    stamp_image: Image.Image,
    stamp_diameter_pt: float,
    metadata_record: Optional[str] = None,
) -> list[int]:
    """検出位置にスタンプ画像を貼り、元PDFに上書き保存。

    回転ページ（/Rotate=90/180/270）でも、スタンプは正立して表示されるよう
    ページごとに事前回転してから埋め込む。
    """
    doc = fitz.open(pdf_path)
    stamped_pages: list[int] = []

    half = stamp_diameter_pt / 2

    # 同じ回転値が連続する場合のキャッシュ
    cached_rotation: Optional[int] = None
    cached_bytes: Optional[bytes] = None

    for page_idx, rects in detections.items():
        if not rects:
            continue
        page = doc[page_idx]
        rot = page.rotation
        if rot != cached_rotation:
            cached_bytes = _stamp_bytes_for_rotation(stamp_image, rot)
            cached_rotation = rot
        stamp_bytes = cached_bytes

        for x, y, w, h in rects:
            cx = x + w / 2
            cy = y + h / 2
            mask_rect = fitz.Rect(
                x - MASK_PADDING_PT,
                y - MASK_PADDING_PT,
                x + w + MASK_PADDING_PT,
                y + h + MASK_PADDING_PT,
            )
            page.draw_rect(mask_rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            stamp_rect = fitz.Rect(cx - half, cy - half, cx + half, cy + half)
            page.insert_image(stamp_rect, stream=stamp_bytes, overlay=True)
        stamped_pages.append(page_idx + 1)

    # メタデータ追記（押印が1ページ以上発生した場合のみ）
    if metadata_record and stamped_pages:
        meta = dict(doc.metadata or {})
        existing = (meta.get("keywords") or "").strip()
        entry = f"{META_MARKER} {metadata_record}"
        meta["keywords"] = (existing + " | " + entry) if existing else entry
        doc.set_metadata(meta)

    tmp_path = pdf_path.with_suffix(".tmp.pdf")
    doc.save(tmp_path, garbage=4, deflate=True)
    doc.close()
    # 先に元ファイルを削除してから rename すると、置き換えに失敗したときに
    # 元PDFが期待した場所から消えてしまう。Path.replace は置き換えを
    # ひとつの操作で行うため、失敗しても元PDFは無傷で残る。
    try:
        tmp_path.replace(pdf_path)
    except OSError:
        tmp_path.unlink(missing_ok=True)  # 中途半端な一時ファイルを残さない
        raise

    return stamped_pages
