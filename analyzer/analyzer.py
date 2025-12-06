from bs4 import BeautifulSoup
from config import config


def extract_color_from_p_or_spans(p):
    """Extract color from paragraph or span style attributes."""
    import re
    COLOR_RE = re.compile(r"color\s*:\s*(#[0-9A-Fa-f]{6})")
    style_attr = p.get("style", "") or ""
    m = COLOR_RE.search(style_attr)
    if m:
        return m.group(1)
    for sp in p.find_all("span"):
        st = sp.get("style", "") or ""
        mm = COLOR_RE.search(st)
        if mm:
            return mm.group(1)
    return None


def extract_players_and_tabs(file_path):
    """Extract player names with occurrence count, colors, tab titles, and tab colors from input HTML.

    Returns dict: {"players": {name: {"color": color_or_None, "count": int}}, "tabs": [titles], "tab_colors": {tab_name: color}, "html": original_html}
    """
    import re

    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    players = {}  # {name: {"color": ..., "count": ...}}
    tabs = []
    tab_colors = {}  # {tab_name: background_color}

    # Extract tab colors from CSS
    for style in soup.find_all("style"):
        if not style.string:
            continue
        # Look for .tN { background-color: #... } patterns
        css_text = style.string
        # Match patterns like .t塩 { background-color: #... }
        for match in re.finditer(r'\.t([^\s{]+)\s*\{[^}]*background-color:\s*([^;}\s]+)', css_text):
            tab_name = match.group(1).strip("[]")
            bg_color = match.group(2).strip()
            if bg_color:
                tab_colors[tab_name] = bg_color

    # collect tab titles (新フォーマット: div.tab)
    for tab in soup.find_all("div", class_="tab"):
        title = tab.find("div", class_="tabtitle")
        if title:
            tt = title.get_text(strip=True)
            if tt not in tabs:
                tabs.append(tt)

    # collect players, colors, and count occurrences
    for p in soup.find_all("p"):
        name = None
        b_tag = p.find("b")
        if b_tag:
            name = b_tag.get_text(strip=True)
        else:
            spans = p.find_all("span")
            if spans and len(spans) >= 2:
                name = spans[1].get_text(strip=True)

        if not name:
            continue

        # Initialize if new player
        if name not in players:
            color = extract_color_from_p_or_spans(p)
            players[name] = {"color": color, "count": 0}

        # Increment count
        players[name]["count"] += 1

        # Also extract tab name from this paragraph (旧フォーマット)
        tab_name = None
        spans = p.find_all("span")
        if spans and len(spans) > 0:
            tab_name = spans[0].get_text(strip=True).strip("[]")

        if tab_name and tab_name not in tabs:
            tabs.append(tab_name)

    return {"players": players, "tabs": tabs, "tab_colors": tab_colors, "html": html}


def extract_roll_lines(file_path):
    """Return a list of roll-containing entries from the HTML.

    Each entry is a dict: {"tab": tab_title_or_None, "name": display_name, "text": text, "rolls": [str,...]}
    """
    # import regex definitions from ccfolia analyzer
    try:
        from analyzer.analyzer_ccfolia import ROLL_RE, D100_FLAG_RE
    except Exception:
        import re
        ROLL_RE = re.compile(r"＞\s*(\d{1,3})")
        D100_FLAG_RE = re.compile(r"1D100", re.IGNORECASE)

    from bs4 import BeautifulSoup

    with open(file_path, "r", encoding="utf-8") as f:
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

        # 名前抽出
        name = None
        spans = p.find_all("span")
        b_tag = p.find("b")
        if spans and len(spans) >= 2:
            name = spans[1].get_text(strip=True)
        elif b_tag:
            name = b_tag.get_text(strip=True)
        if not name:
            name = "不明キャラ"

        tab = p.find_parent("div", class_="tab")
        tag = None
        if tab:
            title = tab.find("div", class_="tabtitle")
            if title:
                tag = title.get_text(strip=True)

        entries.append({"tab": tag, "name": name, "text": text, "rolls": rolls})

    return entries