"""Simple Tkinter based UI for batch translation and incremental learning."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .config import TranslatorConfig
from .mapping_loader import MappingLoader
from .translator import AddressTranslator


class TranslatorUI:
    def __init__(self, loader: MappingLoader, config: TranslatorConfig) -> None:
        self.loader = loader
        self.config = config
        self.translator = AddressTranslator(loader, config)
        self.root = tk.Tk()
        self.root.title("Yunnan Address Translator")
        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        input_label = ttk.Label(main, text="原始地址 (多行，自动带行号)")
        input_label.grid(row=0, column=0, sticky="w")
        self.input_text = tk.Text(main, width=60, height=20)
        self.input_text.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        output_label = ttk.Label(main, text="翻译结果")
        output_label.grid(row=0, column=1, sticky="w")
        self.output_text = tk.Text(main, width=60, height=20, state="normal")
        self.output_text.grid(row=1, column=1, sticky="nsew")

        log_label = ttk.Label(main, text="识别日志")
        log_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.log_text = tk.Text(main, width=120, height=10, state="normal")
        self.log_text.grid(row=3, column=0, columnspan=2, sticky="nsew")

        main.rowconfigure(1, weight=1)
        main.rowconfigure(3, weight=1)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        translate_btn = ttk.Button(button_frame, text="翻译", command=self.translate)
        translate_btn.pack(side=tk.LEFT)

        save_btn = ttk.Button(button_frame, text="追加映射", command=self.open_append_dialog)
        save_btn.pack(side=tk.LEFT, padx=10)

        reload_btn = ttk.Button(button_frame, text="重新加载 mapping", command=self.reload_mapping)
        reload_btn.pack(side=tk.LEFT)

    def translate(self) -> None:
        raw_text = self.input_text.get("1.0", tk.END).strip("\n")
        lines = raw_text.splitlines()
        if not lines:
            messagebox.showinfo("提示", "请先输入地址")
            return

        results = self.translator.translate_lines(lines, log=False)
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)

        for result in results:
            output_line = f"{result.line_number:03d}: {', '.join(result.output)}"
            self.output_text.insert(tk.END, output_line + "\n")
            detected_parts = []
            for level, values in result.detected.items():
                if values:
                    detected_parts.append(f"{level}: {', '.join(values)}")
            log_line = f"第{result.line_number}行 原文: {result.original} | 识别: {'; '.join(detected_parts)} | 输出: {', '.join(result.output)}"
            self.log_text.insert(tk.END, log_line + "\n")

        self.output_text.configure(state="disabled")
        self.log_text.configure(state="disabled")

    def reload_mapping(self) -> None:
        try:
            self.translator.reload_mapping()
            messagebox.showinfo("提示", "mapping.json 已重新加载")
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("错误", f"重新加载失败: {exc}")

    def open_append_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("追加映射")
        ttk.Label(dialog, text="层级").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        level_var = tk.StringVar(value="alias")
        level_combo = ttk.Combobox(
            dialog,
            textvariable=level_var,
            values=("alias", "group", "village", "town", "district", "city", "province"),
            state="readonly",
        )
        level_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="中文 (键)").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        key_entry = ttk.Entry(dialog, width=30)
        key_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="英文 (值)").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        value_entry = ttk.Entry(dialog, width=30)
        value_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_and_close() -> None:
            level = level_var.get()
            key = key_entry.get().strip()
            value = value_entry.get().strip()
            if not key or not value:
                messagebox.showerror("错误", "请输入完整的键和值")
                return
            try:
                self.loader.update_entry(level, key, value)
                self.translator.reload_mapping()
            except Exception as exc:  # pylint: disable=broad-except
                messagebox.showerror("错误", f"追加失败: {exc}")
                return
            messagebox.showinfo("提示", f"已在 {level} 中追加 {key} -> {value}")
            dialog.destroy()

        ttk.Button(dialog, text="保存", command=save_and_close).grid(row=3, column=0, padx=5, pady=10)
        ttk.Button(dialog, text="取消", command=dialog.destroy).grid(row=3, column=1, padx=5, pady=10)

    def run(self) -> None:
        self.root.mainloop()


def launch(loader: MappingLoader, config: TranslatorConfig) -> None:
    app = TranslatorUI(loader, config)
    app.run()
