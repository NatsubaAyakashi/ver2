def build_formatted_html(input_file_path):
    """Build a formatted HTML string from the original input file, applying colors from config.

    This function reads the input HTML, groups content by tab (extracted from span[0] when present),
    and injects a stylesheet that uses colors from `config.players` and `config.tabs`.
    """
    from bs4 import BeautifulSoup
    from config import config
    import re

    with open(input_file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Detect format: look for div.tab (new format) or plain <p> with spans (old format)
    has_div_tabs = soup.find("div", class_="tab") is not None

    if has_div_tabs:
        # New format: div.tab blocks exist
        unique_tabs = []
        for tab in soup.find_all("div", class_="tab"):
            ttitle = tab.find("div", class_="tabtitle")
            if ttitle:
                tt = ttitle.get_text(strip=True)
                if tt not in unique_tabs:
                    unique_tabs.append(tt)
        tabs_structure = None  # will use div.tab structure
    else:
        # Old format: extract tab names from span[0] in <p> tags
        tabs_structure = {}  # {tab_name: [list of <p> elements]}
        unique_tabs = []
        for p in soup.find_all("p"):
            spans = p.find_all("span")
            if spans and len(spans) >= 2:
                tab_name = spans[0].get_text(strip=True).strip(" []")
                if tab_name not in unique_tabs:
                    unique_tabs.append(tab_name)
                if tab_name not in tabs_structure:
                    tabs_structure[tab_name] = []
                tabs_structure[tab_name].append(p)

    # Collect player order and colors
    player_order = []
    player_color_map = {}
    try:
        from analyzer.analyzer_ccfolia import extract_color_from_p_or_spans
    except Exception:
        def extract_color_from_p_or_spans(p):
            return None

    for p in soup.find_all("p"):
        name = None
        b_tag = p.find("b")
        spans = p.find_all("span")
        if spans and len(spans) >= 2:
            name = spans[1].get_text(strip=True)
        elif b_tag:
            name = b_tag.get_text(strip=True)
        if not name:
            continue
        if name not in player_order:
            player_order.append(name)
        # try to get color from HTML first
        c = extract_color_from_p_or_spans(p)
        if c:
            player_color_map[name] = c

    # prefer config colors when present
    for name in list(player_order):
        cfgc = config.get('players', {}).get(name, {}).get('color')
        if cfgc:
            player_color_map[name] = cfgc

    # build detailed CSS similar to sample
    css_lines = [
        "html { font-size: 14px; }",
        f"body {{ -webkit-text-size-adjust: 100%; background-color: {config.get('global_background', '#ffffff')}; }}",
        "h1 { font-size: 20px; margin: 1rem 1rem 0; color: #000; }",
        ".tab { border: 1px solid #999; margin: 2rem 1rem 1rem; line-height: 1.5; position: relative; }",
        ".tabtitle { border: 1px solid transparent; border-color: inherit; background-color: inherit; position: absolute; top: -.8rem; left: 1rem; min-width: 7rem; padding: 0 .5rem; text-align: center; font-size: 1rem; z-index: 9999; line-height: 1.4rem; }",
        ".player { margin: 0; padding: 0 .5rem; padding-left: 10.5rem; border-bottom: 1px dotted transparent; border-color: inherit; position: relative; }",
        ".player:last-child { border-bottom: 0; }",
        ".player b { display: block; height: 100%; width: 9rem; padding: 0 .5rem; border-right: 1px solid transparent; border-color: inherit; position: absolute; top: 0; left: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }",
        ".tabtitle + .player { padding-top: .7rem; }",
        ".tabtitle + .player b { padding-top: .7rem; height: calc(100% - .7rem); }",
        ".diceroll { padding: 0 .5em; color: #ffffff; }",
    ]

    # tab classes (.t0, .t1...) using unique_tabs list order and config
    for idx, t in enumerate(unique_tabs):
        tconf = config.get('tabs', {}).get(t, {})
        bg = tconf.get('background') if tconf else config.get('tab_default_background', '#ffffff')
        border = tconf.get('border') if tconf else config.get('tab_default_border', '#999999')
        color = tconf.get('color') if tconf else '#000'
        font_size = tconf.get('font_size') if tconf else None
        if not bg:
            bg = config.get('tab_default_background', '#ffffff')
        css_lines.append(f"/* [{t}] タブ */")
        css_lines.append(f".t{idx} {{ background-color: {bg}; border-color: {border}; color: {color};{' font-size: ' + font_size + ';' if font_size else ''} }}")

    # player classes
    for idx, name in enumerate(player_order):
        col = player_color_map.get(name, '#888888')
        css_lines.append(f"/* 発言者：{name} */")
        css_lines.append(f".p{idx} {{ color: {col}; }}")
        css_lines.append(f".p{idx} .diceroll {{ background-color: {col}; }}")

    # Build body parts by iterating over ALL div.tab elements (preserving duplicates and order)
    body_parts = []
    import re

    if has_div_tabs:
        # New format: iterate over div.tab elements
        all_tabs = soup.find_all('div', class_='tab')
        for tab_div in all_tabs:
            title_tag = tab_div.find('div', class_='tabtitle')
            t = title_tag.get_text(strip=True) if title_tag else "ログ"
            t_idx = unique_tabs.index(t) if t in unique_tabs else 0
            tab_style = ''
            tconf = config.get('tabs', {}).get(t, {})
            if tconf and tconf.get('background'):
                tab_style = f' style="background-color: {tconf.get("background")};"'
            part = [f'<div class="tab t{t_idx}"{tab_style}>', f'<div class="tabtitle">{t}</div>']
            for p in tab_div.find_all('p', recursive=False):
                b_tag = p.find('b')
                spans = p.find_all('span')
                if spans and len(spans) >= 2:
                    name = spans[1].get_text(strip=True)
                elif b_tag:
                    name = b_tag.get_text(strip=True)
                else:
                    name = ''
                pidx = player_order.index(name) if name in player_order else -1
                pclass = f'p{pidx}' if pidx >= 0 else ''
                part.append(f'<p class="player {pclass}"><b>{name}</b>')
                text = p.get_text("\n", strip=True)
                text = re.sub(r'＞\s*(\d{1,3})', r'＞ <span class="diceroll">\1</span>', text)
                for line in text.splitlines():
                    if line.strip() == name:
                        continue
                    part.append(line + '<br>')
                part.append('</p>')
            part.append('</div>')
            body_parts.append('\n'.join(part))
    else:
        # Old format: process in chronological order, preserving tab transitions and grouping consecutive speakers
        all_p_elements = soup.find_all('p')
        current_tab = None
        current_speaker = None
        current_text_lines = []
        part = None

        for p_elem in all_p_elements:
            spans = p_elem.find_all("span")
            if not spans or len(spans) < 2:
                continue

            tab_name = spans[0].get_text(strip=True).strip(" []")
            speaker_name = spans[1].get_text(strip=True)

            # extract content from span[2] and onwards
            text_parts = []
            for sp in spans[2:]:
                text_parts.append(sp.get_text())
            text = ''.join(text_parts).strip()
            text = re.sub(r'＞\s*(\d{1,3})', r'＞ <span class="diceroll">\1</span>', text)

            # Check if we need to start a new tab block
            if tab_name != current_tab:
                # Save previous speaker block if exists
                if current_speaker is not None and part is not None:
                    part.append(f'<p class="player {current_pclass}"><b>{current_speaker}</b>')
                    for line in current_text_lines:
                        part.append(line + '<br>')
                    part.append('</p>')
                    current_text_lines = []

                # Close previous tab and create new one
                if part is not None:
                    part.append('</div>')
                    body_parts.append('\n'.join(part))

                # Start new tab
                current_tab = tab_name
                t_idx = unique_tabs.index(tab_name) if tab_name in unique_tabs else 0
                tab_style = ''
                tconf = config.get('tabs', {}).get(tab_name, {})
                if tconf and tconf.get('background'):
                    tab_style = f' style="background-color: {tconf.get("background")};"'
                part = [f'<div class="tab t{t_idx}"{tab_style}>', f'<div class="tabtitle">{tab_name}</div>']
                current_speaker = None
                current_text_lines = []

            # Check if speaker changed
            if speaker_name != current_speaker:
                # Save previous speaker block
                if current_speaker is not None:
                    part.append(f'<p class="player {current_pclass}"><b>{current_speaker}</b>')
                    for line in current_text_lines:
                        part.append(line + '<br>')
                    part.append('</p>')
                    current_text_lines = []

                # Start new speaker block
                current_speaker = speaker_name
                pidx = player_order.index(speaker_name) if speaker_name in player_order else -1
                current_pclass = f'p{pidx}' if pidx >= 0 else ''

            # Add text to current speaker's block
            lines = text.replace('<br>', '\n').split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    current_text_lines.append(line)

        # Close final speaker and tab blocks
        if current_speaker is not None and part is not None:
            part.append(f'<p class="player {current_pclass}"><b>{current_speaker}</b>')
            for line in current_text_lines:
                part.append(line + '<br>')
            part.append('</p>')

        if part is not None:
            part.append('</div>')
            body_parts.append('\n'.join(part))

    full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
	<meta charset="UTF-8">
	<title>{config.get('html_title', '整形済みログ')}</title>
	<style>
{chr(10).join('\t\t'+l for l in css_lines)}
	</style>
</head>
<body>
	<h1>{config.get('html_title', '整形済みログ')}</h1>
{chr(10).join('\t'+p for p in body_parts)}
</body>
</html>
"""
    return full_html