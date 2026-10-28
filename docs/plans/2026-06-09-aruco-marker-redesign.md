# ArUcoマーカー方式 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** マーク検出を「丸囲み文字のテンプレート照合」から「ArUcoマーカー検出」へ全面置換し、誤検出を原理的にゼロへ近づける。あわせてマーカー書き出し（PNG/SVG/印刷PDF）を追加し、Acrobat/Word/Excel/印刷スキャンに対応する。

**Architecture:** ページを画像化し `cv2.aruco` で `DICT_4X4_50` のID 0〜4を検出する単一方式。検出結果は従来同形式 `{ページ番号: [(x,y,w,h)]}`（PDFポイント・mediabox座標）で返し、`core/pdf_stamper.py` は無改修。マーカー生成は `core/markers.py` に集約し、検出は `core/mark_detector.py`（ファイル名据え置き）を全面書き換え。

**Tech Stack:** Python 3.13 / OpenCV(opencv-python-headless 4.13, `cv2.aruco`) / PyMuPDF(fitz) / Pillow / customtkinter / pytest / PyInstaller

> **本プロジェクト規約（重要）**
> - **コミットはユーザーの明示指示時のみ実行**。各タスクの「Commit」手順は、指示があるまで実行せず次へ進んでよい。
> - **削除は対象ファイル名と理由を明示してユーザー承認後に実行**（Task 10）。`rm -rf` は使用しない。
> - 作業ディレクトリ（cwd）は `stamp_app/` プロジェクトルート。Pythonは `.venv\Scripts\python.exe` を使用。

---

## ファイル構成（このプランで触る範囲）

**新規作成**
- `core/markers.py` — マーカー定義（ID/ラベル/辞書）＋生成（6×6行列 / PNG / SVG / 印刷PDF / export_all）
- `scripts/generate_markers.py` — 同梱用マーカー一式を `assets/markers/` に生成
- `tests/test_markers.py` — markers の単体テスト

**全面書き換え**
- `core/mark_detector.py` — ArUco検出。`detect_marks(doc, marker_id, progress=None, page_cache=None)` を提供（公開関数名を維持）
- `gui/detection_panel.py` — No.1〜No.5選択（int ID）＋マーカー見本サムネイル
- `tests/test_mark_detector.py` — ArUco検出のテスト（デジタル/スキャン/回転/誤検出ゼロ）

**部分改修**
- `gui/app.py` — サンプル指定/カスタムテンプレ撤去、「マーカー書き出し」ボタン追加、marker_id受け渡し
- `core/settings.py` — `selected_mark` を int(0〜4) に。旧値はロード時に0へ補正
- `build.spec` — 同梱を `assets/marks` → `assets/markers`

**削除（Task 10・承認制）**
- `core/image_finder.py`, `core/text_finder.py`, `gui/sample_picker.py`
- `scripts/generate_mark_templates.py`
- `tests/test_image_finder.py`, `tests/test_text_finder.py`
- `assets/marks/`（旧テンプレ画像5枚）

**パッケージング（Task 11-12）**
- `dist/StampApp/使い方.txt` を更新、EXE再ビルド、配布ZIP作成

---

## Task 1: core/markers.py — 定義と6×6行列

**Files:**
- Create: `core/markers.py`
- Test: `tests/test_markers.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_markers.py` を新規作成：

```python
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
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py -v`
Expected: FAIL（`ModuleNotFoundError: core.markers` または `AttributeError`）

- [ ] **Step 3: 最小実装**

`core/markers.py` を新規作成：

```python
"""ArUcoマーカーの定義と生成（6×6行列 / PNG / SVG / 印刷PDF）。

検出は core/mark_detector.py が担う。本モジュールは「マーカーを作る」責務のみ。
"""
import io
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py -v`
Expected: PASS（3件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/markers.py tests/test_markers.py
git commit -m "feat: add ArUco marker definitions and 6x6 matrix"
```

---

## Task 2: core/markers.py — PNG生成（往復検出）

**Files:**
- Modify: `core/markers.py`
- Test: `tests/test_markers.py`

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_markers.py` の末尾に追記：

```python
def test_render_png_is_grayscale_and_has_label_band():
    img = markers.render_marker_png(0, module_px=10)
    assert img.mode == "L"
    # アスペクト比 横10:縦13（パターン6 + 余白4 + ラベル3 モジュール）
    w, h = img.size
    assert w == 10 * 10
    assert h == 13 * 10


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
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py::test_render_png_roundtrip_detect -v`
Expected: FAIL（`AttributeError: render_marker_png`）

- [ ] **Step 3: 最小実装**

`core/markers.py` の末尾に追記：

```python
def _load_label_font(px: int):
    for fp in ("C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if Path(fp).exists():
            return ImageFont.truetype(fp, px)
    return ImageFont.load_default()


def render_marker_png(marker_id: int, module_px: int = 200, quiet_modules: int = 2) -> Image.Image:
    """白い余白（クワイエットゾーン）と見分け用ラベルを併記したPNG画像を返す。

    画像サイズ（モジュール換算）：横 = 6+2*quiet、縦 = 6+2*quiet+3（ラベル帯）。
    既定の quiet=2 では 横10 : 縦13 モジュール。
    """
    mat = marker_matrix(marker_id)
    pat = _MODULES * module_px
    quiet = quiet_modules * module_px
    label_h = 3 * module_px
    width = pat + 2 * quiet
    height = pat + 2 * quiet + label_h

    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    for r in range(_MODULES):
        for c in range(_MODULES):
            if mat[r, c]:
                x0 = quiet + c * module_px
                y0 = quiet + r * module_px
                draw.rectangle([x0, y0, x0 + module_px - 1, y0 + module_px - 1], fill=0)

    text = MARKER_LABELS[marker_id]
    font = _load_label_font(int(label_h * 0.55))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (width - tw) // 2 - bbox[0]
    ty = pat + 2 * quiet + (label_h - th) // 2 - bbox[1]
    draw.text((tx, ty), text, fill=0, font=font)
    return img
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py -v`
Expected: PASS（5件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/markers.py tests/test_markers.py
git commit -m "feat: render ArUco marker PNG with quiet zone and label"
```

---

## Task 3: core/markers.py — SVG生成

**Files:**
- Modify: `core/markers.py`
- Test: `tests/test_markers.py`

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_markers.py` の末尾に追記：

```python
def test_render_svg_structure():
    svg = markers.render_marker_svg(1, marker_mm=10.0)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert 'viewBox="0 0 10 13"' in svg
    assert 'width="16.667mm"' in svg   # 10*10/6
    assert 'height="21.667mm"' in svg  # 10*13/6
    assert svg.count("<rect") >= 6     # 背景1 + 黒モジュール多数
    assert "No.2" in svg
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py::test_render_svg_structure -v`
Expected: FAIL（`AttributeError: render_marker_svg`）

- [ ] **Step 3: 最小実装**

`core/markers.py` の末尾に追記：

```python
def render_marker_svg(marker_id: int, marker_mm: float = 10.0, quiet_modules: int = 2) -> str:
    """ベクターSVG文字列を返す。パターン本体が marker_mm 四方になるよう実寸指定。"""
    mat = marker_matrix(marker_id)
    vb_w = _MODULES + 2 * quiet_modules          # 既定10
    vb_h = vb_w + 3                              # ラベル帯3モジュール → 既定13
    mm_per_module = marker_mm / _MODULES
    width_mm = vb_w * mm_per_module
    height_mm = vb_h * mm_per_module

    rects = []
    for r in range(_MODULES):
        for c in range(_MODULES):
            if mat[r, c]:
                rects.append(
                    f'<rect x="{quiet_modules + c}" y="{quiet_modules + r}" '
                    f'width="1" height="1" fill="#000"/>'
                )
    label = MARKER_LABELS[marker_id]
    label_y = vb_w + 2.1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_mm:.3f}mm" height="{height_mm:.3f}mm" '
        f'viewBox="0 0 {vb_w} {vb_h}">'
        f'<rect x="0" y="0" width="{vb_w}" height="{vb_h}" fill="#fff"/>'
        + "".join(rects)
        + f'<text x="{vb_w / 2}" y="{label_y}" font-size="2" text-anchor="middle" '
          f'font-family="sans-serif" fill="#000">{label}</text>'
        + "</svg>"
    )
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py -v`
Expected: PASS（6件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/markers.py tests/test_markers.py
git commit -m "feat: render ArUco marker as vector SVG"
```

---

## Task 4: core/markers.py — 印刷PDFと export_all

**Files:**
- Modify: `core/markers.py`
- Test: `tests/test_markers.py`

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_markers.py` の末尾に追記：

```python
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
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py::test_export_all_writes_files -v`
Expected: FAIL（`AttributeError: export_all`）

- [ ] **Step 3: 最小実装**

`core/markers.py` の末尾に追記：

```python
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
    tw_mm = marker_mm * 10 / 6   # PNG横（パターン+余白）
    th_mm = marker_mm * 13 / 6   # PNG縦（+ラベル帯）
    tw, th = tw_mm * mm, th_mm * mm
    x_left, y_top = 60, 100
    col_gap, row_gap = 240, th + 36
    for i, mid in enumerate(MARKER_IDS):
        col, row = i % 2, i // 2
        x = x_left + col * col_gap
        y = y_top + row * row_gap
        png = render_marker_png(mid, module_px=60)
        buf = io.BytesIO()
        png.save(buf, format="PNG")
        page.insert_image(fitz.Rect(x, y, x + tw, y + th), stream=buf.getvalue())
    doc.save(out_path)
    doc.close()


def export_all(out_dir) -> list[Path]:
    """PNG×5・SVG×5・印刷PDF×1 を out_dir に書き出し、生成パス一覧を返す。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_markers.py -v`
Expected: PASS（7件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/markers.py tests/test_markers.py
git commit -m "feat: add printable PDF sheet and export_all for markers"
```

---

## Task 5: core/mark_detector.py — ArUco検出へ全面書き換え

**Files:**
- Rewrite: `core/mark_detector.py`
- Rewrite: `tests/test_mark_detector.py`

- [ ] **Step 1: テストを全面書き換え**

`tests/test_mark_detector.py` を以下で**全置換**：

```python
import io
from pathlib import Path

import cv2
import fitz
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
    pages = [doc.new_page(width=595, height=842) for _ in range(n_pages)]
    for pidx, mid, x, y, s in placements:
        # PNGアスペクト比 横10:縦13
        pages[pidx].insert_image(
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
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_mark_detector.py -v`
Expected: FAIL（旧 `detect_marks` は `marker_id` 非対応／`MARK_CHARS` 参照などで失敗）

- [ ] **Step 3: 検出モジュールを全面書き換え**

`core/mark_detector.py` を以下で**全置換**：

```python
"""ArUcoマーカー検出。

ページを画像化し、選択ID（0〜4）のマーカー位置のみを返す。デジタル挿入PDFでも
スキャン画像PDFでも同一手順。回転ページ（/Rotate）は mediabox 座標へ変換する。
誤り検出符号により無関係な模様は棄却され、誤検出は原理的にゼロに近い。
"""
from typing import Callable, Optional

import cv2
import fitz
import numpy as np

from core.markers import MARKER_IDS, get_dictionary

RENDER_DPI = 250


def _build_detector() -> "cv2.aruco.ArucoDetector":
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
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_mark_detector.py -v`
Expected: PASS（5件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/mark_detector.py tests/test_mark_detector.py
git commit -m "feat: replace template matching with ArUco marker detection"
```

---

## Task 6: core/settings.py — selected_mark を int 化

**Files:**
- Modify: `core/settings.py:5-17`（DEFAULT_SETTINGS）, `core/settings.py:24-35`（load_settings）
- Test: `tests/test_settings.py`（新規）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_settings.py` を新規作成：

```python
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
```

- [ ] **Step 2: テスト失敗を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
Expected: FAIL（`selected_mark` が `"㊎"` のまま、または既定が文字列）

- [ ] **Step 3: 実装**

`core/settings.py` の DEFAULT_SETTINGS 内、該当行を変更：

```python
    "selected_mark": 0,
```
（変更前：`"selected_mark": "㊎",`）

さらに `load_settings` の `merged.update(...)` の直後（`return merged` の前）に2行追加：

```python
        if merged.get("selected_mark") not in (0, 1, 2, 3, 4):
            merged["selected_mark"] = 0
```

- [ ] **Step 4: テスト成功を確認**

Run: `.venv\Scripts\python.exe -m pytest tests/test_settings.py -v`
Expected: PASS（3件）

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add core/settings.py tests/test_settings.py
git commit -m "feat: store selected marker as integer id with legacy coercion"
```

---

## Task 7: gui/detection_panel.py — No.1〜No.5 選択へ

**Files:**
- Rewrite: `gui/detection_panel.py`

> GUIはpytestで自動検証しにくいため、import確認と手動確認で代える。

- [ ] **Step 1: 全面書き換え**

`gui/detection_panel.py` を以下で**全置換**：

```python
"""対象マーカー（No.1〜No.5）の選択と、各ページの検出結果サマリ表示。"""
import customtkinter as ctk

from core.markers import MARKER_IDS, MARKER_LABELS, render_marker_png

try:
    from PIL import Image  # noqa: F401  (CTkImage 用に存在確認)
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


class DetectionPanel(ctk.CTkFrame):
    def __init__(self, master, on_mark_change=None, initial_mark: int = 0):
        super().__init__(master)
        self._on_mark_change = on_mark_change or (lambda _i: None)

        ctk.CTkLabel(self, text="対象マーカー", anchor="w").pack(
            fill="x", padx=6, pady=(6, 0)
        )
        grid = ctk.CTkFrame(self)
        grid.pack(fill="x", padx=6, pady=2)

        if initial_mark not in MARKER_IDS:
            initial_mark = MARKER_IDS[0]
        self.mark_var = ctk.IntVar(value=initial_mark)

        self._thumbs = []  # GC防止のため参照を保持
        for col, mid in enumerate(MARKER_IDS):
            grid.columnconfigure(col, weight=1, uniform="markers")
            if _HAS_PIL:
                pil = render_marker_png(mid, module_px=8).convert("RGB")
                thumb = ctk.CTkImage(light_image=pil, dark_image=pil, size=(46, 60))
                self._thumbs.append(thumb)
                ctk.CTkLabel(grid, text="", image=thumb).grid(
                    row=0, column=col, padx=2, pady=(2, 0)
                )
            ctk.CTkRadioButton(
                grid,
                text=MARKER_LABELS[mid],
                variable=self.mark_var,
                value=mid,
                command=self._fire,
                width=10,
            ).grid(row=1, column=col, padx=2, pady=2)

        ctk.CTkLabel(self, text="検出結果", anchor="w").pack(
            fill="x", padx=6, pady=(8, 0)
        )
        self.result_label = ctk.CTkLabel(
            self, text="（PDF未読込）", anchor="w", justify="left"
        )
        self.result_label.pack(fill="x", padx=6, pady=2)

    def _fire(self):
        self._on_mark_change(self.mark_var.get())

    def selected_mark(self) -> int:
        return int(self.mark_var.get())

    def set_detection_summary(self, marker_id: int, detections: dict):
        label = MARKER_LABELS.get(marker_id, str(marker_id))
        pages = [str(i + 1) for i, rs in detections.items() if rs]
        if not pages:
            self.result_label.configure(text=f"{label} を検出: 0ページ")
        else:
            self.result_label.configure(
                text=f"{label} を検出: {len(pages)}ページ\n(P{','.join(pages)})"
            )
```

- [ ] **Step 2: import確認**

Run: `.venv\Scripts\python.exe -c "import gui.detection_panel as d; print('OK', d.DetectionPanel)"`
Expected: `OK <class 'gui.detection_panel.DetectionPanel'>`（エラーなし）

- [ ] **Step 3: Commit（指示時のみ）**

```bash
git add gui/detection_panel.py
git commit -m "feat: marker selection panel with No.1-No.5 and thumbnails"
```

---

## Task 8: gui/app.py — サンプル指定撤去・書き出しボタン追加・marker_id配線

**Files:**
- Modify: `gui/app.py`（import / ボタン / 状態 / 各ハンドラ）

- [ ] **Step 1: import と定数を修正**

`from gui.sample_picker import SamplePickerWindow` の行を削除し、`from core.pdf_stamper import stamp_pdf_in_place` の下に追加：

```python
from core.markers import export_all
```

`MARKS_DIR = ASSETS / "marks"` の行を削除（検出はテンプレ不要のため）。

- [ ] **Step 2: DetectionPanel初期値を int に**

`gui/app.py` の DetectionPanel 生成箇所を変更：

変更前：
```python
        self.detection_panel = DetectionPanel(
            self.left,
            on_mark_change=self._on_mark_change,
            initial_mark=self._settings.get("selected_mark", "◰"),
        )
```
変更後：
```python
        self.detection_panel = DetectionPanel(
            self.left,
            on_mark_change=self._on_mark_change,
            initial_mark=int(self._settings.get("selected_mark", 0)),
        )
```

- [ ] **Step 3: ボタンを差し替え（サンプル指定→マーカー書き出し）**

変更前：
```python
        self.sample_btn = ctk.CTkButton(
            button_bar,
            text="サンプルマーク指定",
            command=self._on_pick_sample,
            state="disabled",
        )
        self.sample_btn.pack(side="left", padx=4)
```
変更後：
```python
        self.export_btn = ctk.CTkButton(
            button_bar,
            text="マーカー書き出し",
            command=self._on_export_markers,
        )
        self.export_btn.pack(side="left", padx=4)
```

- [ ] **Step 4: 状態変数からカスタムテンプレを除去**

`self._custom_templates: dict[str, np.ndarray] = {}  # ユーザー抽出テンプレート` の行を削除。

- [ ] **Step 5: _on_open のサンプル関連を除去**

変更前：
```python
        self._page_cache = {}  # 新規PDF：キャッシュ初期化
        self._custom_templates = {}  # 新規PDF：カスタムテンプレートをリセット
        self.sample_btn.configure(state="normal")
        self._run_detection_async()
```
変更後：
```python
        self._page_cache = {}  # 新規PDF：キャッシュ初期化
        self._run_detection_async()
```

- [ ] **Step 6: _run_detection_async の検出呼び出しを修正**

変更前：
```python
        mark = self.detection_panel.selected_mark()
```
は維持（戻り値が int になる）。worker内の `detect_marks(...)` を変更：

変更前：
```python
                    results = detect_marks(
                        doc,
                        mark,
                        template_dir=MARKS_DIR,
                        progress=self._post_progress,
                        page_cache=self._page_cache,
                        custom_templates=self._custom_templates,
                    )
```
変更後：
```python
                    results = detect_marks(
                        doc,
                        mark,
                        progress=self._post_progress,
                        page_cache=self._page_cache,
                    )
```

- [ ] **Step 7: サンプル系ハンドラを書き出しハンドラへ置換**

`_on_pick_sample` と `_on_template_picked` の2メソッド（定義全体）を削除し、代わりに以下を追加：

```python
    def _on_export_markers(self):
        if self._busy:
            messagebox.showinfo("StampApp", "現在処理中です。完了後に再度お試しください。")
            return
        folder = filedialog.askdirectory(title="マーカーの保存先フォルダを選択")
        if not folder:
            return
        try:
            written = export_all(Path(folder))
        except Exception as e:
            messagebox.showerror("StampApp", f"書き出しに失敗しました：\n{e}")
            return
        messagebox.showinfo(
            "StampApp",
            f"マーカーを書き出しました（PNG5・SVG5・印刷PDF1）。\n保存先：{folder}\n\n"
            "Acrobat/Word/Excelに『挿入→画像』で貼り付けてください（約10mm・縦横比固定）。",
        )
```

- [ ] **Step 8: 不要importの掃除（任意）**

`import numpy as np` が他で未使用なら削除してよい（`_custom_templates` 削除後に未使用化した場合）。使用が残るなら残す。

- [ ] **Step 9: 起動スモークテスト（手動）**

Run: `.venv\Scripts\python.exe main.py`
Expected: ウィンドウが開く。対象マーカーに No.1〜No.5 とマーカー見本が表示。「マーカー書き出し」ボタンがある。「サンプルマーク指定」ボタンが無い。エラーダイアログが出ない。確認したらウィンドウを閉じる。

- [ ] **Step 10: Commit（指示時のみ）**

```bash
git add gui/app.py
git commit -m "feat: wire marker_id detection and marker export button into app"
```

---

## Task 9: scripts/generate_markers.py と同梱・build.spec

**Files:**
- Create: `scripts/generate_markers.py`
- Create（生成物）: `assets/markers/`（PNG5・SVG5・PDF1）
- Modify: `build.spec:16-19`

- [ ] **Step 1: 生成スクリプトを作成**

`scripts/generate_markers.py` を新規作成：

```python
"""同梱用ArUcoマーカー一式（PNG5・SVG5・印刷PDF1）を assets/markers/ に生成する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.markers import export_all  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "markers"

if __name__ == "__main__":
    for p in export_all(OUT):
        print("wrote", p)
```

- [ ] **Step 2: 同梱マーカーを生成**

Run: `.venv\Scripts\python.exe scripts\generate_markers.py`
Expected: `wrote .../assets/markers/marker_no1.png` 〜 `markers_print.pdf` が11行表示。

- [ ] **Step 3: 生成物を目視確認（任意）**

`assets/markers/markers_print.pdf` を開き、5種マーカーが「No.1〜No.5」付きで表示されることを確認。

- [ ] **Step 4: build.spec の同梱対象を変更**

変更前：
```python
datas = list(ctk_datas) + [
    ("assets/fonts", "assets/fonts"),
    ("assets/marks", "assets/marks"),
]
```
変更後：
```python
datas = list(ctk_datas) + [
    ("assets/fonts", "assets/fonts"),
    ("assets/markers", "assets/markers"),
]
```

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git add scripts/generate_markers.py assets/markers build.spec
git commit -m "build: generate and bundle ArUco marker assets"
```

---

## Task 10: 旧コードの削除（要ユーザー承認）

**Files（削除対象と理由）:**
- `core/image_finder.py` — テンプレートマッチング一式。ArUcoで置換され未参照
- `core/text_finder.py` — テキスト検索。ArUco一本化で未参照
- `gui/sample_picker.py` — サンプルマーク指定。ArUcoで不要
- `scripts/generate_mark_templates.py` — 旧テンプレ生成。generate_markers.py で置換
- `tests/test_image_finder.py` / `tests/test_text_finder.py` — 上記モジュールのテスト
- `assets/marks/`（mark_*.png 5枚）— 旧テンプレ画像。assets/markers/ で置換

- [ ] **Step 1: 全テストが旧ファイルに依存しないことを確認**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: ここまでの新テストがPASS。旧 `tests/test_image_finder.py`・`tests/test_text_finder.py` は次のStepで削除予定（このStepでは失敗していても可。ただし新規テストが緑であることを確認）。

- [ ] **Step 2: 参照が無いことを確認**

Run: `.venv\Scripts\python.exe -c "import gui.app, gui.detection_panel, core.mark_detector; print('imports OK')"`
Expected: `imports OK`（旧モジュール未参照で起動経路が成立）

- [ ] **Step 3: ユーザー承認を得てから削除**

> 実行者へ：上記6グループの削除可否をユーザーに確認すること（理由は本タスク冒頭に記載）。承認後のみ実行。`rm -rf` は使わない。

```bash
git rm core/image_finder.py core/text_finder.py gui/sample_picker.py \
       scripts/generate_mark_templates.py \
       tests/test_image_finder.py tests/test_text_finder.py
git rm -r assets/marks
```

- [ ] **Step 4: 全テスト再実行**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: 全PASS（markers / mark_detector / settings ＋ 既存の stamp_generator・logger・pdf_stamper 系）。

- [ ] **Step 5: Commit（指示時のみ）**

```bash
git commit -m "chore: remove obsolete template-matching detection code"
```

---

## Task 11: EXE再ビルドと 使い方.txt 更新

**Files:**
- 生成: `dist/StampApp/`（PyInstaller出力）
- 作成/更新: `dist/StampApp/使い方.txt`

- [ ] **Step 1: 起動中のEXEを終了（あれば）**

Run: `taskkill //F //IM StampApp.exe`
Expected: 終了する。起動していなければ「見つかりません」と出るが問題なし。

- [ ] **Step 2: EXEをビルド**

> `--noconfirm` で dist を上書き、`--clean` でビルドキャッシュを掃除する（`rm -rf` は使わない）。

Run: `.venv\Scripts\python.exe -m PyInstaller build.spec --clean --noconfirm`
Expected: `dist\StampApp\StampApp.exe` が生成され、`_internal\assets\markers\` が含まれる。

- [ ] **Step 3: 使い方.txt を作成（上書き確認の上）**

> `dist/StampApp/使い方.txt` が既存の場合は上書きになる。ユーザーに上書き可否を確認してから書く。

`dist/StampApp/使い方.txt` に以下を書き込む：

```
StampApp 使い方
=====================================

■ これは何をするアプリ？
PDF上に置いた「ArUcoマーカー（白黒の四角い目印）」を自動で見つけ、その位置に
電子印鑑（朱色の丸印）を貼り付けます。Acrobat・Word・Excelで作ったPDFでも、
紙に印刷してスキャンしたPDFでも対応します。

■ 手順（はじめに一度だけ）
1) アプリを起動し、「マーカー書き出し」を押す
2) 保存先フォルダを選ぶと、次が書き出されます
   - marker_no1.png 〜 marker_no5.png（画像。Acrobat/Word/Excelに貼る用）
   - marker_no1.svg 〜 marker_no5.svg（高精細ベクター。Office2016以降）
   - markers_print.pdf（印刷用シート。印刷→スキャン運用の見本）

■ マーカーの貼り方
・Acrobat：編集 → 画像を追加 → marker_noX.png を選び、約10mm四方で配置
・Word/Excel：挿入 → 画像 → このデバイス → marker_noX.png（またはSVG）
  → サイズを約10mm四方に。縦横比は固定（斜めにしない）
・印刷→スキャン：markers_print.pdf を印刷し、必要箇所に貼る/印字してスキャン
・画質を確実に保ちたい場合：ファイル → オプション → 詳細設定 →
  「ファイル内のイメージを圧縮しない」にチェック

■ 押印のしかた
1) 「PDFを開く」でPDFを選ぶ（自動でマーカーを検出します）
2) 「対象マーカー」で No.1〜No.5 から、自分の使うマーカーを選ぶ
3) 名前・所属・サイズなどを設定（日付は実行時の日付が自動で入ります）
4) 「押印実行」を押す → 元のPDFに上書き保存されます

■ ログ
・押印履歴は Documents\StampApp\stamp_log.csv に記録されます
・「ログを開く」で表示、「ログ検証」で改ざんの有無を確認できます

■ 注意
・以前の丸囲み文字（㊎ など）の目印は使えません。上記のマーカーに貼り替えてください
・マーカーが小さすぎる・斜め・つぶれていると認識しにくくなります（約10mm推奨）
```

- [ ] **Step 4: EXEで動作確認（手動）**

`dist\StampApp\StampApp.exe` を起動 →「マーカー書き出し」で出力 → そのPNGを貼ったPDF（またはmarkers_print.pdfを印刷スキャンしたPDF）を開き、対象マーカーを選んで検出件数を確認 →「押印実行」。
Expected: 正しい位置に押印され、余白への誤押印が無い。

- [ ] **Step 5: Commit（指示時のみ、使い方.txtを版管理する場合）**

> `dist/` は通常ビルド成果物。版管理対象かは `.gitignore` を確認し、対象外なら本Stepは省略。

---

## Task 12: 配布ZIPの作成

**Files:**
- 作成: `StampApp.zip`（`dist/StampApp/` 一式）

- [ ] **Step 1: ZIPを作成（上書き確認の上）**

> 既存の `StampApp.zip` がある場合は上書きになる。ユーザーに確認してから実行。

Run:
```bash
.venv\Scripts\python.exe -c "import shutil; shutil.make_archive('StampApp','zip',root_dir='dist',base_dir='StampApp'); print('done')"
```
Expected: プロジェクト直下に `StampApp.zip` が生成（`StampApp/` 配下に exe・_internal・使い方.txt を含む）。

- [ ] **Step 2: 中身を確認**

Run:
```bash
.venv\Scripts\python.exe -c "import zipfile; z=zipfile.ZipFile('StampApp.zip'); ns=z.namelist(); print('使い方.txt' in [n.split('/')[-1] for n in ns]); print(any('assets/markers' in n for n in ns)); print(len(ns),'entries')"
```
Expected: `True`（使い方.txt 同梱） / `True`（markers 同梱） / エントリ数表示。

- [ ] **Step 3: 完了報告**

ユーザーへ：実機（スキャンPDF・回転ページ・混在PDF）でマーカー検出と押印精度（誤検出ゼロ）を確認してもらう。

---

## 自己レビュー結果（記入済み）

- **仕様カバレッジ**：spec §2方針=Task5、§3マーカー仕様=Task1-3、§4書き出し(PNG/SVG/印刷PDF/Word・Excel手順)=Task4・8・11、§5検出フロー=Task5、§6押印=無改修(pdf_stamper)、§7 UI=Task7-8、§8構成差分=Task1/5/9/10、§9設定=Task6・ログ/メタデータ=無改修、§10エラー処理=Task5(ID外Value Error・回転変換)、§11テスト=Task1-5、§12後方互換=Task6(旧値補正)・Task11使い方.txt注意書き。→ 欠落なし。
- **プレースホルダ**：TBD/TODO無し。各コードステップに実体コードあり。
- **型・名称整合**：`detect_marks(doc, marker_id, progress, page_cache)`／`selected_mark()->int`／`MARKER_IDS`・`MARKER_LABELS`・`get_dictionary`・`marker_matrix`・`render_marker_png`・`render_marker_svg`・`build_printable_pdf`・`export_all` は全タスクで一致。`detection_panel`の import 元を `core.markers` に統一済み（旧 `MARK_CHARS` 参照は廃止）。
```

