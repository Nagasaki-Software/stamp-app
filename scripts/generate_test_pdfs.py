"""動作確認用テストPDFを生成する。

出力:
  tests/samples/test_acrobat.pdf   テキスト埋め込み版（Acrobat製想定）
  tests/samples/test_scanned.pdf   画像のみ版（スキャンPDF想定）

各PDFは5ページ、各ページに 5種マークの中からランダムに 0〜4 個を散布。
"""
import io
import random
import sys
from pathlib import Path

# Windows コンソール（cp932）でマーク文字を出力するため stdout を UTF-8 に
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

MARKS = ["㊎", "㊗", "㊦", "㊨", "㊀"]
PAGE_W, PAGE_H = 595, 842  # A4 pt
N_PAGES = 5
SEED = 20260522  # 再現性のため固定

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "samples"


def _find_symbol_font() -> str:
    for fp in (
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/seguisym.ttf",
    ):
        if Path(fp).exists():
            return fp
    raise RuntimeError("マーク描画可能なフォントが見つかりません")


def _random_marks_for_page(rng: random.Random) -> list[tuple[str, float, float]]:
    """1ページに散布するマーク（文字、x、y）。"""
    n = rng.randint(0, 4)
    placed: list[tuple[str, float, float]] = []
    for _ in range(n):
        ch = rng.choice(MARKS)
        # マークが端に寄りすぎないよう内側にマージン
        x = rng.uniform(60, PAGE_W - 60)
        y = rng.uniform(80, PAGE_H - 80)
        placed.append((ch, x, y))
    return placed


def _print_summary(label: str, mark_layout: list[list[tuple[str, float, float]]]):
    print(f"--- {label} ---")
    for i, items in enumerate(mark_layout, 1):
        if not items:
            print(f"  Page {i}: なし")
        else:
            summary = ", ".join(f"{ch}@({int(x)},{int(y)})" for ch, x, y in items)
            print(f"  Page {i}: {summary}")


def build_acrobat_pdf(path: Path, layout: list[list[tuple[str, float, float]]]):
    """テキストレイヤとしてマークを埋め込んだPDF。"""
    doc = fitz.open()
    for items in layout:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        # 見出し
        page.insert_text((40, 40), f"Sample (Acrobat-style)", fontsize=10)
        for ch, x, y in items:
            html = f'<span style="font-size: 16pt;">{ch}</span>'
            page.insert_htmlbox(fitz.Rect(x - 20, y - 14, x + 20, y + 14), html)
    doc.save(path, garbage=4, deflate=True)
    doc.close()


def build_scanned_pdf(path: Path, layout: list[list[tuple[str, float, float]]]):
    """画像レイヤのみのPDF（スキャン想定）。テキスト検索に引っかからない。"""
    font_path = _find_symbol_font()
    # 150dpi で A4 画像生成
    px_w, px_h = int(PAGE_W / 72 * 150), int(PAGE_H / 72 * 150)
    scale = 150 / 72
    font = ImageFont.truetype(font_path, 36)
    doc = fitz.open()
    for items in layout:
        img = Image.new("RGB", (px_w, px_h), "white")
        draw = ImageDraw.Draw(img)
        draw.text((80, 60), "Sample (Scanned-style)", fill="black", font=ImageFont.truetype(font_path, 22))
        for ch, x, y in items:
            px = int(x * scale)
            py = int(y * scale)
            bbox = font.getbbox(ch)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((px - tw / 2 - bbox[0], py - th / 2 - bbox[1]), ch, fill="black", font=font)
        tmp_png = path.with_suffix(f".tmp_p.png")
        img.save(tmp_png)
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_image(page.rect, filename=str(tmp_png))
        tmp_png.unlink()
    doc.save(path, garbage=4, deflate=True)
    doc.close()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    layout = [_random_marks_for_page(rng) for _ in range(N_PAGES)]

    _print_summary("マーク配置（両PDF共通）", layout)

    acrobat = OUT_DIR / "test_acrobat.pdf"
    scanned = OUT_DIR / "test_scanned.pdf"
    build_acrobat_pdf(acrobat, layout)
    build_scanned_pdf(scanned, layout)
    print()
    print(f"saved: {acrobat}")
    print(f"saved: {scanned}")


if __name__ == "__main__":
    main()
