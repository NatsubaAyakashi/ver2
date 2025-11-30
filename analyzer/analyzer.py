from bs4 import BeautifulSoup
from config import config

def analyze_log(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    summary_text = ""
    character_colors = {}

    # プレイヤー名を抽出（例: <b>タグ）
    for b in soup.find_all("b"):
        name = b.get_text().strip()
        if name not in config["players"]:
            # デフォルト色割り当て
            default_colors = ["#4caf50", "#ff5722", "#2196f3", "#9c27b0", "#795548"]
            assigned_color = default_colors[len(config["players"]) % len(default_colors)]
            config["players"][name] = {"color": assigned_color, "background": "#ffffff"}
        character_colors[name] = config["players"][name]["color"]

    # 本文抽出
    for p in soup.find_all("p"):
        summary_text += p.get_text() + "\n"

    return {
        "summary_text": summary_text,
        "character_colors": character_colors
    }