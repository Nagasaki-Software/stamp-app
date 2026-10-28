"""同梱用ArUcoマーカー一式（PNG5・SVG5・印刷PDF1）を assets/markers/ に生成する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.markers import export_all  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "markers"

if __name__ == "__main__":
    for p in export_all(OUT):
        print("wrote", p)
