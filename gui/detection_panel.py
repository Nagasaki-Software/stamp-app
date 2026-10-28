"""対象マーカー（No.1〜No.5）の選択と、各ページの検出結果サマリ表示。"""
import customtkinter as ctk

from core.markers import MARKER_IDS, MARKER_LABELS, render_marker_png

try:
    from PIL import Image  # noqa: F401  (CTkImage 用に存在確認)
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


class DetectionPanel(ctk.CTkFrame):
    def __init__(self, master, on_mark_change=None, initial_mark: int = 0):
        super().__init__(master)
        self._on_mark_change = on_mark_change or (lambda _i: None)

        ctk.CTkLabel(self, text="対象マーカー", anchor="w").pack(
            fill="x", padx=6, pady=(6, 0)
        )
        grid = ctk.CTkFrame(self)
        grid.pack(fill="x", padx=6, pady=2)

        if initial_mark not in MARKER_IDS:
            initial_mark = MARKER_IDS[0]
        self.mark_var = ctk.IntVar(value=initial_mark)

        self._thumbs = []  # GC防止のため参照を保持
        for col, mid in enumerate(MARKER_IDS):
            grid.columnconfigure(col, weight=1, uniform="markers")
            if _HAS_PIL:
                pil = render_marker_png(mid, module_px=8).convert("RGB")
                thumb = ctk.CTkImage(light_image=pil, dark_image=pil, size=(46, 60))
                self._thumbs.append(thumb)
                ctk.CTkLabel(grid, text="", image=thumb).grid(
                    row=0, column=col, padx=2, pady=(2, 0)
                )
            ctk.CTkRadioButton(
                grid,
                text=MARKER_LABELS[mid],
                variable=self.mark_var,
                value=mid,
                command=self._fire,
                width=10,
            ).grid(row=1, column=col, padx=2, pady=2)

        ctk.CTkLabel(self, text="検出結果", anchor="w").pack(
            fill="x", padx=6, pady=(8, 0)
        )
        self.result_label = ctk.CTkLabel(
            self, text="（PDF未読込）", anchor="w", justify="left"
        )
        self.result_label.pack(fill="x", padx=6, pady=2)

    def _fire(self):
        self._on_mark_change(self.mark_var.get())

    def selected_mark(self) -> int:
        return int(self.mark_var.get())

    def set_detection_summary(self, marker_id: int, detections: dict):
        label = MARKER_LABELS.get(marker_id, str(marker_id))
        pages = [str(i + 1) for i, rs in detections.items() if rs]
        if not pages:
            self.result_label.configure(text=f"{label} を検出: 0ページ")
        else:
            self.result_label.configure(
                text=f"{label} を検出: {len(pages)}ページ\n(P{','.join(pages)})"
            )
