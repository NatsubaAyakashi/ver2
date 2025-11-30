import tkinter as tk
from tkinter import colorchooser
from analyzer.analyzer import config
from controller import re_run_analysis

def open_settings(root, output_area, display_mode):
    win = tk.Toplevel(root)
    win.title("設定")
    win.grab_set()

    # 全体背景色
    tk.Label(win, text="全体背景色").grid(row=0, column=0, sticky="w")
    bg_var = tk.StringVar(win, value=config["global_background"])
    tk.Entry(win, textvariable=bg_var, width=10).grid(row=0, column=1)
    tk.Button(win, text="選択", command=lambda: choose_color(bg_var)).grid(row=0, column=2)

    def save():
        config["global_background"] = bg_var.get()
        win.destroy()
        re_run_analysis(output_area, display_mode)

    tk.Button(win, text="保存", command=save).grid(row=10, column=0, pady=5)
    tk.Button(win, text="キャンセル", command=win.destroy).grid(row=10, column=1, pady=5)

def choose_color(var):
    color_code = colorchooser.askcolor(title="色を選択")[1]
    if color_code:
        var.set(color_code)