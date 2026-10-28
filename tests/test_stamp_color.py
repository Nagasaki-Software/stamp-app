from pathlib import Path

import numpy as np

from core.font_registry import list_fonts
from core.stamp_generator import VERMILLION, _parse_color, generate_stamp


def _font_path() -> Path:
    fonts = list_fonts(Path("assets/fonts"))
    return next(iter(fonts.values()))


def _ink_channel_means(img):
    """不透明画素（インク）のR,G,B平均を返す。"""
    arr = np.array(img).astype(float)
    ink = arr[arr[:, :, 3] > 10]
    return ink[:, 0].mean(), ink[:, 1].mean(), ink[:, 2].mean()


def test_parse_color_variants():
    assert _parse_color("#0000FF") == (0, 0, 255, 255)
    assert _parse_color("0000ff") == (0, 0, 255, 255)
    assert _parse_color((10, 20, 30)) == (10, 20, 30, 255)
    assert _parse_color("garbage") == VERMILLION


def test_default_color_is_reddish():
    r, g, b = _ink_channel_means(
        generate_stamp("山田", "'26.06.10", "営業部", 15.0, 1.0, _font_path())
    )
    assert r > b  # 既定は朱色（赤 > 青）


def test_custom_color_changes_ink_to_blue():
    r, g, b = _ink_channel_means(
        generate_stamp(
            "山田", "'26.06.10", "営業部", 15.0, 1.0, _font_path(), color="#0000FF"
        )
    )
    assert b > r  # 青指定で 青 > 赤
