"""ArUcoマーカー検出。

ページを画像化し、選択ID（0〜4）のマーカー位置のみを返す。デジタル挿入PDFでも
スキャン画像PDFでも同一手順。回転ページ（/Rotate）は mediabox 座標へ変換する。
誤り検出符号により無関係な模様は棄却され、誤検出は原理的にゼロに近い。
"""
from typing import Callable, Optional

import cv2
import pymupdf as fitz
import numpy as np

from core.markers import MARKER_IDS, get_dictionary

RENDER_DPI = 250


def _build_detector():
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(get_dictionary(), params)


def _render_gray(page: fitz.Page, dpi: int, page_cache: Optional[dict], idx: int) -> np.ndarray:
    if page_cache is not None and idx in page_cache:
        return page_cache[idx]
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n >= 3:
        gray = cv2.cvtColor(np.ascontiguousarray(img[:, :, :3]), cv2.COLOR_RGB2GRAY)
    else:
        gray = np.ascontiguousarray(img[:, :, 0])
    if page_cache is not None:
        page_cache[idx] = gray
    return gray


def detect_marks(
    doc: fitz.Document,
    marker_id: int,
    progress: Optional[Callable[[str, float], None]] = None,
    page_cache: Optional[dict] = None,
) -> dict[int, list[tuple[float, float, float, float]]]:
    """PDF中の指定ArUco ID を検出し、ページ毎の (x, y, w, h)[PDFポイント] を返す。"""
    if marker_id not in MARKER_IDS:
        raise ValueError(f"未対応のマーカーID: {marker_id}")

    detector = _build_detector()
    scale = 72 / RENDER_DPI
    results: dict[int, list[tuple[float, float, float, float]]] = {}
    total = max(1, doc.page_count)

    for i, page in enumerate(doc):
        if progress:
            progress(f"検出中… {i + 1}/{total}", (i + 0.5) / total)
        gray = _render_gray(page, RENDER_DPI, page_cache, i)
        corners, ids, _ = detector.detectMarkers(gray)
        rects: list[tuple[float, float, float, float]] = []
        if ids is not None:
            for quad, mid in zip(corners, ids.ravel()):
                if int(mid) != marker_id:
                    continue
                pts = quad.reshape(-1, 2)
                x0, y0 = float(pts[:, 0].min()), float(pts[:, 1].min())
                x1, y1 = float(pts[:, 0].max()), float(pts[:, 1].max())
                rx, ry = x0 * scale, y0 * scale
                rw, rh = (x1 - x0) * scale, (y1 - y0) * scale
                if page.rotation:
                    # get_pixmap は回転後の見た目で描画するが、insert_image/draw_rect は
                    # mediabox（未回転）座標で配置するため derotation_matrix で変換する。
                    r = fitz.Rect(rx, ry, rx + rw, ry + rh) * page.derotation_matrix
                    xx0, xx1 = sorted((r.x0, r.x1))
                    yy0, yy1 = sorted((r.y0, r.y1))
                    rects.append((xx0, yy0, xx1 - xx0, yy1 - yy0))
                else:
                    rects.append((rx, ry, rw, rh))
        results[i] = rects

    if progress:
        progress("完了", 1.0)
    return results
