"""EXE のアイコン（朱色の丸印に「印」）を assets/icon.ico に作る。

使い方（アプリのフォルダで）:
    .venv\\Scripts\\python.exe scripts\\make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"
FONT = ROOT / "assets" / "fonts" / "NotoSerifJP-Regular.otf"
# 32px 以下は明朝体の細い線がにじむため、太いゴシック体にする
FONT_SMALL = ROOT / "assets" / "fonts" / "NotoSansJP-Bold.otf"
RED = (230, 0, 51, 255)  # 印鑑の初期色 #E60033 と同じ
PAPER = (255, 250, 240, 255)
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw(size: int) -> Image.Image:
    # 大きく描いてから縮めると、輪郭がなめらかになる
    s = 1024
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 小さいアイコンほど線を太くしないと、縮めたときに消える
    ring = int(s * (0.10 if size <= 24 else 0.07))
    m = int(s * 0.03)
    d.ellipse((m, m, s - m, s - m), fill=PAPER, outline=RED, width=ring)
    font = ImageFont.truetype(str(FONT_SMALL if size <= 32 else FONT), int(s * 0.62))
    box = d.textbbox((0, 0), "印", font=font, stroke_width=int(s * 0.012))
    x = (s - (box[2] - box[0])) / 2 - box[0]
    y = (s - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), "印", font=font, fill=RED, stroke_width=int(s * 0.012), stroke_fill=RED)
    return img.resize((size, size), Image.LANCZOS)


def main():
    images = [draw(n) for n in SIZES]
    images[-1].save(OUT, sizes=[(n, n) for n in SIZES], append_images=images[:-1])
    print("作成しました:", OUT)


if __name__ == "__main__":
    main()
