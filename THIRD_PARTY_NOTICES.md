# 第三者の著作物について

## リポジトリに同梱しているもの

| 名前 | 場所 | 作者 | ライセンス |
|---|---|---|---|
| Noto Sans JP（Regular / Bold） | `assets/fonts/NotoSansJP-*.otf` | Adobe / Google | SIL Open Font License 1.1（[本文](assets/fonts/OFL.txt)） |
| Noto Serif JP（Regular） | `assets/fonts/NotoSerifJP-Regular.otf` | Adobe / Google | SIL Open Font License 1.1（[本文](assets/fonts/OFL.txt)） |

## EXE に同梱されるもの

PyInstaller でビルドした EXE（Releases の zip）には、次の部品も入っています。
ライセンスの本文は、EXE のフォルダの **`StampApp\_internal\licenses\`** に入っています。

| 名前 | ライセンス | 本文の場所（licenses の中） | 入手先 |
|---|---|---|---|
| Python | PSF License ほか | `python/LICENSE.txt` | https://www.python.org/ |
| bzip2（Python に同梱） | bzip2 License | `python/LICENSE.txt` | https://sourceware.org/bzip2/ |
| Tcl/Tk（Python に同梱） | Tcl/Tk License（BSD 系） | `python/LICENSE.txt` | https://www.tcl-lang.org/ |
| OpenSSL（Python に同梱） | Apache License 2.0 | `openssl/LICENSE.txt` | https://www.openssl.org/ |
| libffi（Python に同梱） | MIT | `libffi/LICENSE` | https://github.com/libffi/libffi |
| mpdecimal（Python に同梱） | BSD-2-Clause | `mpdecimal/LICENSE.txt` | https://www.bytereef.org/mpdecimal/ |
| Expat（Python に同梱） | MIT | `expat/COPYING` | https://github.com/libexpat/libexpat |
| customtkinter | MIT | `customtkinter/` | https://github.com/TomSchimansky/CustomTkinter |
| darkdetect | BSD-3-Clause | `darkdetect/` | https://github.com/albertosottile/darkdetect |
| packaging | Apache 2.0 または BSD-2-Clause | `packaging/` | https://github.com/pypa/packaging |
| PyMuPDF（MuPDF を含む） | GNU AGPL 3.0（または Artifex 社の商用ライセンス） | `PyMuPDF/COPYING` | https://github.com/pymupdf/PyMuPDF |
| opencv-python-headless（OpenCV と同梱ライブラリ） | Apache 2.0 ほか | `opencv-python-headless/` | https://github.com/opencv/opencv-python |
| NumPy（OpenBLAS などを含む） | BSD-3-Clause ほか | `numpy/` | https://github.com/numpy/numpy |
| Pillow（同梱の画像ライブラリを含む） | MIT-CMU ほか | `Pillow/` | https://github.com/python-pillow/Pillow |
| PyInstaller（起動部分） | GPL 2.0（ブートローダー例外付き） | `pyinstaller/COPYING.txt` | https://github.com/pyinstaller/pyinstaller |
| Microsoft Visual C++ ランタイム | Microsoft の再頒布可能コード | `python/LICENSE.txt` | https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist |

OpenCV に付いてくる動画用の FFmpeg は、このアプリでは使わないため、EXE に入れていません。

## リポジトリには含まないもの（`pip install -r requirements.txt` で入る部品）

上の表の customtkinter・PyMuPDF・opencv-python-headless・NumPy・Pillow・PyInstaller は、リポジトリには入っていません。開発するときに `pip install` で入ります。テスト用の pytest も同じです。

### PyMuPDF（AGPL 3.0）についての注意

PyMuPDF を同梱した EXE を配布する場合、その EXE 全体には GNU AGPL 3.0 の条件がかかります。
配布する人は、受け取った人がこのリポジトリのソースコードを入手できるようにしてください。
