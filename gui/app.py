"""StampApp メインウィンドウ。左：設定、右：プレビュー。"""
import os
import socket
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import fitz

from core.font_registry import list_fonts
from core.logger import append_log, default_log_path, verify_log
from core.identity import apply_admin_override, load_locked_name, save_locked_name
from core.mark_detector import detect_marks
from core.markers import export_all
from core.pdf_stamper import stamp_pdf_in_place
from core.settings import load_settings, save_settings
from core.stamp_generator import generate_stamp
from gui.detection_panel import DetectionPanel
from gui.preview import PreviewPanel
from gui.stamp_panel import StampPanel


def _resource_root() -> Path:
    """EXE化時は _MEIPASS、開発時はプロジェクトルート。"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


ASSETS = _resource_root() / "assets"
FONTS_DIR = ASSETS / "fonts"


class StampApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("StampApp")
        self.geometry("960x720")
        ctk.set_appearance_mode("light")

        self._fonts = list_fonts(FONTS_DIR)
        self._settings = load_settings()
        # PCのデバイス名（ホスト名）をログとPDFメタデータに記録する
        try:
            self._hostname = socket.gethostname()
        except Exception:
            self._hostname = "unknown"

        # 名前ロック（偽造防止）：管理者override→ロック読込
        self._startup_notices: list[tuple[str, str]] = []
        self._name_locked = False
        self._identity_tampered = False
        ov_status, ov_name = apply_admin_override()
        if ov_status == "applied":
            self._startup_notices.append(("info", f"管理者により名前を変更しました：{ov_name}"))
        elif ov_status == "bad_keyword":
            self._startup_notices.append(("error", "管理者キーワードが正しくありません。"))
        locked_name, lock_status = load_locked_name()
        if lock_status == "locked":
            self._name_locked = True
            self._settings["name"] = locked_name
        elif lock_status == "tampered":
            self._name_locked = True
            self._identity_tampered = True
            self._settings["name"] = ""
            self._startup_notices.append(
                ("error", "本人名情報が破損/改ざんされています。管理者に連絡してください。")
            )

        # 上部バー
        topbar = ctk.CTkFrame(self)
        topbar.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkButton(topbar, text="PDFを開く", command=self._on_open).pack(
            side="left", padx=4
        )
        self.file_label = ctk.CTkLabel(topbar, text="ファイル未選択")
        self.file_label.pack(side="left", padx=8)

        # ステータス＋プログレスバー
        status_bar = ctk.CTkFrame(self)
        status_bar.pack(fill="x", padx=8, pady=(4, 0))
        self.status_label = ctk.CTkLabel(status_bar, text="待機中", anchor="w")
        self.status_label.pack(side="left", padx=8)
        self.progress = ctk.CTkProgressBar(status_bar, mode="determinate", height=10)
        self.progress.pack(side="left", fill="x", expand=True, padx=8)
        self.progress.set(0.0)

        # 左右ペイン
        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=8, pady=8)
        self.left = ctk.CTkFrame(body, width=420)
        self.left.pack(side="left", fill="y", padx=(0, 4))
        self.left.pack_propagate(False)
        self.right = ctk.CTkFrame(body)
        self.right.pack(side="left", fill="both", expand=True, padx=(4, 0))

        self.stamp_panel = StampPanel(
            self.left,
            fonts=self._fonts,
            initial=self._settings,
            on_change=self._on_settings_change,
            name_locked=self._name_locked,
        )
        self.stamp_panel.pack(fill="x", padx=4, pady=4)

        self.detection_panel = DetectionPanel(
            self.left,
            on_mark_change=self._on_mark_change,
            initial_mark=int(self._settings.get("selected_mark", 0)),
        )
        self.detection_panel.pack(fill="x", padx=4, pady=4)

        button_bar = ctk.CTkFrame(self.left)
        button_bar.pack(fill="x", padx=4, pady=8)
        self.execute_btn = ctk.CTkButton(
            button_bar,
            text="押印実行",
            command=self._on_execute,
            fg_color="#C8102E",
            hover_color="#A50E1F",
        )
        self.execute_btn.pack(side="left", padx=4)
        self.export_btn = ctk.CTkButton(
            button_bar,
            text="マーカー書き出し",
            command=self._on_export_markers,
        )
        self.export_btn.pack(side="left", padx=4)
        ctk.CTkButton(button_bar, text="ログを開く", command=self._on_open_log).pack(
            side="left", padx=4
        )
        ctk.CTkButton(button_bar, text="ログ検証", command=self._on_verify_log).pack(
            side="left", padx=4
        )

        self.preview = PreviewPanel(self.right)
        self.preview.pack(fill="both", expand=True, padx=4, pady=4)

        # 状態
        self._pdf_path: Path | None = None
        self._detections: dict[int, list] = {}
        self._page_cache: dict | None = None  # 画像PDF用ページレンダリングキャッシュ
        self._busy = False

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_settings_change()
        if self._startup_notices:
            self.after(300, self._flush_startup_notices)

    def _flush_startup_notices(self):
        for kind, msg in self._startup_notices:
            if kind == "error":
                messagebox.showerror("StampApp", msg)
            else:
                messagebox.showinfo("StampApp", msg)
        self._startup_notices = []

    # ---- 進捗表示 ----

    def _set_status(self, msg: str, ratio: float):
        """GUIスレッドからのみ呼び出すこと。"""
        self.status_label.configure(text=msg)
        self.progress.set(max(0.0, min(1.0, ratio)))

    def _post_progress(self, msg: str, ratio: float):
        """ワーカースレッドからGUIスレッドへ安全に進捗を通知。"""
        self.after(0, self._set_status, msg, ratio)

    # ---- イベントハンドラ ----

    def _on_open(self):
        if self._busy:
            return
        path = filedialog.askopenfilename(
            title="PDFを選択", filetypes=[("PDF files", "*.pdf")]
        )
        if not path:
            return
        self._pdf_path = Path(path)
        self.file_label.configure(text=self._pdf_path.name)
        self._page_cache = {}  # 新規PDF：キャッシュ初期化
        self._run_detection_async()

    def _on_mark_change(self, _mark: str):
        if self._busy:
            return
        self._run_detection_async()

    def _on_settings_change(self):
        self.preview.update_stamp(self.stamp_panel.values())

    def _run_detection_async(self):
        if not self._pdf_path or self._busy:
            return
        self._busy = True
        self.execute_btn.configure(state="disabled")
        mark = self.detection_panel.selected_mark()
        self._set_status("検出開始…", 0.0)

        def worker():
            error = None
            results: dict[int, list] = {}
            try:
                doc = fitz.open(self._pdf_path)
                try:
                    results = detect_marks(
                        doc,
                        mark,
                        progress=self._post_progress,
                        page_cache=self._page_cache,
                    )
                finally:
                    doc.close()
            except Exception as e:
                error = e
            self.after(0, self._on_detection_done, mark, results, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_detection_done(self, mark: str, results: dict, error: Exception | None):
        self._busy = False
        self.execute_btn.configure(state="normal")
        if error is not None:
            self._set_status("エラー", 0.0)
            messagebox.showerror("StampApp 検出エラー", str(error))
            self._detections = {}
        else:
            self._detections = results
            total_pages = sum(1 for rs in results.values() if rs)
            self._set_status(f"検出完了: {total_pages}ページ", 1.0)
        self.detection_panel.set_detection_summary(mark, self._detections)

    def _on_execute(self):
        if self._busy:
            return
        if not self._pdf_path:
            messagebox.showwarning("StampApp", "PDFが選択されていません")
            return
        target_count = sum(1 for rs in self._detections.values() if rs)
        if target_count == 0:
            messagebox.showinfo("StampApp", "選択中のマークが検出されませんでした")
            return
        # 名前情報が改ざんされている場合は押印を止める（偽名押印を許さない）
        if self._identity_tampered:
            messagebox.showerror(
                "StampApp", "本人名情報が破損/改ざんされています。管理者に連絡してください。"
            )
            return
        # 未ロックなら初回押印時に名前を確定（以後は管理者キーワードでのみ変更）
        if not self._name_locked:
            name_now = self.stamp_panel.values()["name"].strip()
            if not name_now:
                messagebox.showwarning("StampApp", "名前が入力されていません")
                return
            if not messagebox.askokcancel(
                "StampApp 名前の確定",
                f"この名前『{name_now}』で確定します。\n"
                "以後の変更には管理者キーワードが必要です。よろしいですか？",
            ):
                return
            save_locked_name(name_now)
            self._name_locked = True
            self.stamp_panel.lock_name()
        if not messagebox.askokcancel(
            "StampApp",
            f"PDFを上書きします。よろしいですか？\n対象: {target_count} ページ",
        ):
            return
        self._busy = True
        self.execute_btn.configure(state="disabled")
        self._set_status("押印処理中…", 0.3)

        values = self.stamp_panel.values()
        values["date_str"] = datetime.now().strftime("'%y.%m.%d")

        # 押印予定ページを事前確定（ハッシュチェーンとPDFメタデータに同じ情報を埋め込むため）
        pages_to_stamp = sorted(
            idx + 1 for idx, rs in self._detections.items() if rs
        )
        log_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def worker():
            error = None
            stamped: list[int] = []
            try:
                # ログを先に追記（row_hash を取得してPDFメタデータに埋め込むため）
                row_hash = append_log(
                    default_log_path(),
                    timestamp=log_timestamp,
                    pdf_path=str(self._pdf_path),
                    pages=pages_to_stamp,
                    stamp_name=values["name"],
                    stamp_date=values["date_str"],
                    stamp_affiliation=values["affiliation"],
                    hostname=self._hostname,
                )
                metadata_record = (
                    f"v1.1 / {log_timestamp} / {values['name']} / "
                    f"{values['affiliation']} / host: {self._hostname} / "
                    f"pages: {','.join(str(p) for p in pages_to_stamp)} / "
                    f"hash: {row_hash}"
                )
                stamp_img = generate_stamp(
                    name=values["name"],
                    date_str=values["date_str"],
                    affiliation=values["affiliation"],
                    diameter_mm=values["diameter_mm"],
                    line_width_pt=values["line_width_pt"],
                    font_path=values["font_path"],
                    name_size_scale=values.get("name_size_scale", 1.0),
                    name_y_offset_mm=values.get("name_y_offset_mm", 0.0),
                    aff_size_scale=values.get("aff_size_scale", 1.0),
                    aff_y_offset_mm=values.get("aff_y_offset_mm", 0.0),
                    color=values.get("stamp_color", "#C8102E"),
                )
                stamped = stamp_pdf_in_place(
                    pdf_path=self._pdf_path,
                    detections=self._detections,
                    stamp_image=stamp_img,
                    stamp_diameter_pt=values["diameter_mm"] * 72 / 25.4,
                    metadata_record=metadata_record,
                )
            except Exception as e:
                error = e
            self.after(0, self._on_execute_done, stamped, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_execute_done(self, stamped: list[int], error: Exception | None):
        self._busy = False
        self.execute_btn.configure(state="normal")
        if error is not None:
            self._set_status("エラー", 0.0)
            messagebox.showerror("StampApp エラー", str(error))
            return
        self._set_status(f"押印完了: {len(stamped)}ページ", 1.0)
        # PDF内容が変わったのでキャッシュを破棄
        self._page_cache = {}
        messagebox.showinfo(
            "StampApp",
            f"{len(stamped)}ページに押印しました。\nログに記録しました。",
        )
        # 再検出（押印後はマークが消えているので 0 ページになるはず）
        self._run_detection_async()

    def _on_export_markers(self):
        if self._busy:
            messagebox.showinfo("StampApp", "現在処理中です。完了後に再度お試しください。")
            return
        folder = filedialog.askdirectory(title="マーカーの保存先フォルダを選択")
        if not folder:
            return
        try:
            export_all(Path(folder))
        except Exception as e:
            messagebox.showerror("StampApp", f"書き出しに失敗しました：\n{e}")
            return
        messagebox.showinfo(
            "StampApp",
            f"マーカーを書き出しました（PNG5・SVG5・印刷PDF1）。\n保存先：{folder}\n\n"
            "Acrobat/Word/Excelに『挿入→画像』で貼り付けてください（約10mm・縦横比固定）。",
        )

    def _on_open_log(self):
        path = default_log_path()
        if not path.exists():
            messagebox.showinfo("StampApp", "ログはまだありません")
            return
        os.startfile(path)  # type: ignore[attr-defined]

    def _on_verify_log(self):
        path = default_log_path()
        if not path.exists():
            messagebox.showinfo("StampApp ログ検証", "ログはまだありません")
            return
        is_valid, tampered, legacy = verify_log(path)
        # 行数の取得（ヘッダ除く）
        try:
            with path.open(encoding="utf-8-sig") as f:
                total = max(0, sum(1 for _ in f) - 1)
        except Exception:
            total = 0
        if is_valid:
            messagebox.showinfo(
                "StampApp ログ検証",
                f"✓ ログは改ざんされていません。\n対象: {total} 行 / すべて正当",
            )
            return
        msg_lines = ["✗ ログの検証に失敗しました。"]
        if tampered:
            msg_lines.append(f"改ざん検知: 行 {', '.join(str(n) for n in tampered)}")
        if legacy:
            head = ", ".join(str(n) for n in legacy[:8])
            more = "" if len(legacy) <= 8 else f" 他{len(legacy) - 8}件"
            msg_lines.append(f"旧形式または列不足: 行 {head}{more}")
        messagebox.showwarning("StampApp ログ検証", "\n".join(msg_lines))

    def _on_close(self):
        try:
            values = self.stamp_panel.values()
            save_settings(
                {
                    "name": values["name"],
                    "affiliation": values["affiliation"],
                    "diameter_mm": values["diameter_mm"],
                    "line_width_pt": values["line_width_pt"],
                    "font_key": values["font_key"],
                    "stamp_color": values["stamp_color"],
                    "selected_mark": self.detection_panel.selected_mark(),
                    "name_size_scale": values["name_size_scale"],
                    "name_y_offset_mm": values["name_y_offset_mm"],
                    "aff_size_scale": values["aff_size_scale"],
                    "aff_y_offset_mm": values["aff_y_offset_mm"],
                }
            )
        except Exception:
            pass
        self.destroy()
