import re
from tkinter import filedialog, messagebox
from pathlib import Path
from analyzer.analyzer import extract_players_and_tabs
from renderer import build_formatted_html
from config import config
from bs4 import BeautifulSoup

last_file_path: Path | None = None
current_structure: dict | None = None

def run_analysis():
    """ファイルを開き、内容を解析して、UIで利用するための基本的な構造を準備する。"""
    global last_file_path, current_structure

    filepath_str = filedialog.askopenfilename(filetypes=[("HTML files", "*.html")])
    if not filepath_str:
        return

    file_path = Path(filepath_str)
    last_file_path = file_path

    try:
        current_structure = extract_players_and_tabs(file_path)
    except Exception:
        current_structure = None
        messagebox.showerror("解析エラー", f"ファイルの解析中にエラーが発生しました:\n{file_path}")

    try:
        with file_path.open("r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            config["html_title"] = title_tag.get_text(strip=True)
        else:
            config["html_title"] = file_path.stem
    except Exception:
        config["html_title"] = file_path.stem

def re_run_analysis():
    """最後に開いたファイルに対して再解析を実行する。主に設定変更後に呼び出される。"""
    global last_file_path, current_structure
    if last_file_path:
        try:
            current_structure = extract_players_and_tabs(last_file_path)
        except Exception as e:
            current_structure = None
            messagebox.showerror("再解析エラー", f"ファイルの再解析中にエラーが発生しました:\n{e}")

def export_formatted_html():
    """最後に解析したファイルの内容と現在の設定を基に、整形済みのHTMLファイルを出力する。"""
    global last_file_path
    if not last_file_path:
        messagebox.showinfo("出力", "まず入力ファイルを選んで解析してください。")
        return

    # HTMLタイトルをファイル名として使用（使用不可文字は置換）
    candidate_name = config.get("html_title", last_file_path.stem)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', candidate_name).strip()
    if not safe_name:
        safe_name = last_file_path.stem
    initial_filename = f"{safe_name}.html"

    output_path_str = filedialog.asksaveasfilename(
        title="整形済みHTMLを保存",
        defaultextension=".html",
        filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
        initialdir=str(Path.home()),
        initialfile=initial_filename
    )
    if not output_path_str:
        return

    output_path = Path(output_path_str)

    try:
        html_content = build_formatted_html(last_file_path, config)
        output_path.write_text(html_content, encoding="utf-8")
        messagebox.showinfo("保存完了", f"整形済みHTMLを保存しました:\n{output_path}")
    except Exception as e:
        messagebox.showerror("保存エラー", f"ファイルの保存中にエラーが発生しました:\n{e}")
