from tkinter import filedialog, messagebox
import os
from analyzer.analyzer import analyze_log
from renderer import render_with_colors

last_file_path = None

def run_analysis(output_area, display_mode):
    global last_file_path
    file_path = filedialog.askopenfilename(filetypes=[("HTML files", "*.html")])
    if not file_path:
        return
    last_file_path = file_path
    _do_analysis(file_path, output_area, display_mode)

def re_run_analysis(output_area, display_mode):
    global last_file_path
    if last_file_path:
        _do_analysis(last_file_path, output_area, display_mode)

def _do_analysis(file_path, output_area, display_mode):
    output_area.delete("1.0", "end")
    try:
        result = analyze_log(file_path)
        render_with_colors(output_area, result["summary_text"], result["character_colors"], display_mode.get())
    except Exception as e:
        messagebox.showerror("解析エラー", str(e))

def save_text(output_area):
    content = output_area.get("1.0", "end").rstrip("\n")
    if not content.strip():
        messagebox.showinfo("保存", "保存する内容がありません。")
        return
    file_path = filedialog.asksaveasfilename(
        title="結果をテキスト保存",
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        initialdir=os.path.expanduser("~"),
        initialfile="TRPG解析結果.txt"
    )
    if not file_path:
        return
    try:
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content + "\n")
        messagebox.showinfo("保存", f"テキストを保存しました：\n{file_path}")
    except Exception as e:
        messagebox.showerror("保存エラー", str(e))