"""押印を試すためのサンプル書類（架空）を samples/ に作る。

使い方（アプリのフォルダで）:
    .venv\\Scripts\\python.exe scripts\\make_samples.py
"""
from datetime import date
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples"
MARKERS = ROOT / "assets" / "markers"

MM = 72 / 25.4
A4 = fitz.paper_rect("a4")
COMPANY = "サンプル商事株式会社"  # 架空
GRAY = (0.35, 0.35, 0.35)


# 同梱の Noto は CFF 形式で部分埋め込みができず PDF が 1 つ 8MB になるため、
# PDF 標準の日本語フォント（埋め込まない。表示する側のフォントで描かれる）を使う
JP = fitz.Font("japan")


def new_page(doc):
    return doc.new_page(width=A4.width, height=A4.height)


HELV = fitz.Font("helv")


def runs(s):
    """英数字（Helvetica）と日本語（japan）に分ける。japan だと英数字が全角幅で間延びするため。"""
    out = []
    for ch in s:
        kind = "helv" if ord(ch) < 128 else "japan"
        if out and out[-1][0] == kind:
            out[-1][1] += ch
        else:
            out.append([kind, ch])
    return out


def width(s, size):
    return sum((HELV if k == "helv" else JP).text_length(t, fontsize=size) for k, t in runs(s))


def text(page, x_mm, y_mm, s, size=10.5, bold=False, color=(0, 0, 0)):
    x = x_mm * MM
    for kind, t in runs(s):
        # 太字は輪郭も塗って太く見せる
        page.insert_text((x, y_mm * MM), t, fontname=kind, fontsize=size,
                         color=color, fill=color, render_mode=2 if bold else 0,
                         border_width=0.04 if bold else 0)
        x += (HELV if kind == "helv" else JP).text_length(t, fontsize=size)


def box(page, x_mm, y_mm, w_mm, h_mm, width=0.8):
    page.draw_rect(fitz.Rect(x_mm * MM, y_mm * MM, (x_mm + w_mm) * MM, (y_mm + h_mm) * MM),
                   width=width)


def centered(page, x_mm, w_mm, y_mm, s, size=10.5, bold=False):
    tw = width(s, size) / MM
    text(page, x_mm + (w_mm - tw) / 2, y_mm, s, size, bold)


def marker(page, cx_mm, cy_mm, no, size_mm=10):
    r = fitz.Rect((cx_mm - size_mm / 2) * MM, (cy_mm - size_mm / 2) * MM,
                  (cx_mm + size_mm / 2) * MM, (cy_mm + size_mm / 2) * MM)
    page.insert_image(r, filename=str(MARKERS / f"marker_no{no}.png"))


def stamp_row(page, x_mm, y_mm, labels, nos, cell=24):
    """押印欄（見出し＋四角）を横に並べ、四角の中央にマーカーを置く。"""
    for i, (label, no) in enumerate(zip(labels, nos)):
        x = x_mm + i * cell
        box(page, x, y_mm, cell, 7)
        centered(page, x, cell, y_mm + 5, label, 9)
        box(page, x, y_mm + 7, cell, cell)
        if no:
            marker(page, x + cell / 2, y_mm + 7 + cell / 2, no)


def header(page, title, doc_no):
    text(page, 20, 22, f"文書番号：{doc_no}", 9, color=GRAY)
    text(page, 20, 27, f"作成日：{date(2026, 10, 1):%Y年%m月%d日}", 9, color=GRAY)
    centered(page, 0, 210, 45, title, 20, bold=True)
    text(page, 20, 285, f"{COMPANY}（架空の会社です。StampApp の練習用サンプル）", 8, color=GRAY)


def form_rows(page, y_mm, rows, label_w=35, h=11):
    for label, value in rows:
        box(page, 20, y_mm, label_w, h)
        box(page, 20 + label_w, y_mm, 170 - label_w, h)
        text(page, 23, y_mm + 7.3, label, 10)
        text(page, 23 + label_w, y_mm + 7.3, value, 10)
        y_mm += h
    return y_mm


def save(doc, path):
    doc.save(path, garbage=4, deflate=True)


def ringisho():
    """稟議書：担当 No.1 / 課長 No.2 / 部長 No.3。"""
    doc = fitz.open()
    page = new_page(doc)
    header(page, "稟　議　書", "R-2026-0123")
    stamp_row(page, 118, 55, ["部長", "課長", "担当"], [3, 2, 1])
    y = form_rows(page, 95, [
        ("件名", "会議室用プロジェクターの購入について"),
        ("起案者", "営業部　山田 太郎"),
        ("金額", "金 128,000 円（税込）"),
        ("購入先", "見本電機株式会社（架空）"),
    ])
    box(page, 20, y, 170, 70)
    text(page, 23, y + 7, "理由", 10, bold=True)
    for i, line in enumerate([
        "第2会議室のプロジェクターが故障し、修理部品の供給も終了しています。",
        "来客対応や社内会議に支障が出ているため、後継機の購入を申請します。",
        "見積もりは3社から取り、最も安い見本電機株式会社に決めました。",
    ]):
        text(page, 23, y + 16 + i * 7, line, 10)
    save(doc, OUT / "稟議書_サンプル.pdf")


def shuccho():
    """出張報告書（2ページ）：どちらのページにも No.1。"""
    doc = fitz.open()
    page = new_page(doc)
    header(page, "出張報告書", "B-2026-0456")
    stamp_row(page, 142, 55, ["確認", "報告者"], [2, 1])
    y = form_rows(page, 95, [
        ("出張者", "営業部　山田 太郎"),
        ("期間", "2026年9月24日〜9月25日（1泊2日）"),
        ("行き先", "見本市（架空の展示会）"),
        ("目的", "新製品の情報収集と取引先へのあいさつ"),
    ])
    box(page, 20, y, 170, 80)
    text(page, 23, y + 7, "内容（1/2）", 10, bold=True)
    for i, line in enumerate([
        "1日目：展示会を見学し、競合各社の新製品の資料を集めました。",
        "2日目：取引先2社を訪問し、来期の発注予定をうかがいました。",
        "くわしい内容は2ページ目に書きます。",
    ]):
        text(page, 23, y + 16 + i * 7, line, 10)

    page = new_page(doc)
    header(page, "出張報告書（2/2）", "B-2026-0456")
    box(page, 20, 60, 170, 90)
    text(page, 23, 67, "内容（2/2）・所感", 10, bold=True)
    for i, line in enumerate([
        "展示会では、省電力の製品に注目が集まっていました。",
        "当社でも、省電力を前面に出した提案資料を用意するべきだと考えます。",
    ]):
        text(page, 23, 76 + i * 7, line, 10)
    text(page, 120, 172, "以上のとおり報告します。", 10)
    stamp_row(page, 166, 180, ["報告者"], [1])
    save(doc, OUT / "出張報告書_サンプル.pdf")


def kairan():
    """回覧表：5人それぞれに No.1〜No.5。"""
    doc = fitz.open()
    page = new_page(doc)
    header(page, "回　覧", "K-2026-0789")
    y = form_rows(page, 60, [
        ("件名", "年末大掃除の担当区域について"),
        ("回覧元", "総務部"),
    ])
    box(page, 20, y, 170, 40)
    for i, line in enumerate([
        "12月26日（金）の午後に大掃除を行います。担当区域は掲示板を見てください。",
        "読んだら、自分の欄に押印して次の人へ回してください。",
    ]):
        text(page, 23, y + 9 + i * 7, line, 10)
    y += 52
    text(page, 20, y, "回覧先（読んだら押印）", 10, bold=True)
    names = ["佐藤 花子", "鈴木 一郎", "高橋 美咲", "田中 健太", "山田 太郎"]
    stamp_row(page, 25, y + 4, names, [1, 2, 3, 4, 5], cell=32)
    text(page, 20, y + 50, "※ 一人ひとりに別の番号のマーカーを置いています。"
         "StampApp では、自分の番号だけを選んで押します。", 9, color=GRAY)
    save(doc, OUT / "回覧_サンプル.pdf")


def main():
    OUT.mkdir(exist_ok=True)
    ringisho()
    shuccho()
    kairan()
    print("作成しました:", OUT)


if __name__ == "__main__":
    main()
