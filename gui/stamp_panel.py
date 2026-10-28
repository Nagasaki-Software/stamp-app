"""スタンプ設定UI：名前/所属/日付（読取専用）/サイズ/線太さ/書体/詳細設定。

数値入力欄はスライダーと双方向同期する。
"""
from datetime import datetime
from pathlib import Path
from typing import Callable

import customtkinter as ctk


def _parse_float(s: str) -> float:
    return float(s.strip().replace("+", ""))


def _parse_percent(s: str) -> float:
    return float(s.strip().rstrip("%").replace("+", "")) / 100.0


def _value_row(
    parent,
    row: int,
    label: str,
    variable: ctk.Variable,
    from_: float,
    to: float,
    display_fmt: str,
    parse_fn: Callable[[str], float],
    on_change: Callable[[], None],
) -> tuple[ctk.CTkSlider, ctk.CTkEntry, ctk.StringVar]:
    """スライダー＋数値入力欄を1行配置。双方向同期。"""
    ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
    holder = ctk.CTkFrame(parent, fg_color="transparent")
    holder.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
    holder.columnconfigure(0, weight=1)

    slider = ctk.CTkSlider(
        holder,
        from_=from_,
        to=to,
        variable=variable,
        command=lambda _: on_change(),
    )
    slider.grid(row=0, column=0, sticky="ew")

    text_var = ctk.StringVar(value=display_fmt.format(variable.get()))
    entry = ctk.CTkEntry(holder, textvariable=text_var, width=72, justify="right")
    entry.grid(row=0, column=1, padx=(6, 0))

    syncing = {"v": False}

    def _sync_from_var(*_):
        if syncing["v"]:
            return
        text_var.set(display_fmt.format(variable.get()))

    def _commit_entry(_event=None):
        try:
            v = parse_fn(text_var.get())
        except (ValueError, TypeError):
            text_var.set(display_fmt.format(variable.get()))
            return
        v = max(from_, min(to, v))
        syncing["v"] = True
        variable.set(v)
        syncing["v"] = False
        text_var.set(display_fmt.format(v))
        on_change()

    variable.trace_add("write", _sync_from_var)
    entry.bind("<Return>", _commit_entry)
    entry.bind("<FocusOut>", _commit_entry)

    return slider, entry, text_var


class StampPanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        fonts: dict[str, Path],
        initial: dict,
        on_change=None,
        name_locked: bool = False,
    ):
        super().__init__(master)
        self._on_change = on_change or (lambda: None)
        self._fonts = fonts

        # 名前（ロック時は編集不可＝グレーアウト）
        ctk.CTkLabel(self, text="名前").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.name_var = ctk.StringVar(value=initial.get("name", ""))
        self.name_entry = ctk.CTkEntry(self, textvariable=self.name_var)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        if name_locked:
            self.name_entry.configure(state="disabled")

        # 所属
        ctk.CTkLabel(self, text="所属/役職").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.affiliation_var = ctk.StringVar(value=initial.get("affiliation", ""))
        ctk.CTkEntry(self, textvariable=self.affiliation_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )

        # 日付
        ctk.CTkLabel(self, text="日付").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.date_label = ctk.CTkLabel(self, text=self._format_date_now(), anchor="w")
        self.date_label.grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        self._tick_date()

        # サイズ
        self.size_var = ctk.DoubleVar(value=float(initial.get("diameter_mm", 15.0)))
        _value_row(
            self, 3, "サイズ (mm)", self.size_var, 5, 30,
            "{:.1f}", _parse_float, self._on_change,
        )

        # 線太さ
        self.line_var = ctk.DoubleVar(value=float(initial.get("line_width_pt", 1.0)))
        _value_row(
            self, 4, "線太さ (pt)", self.line_var, 0.3, 3.0,
            "{:.2f}", _parse_float, self._on_change,
        )

        # 書体
        ctk.CTkLabel(self, text="書体").grid(row=5, column=0, sticky="w", padx=6, pady=4)
        font_names = list(self._fonts.keys()) or ["（フォント無し）"]
        initial_font = initial.get("font_key")
        if initial_font not in font_names:
            initial_font = font_names[0]
        self.font_var = ctk.StringVar(value=initial_font)
        ctk.CTkOptionMenu(
            self,
            values=font_names,
            variable=self.font_var,
            command=lambda _: self._on_change(),
        ).grid(row=5, column=1, sticky="ew", padx=6, pady=4)

        # 印鑑の色
        ctk.CTkLabel(self, text="印鑑の色").grid(row=6, column=0, sticky="w", padx=6, pady=4)
        self.color_var = ctk.StringVar(value=initial.get("stamp_color", "#C8102E"))
        color_holder = ctk.CTkFrame(self, fg_color="transparent")
        color_holder.grid(row=6, column=1, sticky="w", padx=6, pady=4)
        self.color_swatch = ctk.CTkButton(
            color_holder,
            text="",
            width=40,
            command=self._pick_color,
            fg_color=self.color_var.get(),
            hover=False,
        )
        self.color_swatch.pack(side="left")
        ctk.CTkButton(
            color_holder, text="色を選ぶ", width=80, command=self._pick_color
        ).pack(side="left", padx=(6, 0))

        # ---- 詳細設定 ----
        self._adv_open = ctk.BooleanVar(value=False)
        self.adv_toggle = ctk.CTkButton(
            self,
            text="▶ 詳細設定（位置・サイズ補正）",
            command=self._toggle_advanced,
            anchor="w",
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray80", "gray30"),
        )
        self.adv_toggle.grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 2))

        self.adv_frame = ctk.CTkFrame(self)
        self.adv_frame.columnconfigure(1, weight=1)

        self.name_size_scale = ctk.DoubleVar(value=float(initial.get("name_size_scale", 1.0)))
        _value_row(
            self.adv_frame, 0, "名前サイズ (%)",
            self.name_size_scale, 0.5, 1.5,
            "{:.0%}", _parse_percent, self._on_change,
        )

        self.name_y_offset = ctk.DoubleVar(value=float(initial.get("name_y_offset_mm", 0.0)))
        _value_row(
            self.adv_frame, 1, "名前 上下 (mm)",
            self.name_y_offset, -5.0, 5.0,
            "{:+.1f}", _parse_float, self._on_change,
        )

        self.aff_size_scale = ctk.DoubleVar(value=float(initial.get("aff_size_scale", 1.0)))
        _value_row(
            self.adv_frame, 2, "所属サイズ (%)",
            self.aff_size_scale, 0.5, 1.5,
            "{:.0%}", _parse_percent, self._on_change,
        )

        self.aff_y_offset = ctk.DoubleVar(value=float(initial.get("aff_y_offset_mm", 0.0)))
        _value_row(
            self.adv_frame, 3, "所属 上下 (mm)",
            self.aff_y_offset, -5.0, 5.0,
            "{:+.1f}", _parse_float, self._on_change,
        )

        ctk.CTkButton(
            self.adv_frame,
            text="補正を初期値に戻す",
            command=self._reset_advanced,
            height=24,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 4))

        self.columnconfigure(1, weight=1)

        # 名前・所属のテキスト変更でプレビュー再描画
        self.name_var.trace_add("write", lambda *_: self._on_change())
        self.affiliation_var.trace_add("write", lambda *_: self._on_change())

    def _toggle_advanced(self):
        if self._adv_open.get():
            self.adv_frame.grid_remove()
            self.adv_toggle.configure(text="▶ 詳細設定（位置・サイズ補正）")
            self._adv_open.set(False)
        else:
            self.adv_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
            self.adv_toggle.configure(text="▼ 詳細設定（位置・サイズ補正）")
            self._adv_open.set(True)

    def _reset_advanced(self):
        self.name_size_scale.set(1.0)
        self.name_y_offset.set(0.0)
        self.aff_size_scale.set(1.0)
        self.aff_y_offset.set(0.0)
        self._on_change()

    def _pick_color(self):
        from tkinter import colorchooser
        _rgb, hexv = colorchooser.askcolor(
            color=self.color_var.get(), title="印鑑の色を選ぶ"
        )
        if hexv:
            self.color_var.set(hexv)
            self.color_swatch.configure(fg_color=hexv)
            self._on_change()

    @staticmethod
    def _format_date_now() -> str:
        return datetime.now().strftime("'%y.%m.%d")

    def _tick_date(self):
        new_str = self._format_date_now()
        if self.date_label.cget("text") != new_str:
            self.date_label.configure(text=new_str)
            self._on_change()
        self.after(60_000, self._tick_date)

    def lock_name(self):
        """名前欄を編集不可（グレーアウト）にする。初回確定時に呼ぶ。"""
        self.name_entry.configure(state="disabled")

    def selected_font_path(self) -> Path:
        key = self.font_var.get()
        if key in self._fonts:
            return self._fonts[key]
        return next(iter(self._fonts.values()))

    def values(self) -> dict:
        return {
            "name": self.name_var.get(),
            "affiliation": self.affiliation_var.get(),
            "date_str": self._format_date_now(),
            "diameter_mm": float(self.size_var.get()),
            "line_width_pt": float(self.line_var.get()),
            "font_key": self.font_var.get(),
            "font_path": self.selected_font_path(),
            "stamp_color": self.color_var.get(),
            "name_size_scale": float(self.name_size_scale.get()),
            "name_y_offset_mm": float(self.name_y_offset.get()),
            "aff_size_scale": float(self.aff_size_scale.get()),
            "aff_y_offset_mm": float(self.aff_y_offset.get()),
        }
