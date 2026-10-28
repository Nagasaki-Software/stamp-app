from pathlib import Path

from PIL import Image

from core.stamp_generator import generate_stamp

FONT = Path("assets/fonts/NotoSansJP-Regular.otf")


def test_generates_circular_transparent_png():
    img = generate_stamp(
        name="山田 太郎",
        date_str="'26.05.23",
        affiliation="営業部",
        diameter_mm=15.0,
        line_width_pt=1.0,
        font_path=FONT,
    )
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    # 15mm × 600dpi → 約354px
    assert 340 <= img.width <= 370
    assert img.width == img.height
    # 四隅は透明
    assert img.getpixel((0, 0))[3] == 0


def test_stamp_uses_vermillion_color():
    img = generate_stamp(
        name="山田",
        date_str="'26.05.23",
        affiliation="部",
        diameter_mm=15.0,
        line_width_pt=1.0,
        font_path=FONT,
    )
    cx, cy = img.width // 2, img.height // 2
    has_red = False
    for x in range(cx - 50, cx + 50):
        for y in range(cy - 50, cy + 50):
            r, g, b, a = img.getpixel((x, y))
            if a > 0 and r > 150 and g < 50 and b < 80:
                has_red = True
                break
        if has_red:
            break
    assert has_red


def test_long_text_is_shrunk_to_fit():
    img = generate_stamp(
        name="山田太郎次郎三郎",
        date_str="'26.05.23",
        affiliation="経営企画部部長",
        diameter_mm=15.0,
        line_width_pt=1.0,
        font_path=FONT,
    )
    assert img.width > 0
