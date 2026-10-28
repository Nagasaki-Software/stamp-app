# 第三者の著作物について

## リポジトリに同梱しているもの

| 名前 | 場所 | 作者 | ライセンス |
|---|---|---|---|
| Noto Sans JP（Regular / Bold） | `assets/fonts/NotoSansJP-*.otf` | Adobe / Google | SIL Open Font License 1.1（[本文](assets/fonts/OFL.txt)） |
| Noto Serif JP（Regular） | `assets/fonts/NotoSerifJP-Regular.otf` | Adobe / Google | SIL Open Font License 1.1（[本文](assets/fonts/OFL.txt)） |

## リポジトリには含まないもの（`pip install -r requirements.txt` で入る部品）

EXE（PyInstaller でビルドしたもの）には、これらの部品も同梱されます。

| 名前 | ライセンス | 入手先 |
|---|---|---|
| customtkinter | MIT | https://github.com/TomSchimansky/CustomTkinter |
| PyMuPDF | GNU AGPL 3.0（または Artifex 社の商用ライセンス） | https://github.com/pymupdf/PyMuPDF |
| opencv-python-headless | Apache 2.0 | https://github.com/opencv/opencv-python |
| NumPy | BSD-3-Clause ほか | https://github.com/numpy/numpy |
| Pillow | MIT-CMU | https://github.com/python-pillow/Pillow |
| PyInstaller（ビルド時のみ） | GPL 2.0（ブートローダー例外付き） | https://github.com/pyinstaller/pyinstaller |

### PyMuPDF（AGPL 3.0）についての注意

PyMuPDF を同梱した EXE を配布する場合、その EXE 全体には GNU AGPL 3.0 の条件がかかります。
配布する人は、受け取った人がこのリポジトリのソースコードを入手できるようにしてください。
