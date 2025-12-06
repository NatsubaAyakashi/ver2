from tkinter import filedialog, messagebox
import os
from analyzer.analyzer import extract_players_and_tabs
from renderer import build_formatted_html
from config import config
from bs4 import BeautifulSoup

last_file_path = None
current_structure = None

def run_analysis():
    global last_file_path
    file_path = filedialog.askopenfilename(filetypes=[("HTML files", "*.html")])
    if not file_path:
        return
    last_file_path = file_path
    # store structure for settings UI and export
    try:
        global current_structure
        current_structure = extract_players_and_tabs(file_path)
    except Exception:
        current_structure = None
    # try to extract title for config
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            config["html_title"] = title_tag.get_text(strip=True)
    except Exception:
        pass

def re_run_analysis():
    global last_file_path, current_structure
    if last_file_path:
        try:
            current_structure = extract_players_and_tabs(last_file_path)
        except Exception:
            current_structure = None

# _do_analysis and on-screen preview removed per UI simplification


def export_formatted_html():
    """Prompt for save location and export formatted HTML based on last opened file and current config."""
    global last_file_path, current_structure
    if not last_file_path:
        messagebox.showinfo("出力", "まず入力ファイルを選んで解析してください。")
        return
    file_path = filedialog.asksaveasfilename(
        title="整形済みHTMLを保存",
        defaultextension=".html",
        filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
        initialdir=os.path.expanduser("~"),
        initialfile=os.path.splitext(os.path.basename(last_file_path))[0] + "_整形後.html"
    )
    if not file_path:
        return
    try:
        html = build_formatted_html(last_file_path)
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        messagebox.showinfo("保存", f"整形済みHTMLを保存しました：\n{file_path}")
    except Exception as e:
        messagebox.showerror("保存エラー", str(e))

# removed save_text: text export not required per UI simplification