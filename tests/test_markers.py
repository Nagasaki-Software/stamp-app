import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from core import markers


def test_marker_ids_and_labels():
    assert markers.MARKER_IDS == [0, 1, 2, 3, 4]
    assert set(markers.MARKER_LABELS) == set(markers.MARKER_IDS)
    assert markers.MARKER_LABELS[0] == "No.1"


def test_marker_matrix_shape_and_binary():
    m = markers.marker_matrix(0)
    assert m.shape == (6, 6)
    assert set(np.unique(m).tolist()) <= {0, 1}
    # ArUcoは外周1モジュールが黒枠
    assert m[0, 0] == 1 and m[0, 5] == 1 and m[5, 0] == 1


def test_marker_matrix_rejects_unknown_id():
    import pytest
    with pytest.raises(ValueError):
        markers.marker_matrix(9)


def test_render_png_is_square_grayscale_no_label():
    img = markers.render_marker_png(0, module_px=10)
    assert img.mode == "L"
    # 正方形（パターン6 + 余白4 = 10 モジュール）。番号ラベルは付けない。
    w, h = img.size
    assert w == 10 * 10
    assert h == 10 * 10


def test_render_png_roundtrip_detect():
    """生成PNGをArUco検出して同じIDが取れること。"""
    img = markers.render_marker_png(2, module_px=40)
    arr = np.array(img)
    det = cv2.aruco.ArucoDetector(
        markers.get_dictionary(), cv2.aruco.DetectorParameters()
    )
    corners, ids, _ = det.detectMarkers(arr)
    assert ids is not None
    assert 2 in ids.ravel().tolist()


def test_render_svg_structure():
    svg = markers.render_marker_svg(1, marker_mm=10.0)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert 'viewBox="0 0 10 10"' in svg
    assert 'width="16.667mm"' in svg    # 10*10/6（パターン+余白で正方形）
    assert 'height="16.667mm"' in svg
    assert svg.count("<rect") >= 6      # 背景1 + 黒モジュール多数
    assert "<text" not in svg           # 番号ラベルなし


def test_export_all_writes_files(tmp_path):
    written = markers.export_all(tmp_path)
    pngs = sorted(tmp_path.glob("marker_*.png"))
    svgs = sorted(tmp_path.glob("marker_*.svg"))
    assert len(pngs) == 5
    assert len(svgs) == 5
    assert (tmp_path / "markers_print.pdf").exists()
    assert len(written) == 11  # 5png + 5svg + 1pdf

    # 書き出したPNGを再検出して往復一致
    det = cv2.aruco.ArucoDetector(
        markers.get_dictionary(), cv2.aruco.DetectorParameters()
    )
    arr = np.array(Image.open(pngs[0]).convert("L"))
    _, ids, _ = det.detectMarkers(arr)
    assert ids is not None
