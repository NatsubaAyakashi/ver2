import re
from pathlib import Path
from bs4 import BeautifulSoup
from config import config

# 正規表現の事前コンパイル
# color: #xxxxxx, #xxx, rgb(r,g,b) に対応
COLOR_RE = re.compile(r"color\s*:\s*((?:#[0-9A-Fa-f]{6})|(?:#[0-9A-Fa-f]{3})|(?:rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)))", re.IGNORECASE)
ROLL_RE = re.compile(r"＞\s*(\d{1,3})")
D100_FLAG_RE = re.compile(r"1D100", re.IGNORECASE)
TAB_COLOR_RE = re.compile(r'\.t([^\s{]+)\s*\{[^}]*background-color:\s*([^;}\s]+)')

def _normalize_color(c):
    """色文字列を正規化する（rgb -> hex変換など）。Tkinter等での互換性のため。"""
    if c.lower().startswith("rgb"):
        nums = re.findall(r'\d+', c)
        if len(nums) >= 3:
            r, g, b = map(int, nums[:3])
            return f"#{r:02x}{g:02x}{b:02x}"
    return c

def extract_color_from_p_or_spans(p):
    """pタグまたはその子要素(b, span, font)から色を抽出する。"""
    # 1. pタグ自身の style
    style_attr = p.get("style", "") or ""
    m = COLOR_RE.search(style_attr)
    if m:
        return _normalize_color(m.group(1))

    # 2. bタグ (名前) の style
    b = p.find("b")
    if b:
        st = b.get("style", "") or ""
        m = COLOR_RE.search(st)
        if m:
            return _normalize_color(m.group(1))

    # 3. spanタグ の style
    for sp in p.find_all("span"):
        st = sp.get("style", "") or ""
        mm = COLOR_RE.search(st)
        if mm:
            return _normalize_color(mm.group(1))

    # 4. fontタグ (古い形式) の color
    for f in p.find_all("font"):
        c = f.get("color")
        if c:
            return c

    return None


def extract_players_and_tabs(file_path: Path):
    """
    HTMLを解析し、プレイヤー名、出現回数、色、タブ名、タブ色を抽出する。

    戻り値:
    {"players": {name: {"color": str|None, "count": int}}, "tabs": [str], "tab_colors": {str: str}, "html": str}
    """
    with file_path.open("r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    players = {}
    tabs = []
    tab_colors = {}

    # CSSからタブの色を抽出
    for style in soup.find_all("style"):
        if not style.string:
            continue
        css_text = style.string
        for match in TAB_COLOR_RE.finditer(css_text):
            tab_name = match.group(1).strip("[]")
            bg_color = match.group(2).strip()
            if bg_color:
                tab_colors[tab_name] = bg_color

    # 新フォーマット（div.tab）からタブ名とプレイヤーを抽出
    for tab_div in soup.find_all("div", class_="tab"):
        title_tag = tab_div.find("div", class_="tabtitle")
        if title_tag:
            tt = title_tag.get_text(strip=True)
            if tt not in tabs:
                tabs.append(tt)

        for p in tab_div.find_all("p"):
            name_tag = p.find("b")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            if name not in players:
                players[name] = {"color": extract_color_from_p_or_spans(p), "count": 0}
            players[name]["count"] += 1

    # 旧フォーマット（p > span）からタブ名とプレイヤーを抽出
    if not players: # 新フォーマットでプレイヤーが見つからない場合のみ
        for p in soup.find_all("p"):
            spans = p.find_all("span")
            if len(spans) < 2:
                continue

            tab_name = spans[0].get_text(strip=True).strip("[]")
            if tab_name and tab_name not in tabs:
                tabs.append(tab_name)

            name = spans[1].get_text(strip=True)
            if not name:
                continue

            if name not in players:
                players[name] = {"color": extract_color_from_p_or_spans(p), "count": 0}
            players[name]["count"] += 1

    return {"players": players, "tabs": list(dict.fromkeys(tabs)), "tab_colors": tab_colors, "html": html}


def extract_roll_lines(file_path: Path):
    """
    HTMLからダイスロールを含む行を抽出する。

    戻り値:
    [{"tab": str|None, "name": str, "text": str, "rolls": [str]}]
    """
    with file_path.open("r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    entries = []

    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not D100_FLAG_RE.search(text):
            continue
        rolls = ROLL_RE.findall(text)
        if not rolls:
            continue

        name = "不明"
        b_tag = p.find("b")
        if b_tag:
            name = b_tag.get_text(strip=True)
        else:
            spans = p.find_all("span")
            if len(spans) >= 2:
                name = spans[1].get_text(strip=True)

        tag = None
        tab_div = p.find_parent("div", class_="tab")
        if tab_div:
            title_tag = tab_div.find("div", class_="tabtitle")
            if title_tag:
                tag = title_tag.get_text(strip=True)

        entries.append({"tab": tag, "name": name, "text": text, "rolls": rolls})

    return entries
