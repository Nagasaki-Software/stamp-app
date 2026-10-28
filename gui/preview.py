"""スタンププレビュー。stamp_generator の出力を CTkLabel に表示。"""
import customtkinter as ctk
from PIL import Image

from core.stamp_generator import generate_stamp


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.label = ctk.CTkLabel(self, text="プレビュー")
        self.label.pack(expand=True)

    def update_stamp(self, values: dict):
        try:
            img = generate_stamp(
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
                color=values.get("stamp_color", "#E60033"),
            )
        except Exception as e:
            self.label.configure(text=f"プレビューエラー: {e}", image=None)
            return
        max_side = 320
        ratio = max_side / max(img.size)
        thumb = img.resize(
            (int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS
        )
        ctk_img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
        self.label.configure(image=ctk_img, text="")
        self.label.image = ctk_img  # 参照保持
