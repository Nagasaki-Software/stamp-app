"""StampApp 起動エントリ。"""
import os
import sys

# --windowed ビルド時は stdout/stderr が None になりライブラリ内print等でクラッシュするため
# 黒穴ファイルにリダイレクト。必ず他の import より前に実行する。
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# タスクバーで python.exe の仲間として扱われず、アプリ自身のアイコンが出るようにする
try:
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StampApp")
except Exception:
    pass

from gui.app import StampApp  # noqa: E402


def main():
    app = StampApp()
    app.mainloop()


if __name__ == "__main__":
    main()
