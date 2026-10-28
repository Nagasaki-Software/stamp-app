# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — StampApp を onedir 方式でビルドする。

onedir 方式の利点:
- 初回起動の一時展開が不要で、起動が大幅に高速化（数秒→1秒程度）
- 2回目以降も同様に高速

トレードオフ:
- 配布物は dist/StampApp/ フォルダ全体（200+ファイル）。
  単一ファイルとして配布したい場合はZIP圧縮を推奨。
"""
import os

from PyInstaller.utils.hooks import collect_all

# 秘密値が無いと公開済みの開発用の値で EXE ができてしまうため、ビルドを止める
if not os.path.exists(os.path.join("core", "_secrets.py")):
    raise SystemExit("core/_secrets.py がありません。配布ビルドには秘密値ファイルが必要です。")

# 画面の版数（gui/app.py）と EXE のプロパティの版数（version_info.txt）の食い違いを止める
import re

_app_ver = re.search(r'APP_VERSION = "(.+?)"', open(os.path.join("gui", "app.py"), encoding="utf-8").read()).group(1)
_exe_ver = re.search(r"u'ProductVersion', u'(.+?)'", open("version_info.txt", encoding="utf-8").read()).group(1)
if _app_ver != _exe_ver:
    raise SystemExit(f"版数が食い違っています：gui/app.py={_app_ver} / version_info.txt={_exe_ver}")

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

datas = list(ctk_datas) + [
    ("assets/fonts", "assets/fonts"),
    ("assets/markers", "assets/markers"),
    ("assets/icon.ico", "assets"),  # 画面左上・タスクバー用
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=list(ctk_binaries),
    datas=datas,
    hiddenimports=list(ctk_hiddenimports),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=None,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir: バイナリは COLLECT 側に
    name="StampApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",  # scripts/make_icon.py で作る
    version="version_info.txt",  # SAC/SmartScreen の誤検知低減のためメタデータ付与
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="StampApp",
)
