import html
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# プロジェクトルートをパスに追加してモジュール検索できるようにする
# resolve() を使うことで絶対パスを取得し、実行場所によるパスずれを防ぐ
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from analyzer.analyzer import extract_color_from_p_or_spans

# CSSへ埋め込む値の検証用。許可形式以外は既定値へフォールバックする
_CSS_COLOR_RE = re.compile(
    r"^(?:#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})"
    r"|(?:rgb|hsl)a?\(\s*[\d.]+%?(?:\s*,\s*[\d.]+%?){2,3}\s*\)"
    r"|[A-Za-z]{3,30})$"
)
_CSS_FONT_SIZE_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3})?(?:px|pt|em|rem|%)$")

def _esc(value):
    """表示用テキストとしてHTMLエスケープする（属性値にも使える）。"""
    return html.escape(str(value), quote=True)

def _safe_color(value, default=None):
    """検証済みのCSS色のみ返す。不正な値はdefaultを返す。"""
    if isinstance(value, str):
        value = value.strip()
        if _CSS_COLOR_RE.match(value):
            return value
    return default

def _safe_font_size(value):
    if isinstance(value, str) and _CSS_FONT_SIZE_RE.match(value.strip()):
        return value.strip()
    return None

def _css_comment_text(value):
    """CSSコメントに埋め込む文字列から、コメント終端・改行・HTML特殊文字（</style>等）を除く。"""
    text = re.sub(r"\s+", " ", str(value).replace("*/", "* /").replace("/*", "/ *"))
    return html.escape(text, quote=True)

def _setting_color(settings, key, default):
    return _safe_color(settings.get(key), default)

def build_formatted_html(input_file_path, settings=None):
    """
    入力ファイルを読み込み、設定に基づいて整形されたHTML文字列を生成して返す。
    （build_formatted_html_from_string のファイル読み込み付きラッパー）
    """
    with open(input_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return build_formatted_html_from_string(html_content, settings)

def build_formatted_html_from_string(html_content, settings=None):
    """
    ログHTMLの文字列を受け取り、設定に基づいて整形されたHTML文字列を生成して返す。
    """
    # 設定が渡されていない場合はconfig.pyから読み込む
    if settings is None:
        from config import config as settings

    soup = BeautifulSoup(html_content, "html.parser")

    # フォーマット判定: div.tab があるかどうか
    has_div_tabs = soup.find("div", class_="tab") is not None

    # 1. データ抽出フェーズ（タブ一覧、プレイヤー一覧、色）
    unique_tabs = _extract_unique_tabs(soup, has_div_tabs)
    player_order, player_color_map = _extract_players_and_colors(soup, settings)

    # 2. CSS生成フェーズ
    css_lines = _generate_css(settings, unique_tabs, player_order, player_color_map)

    # 3. Body生成フェーズ
    if has_div_tabs:
        body_parts = _build_body_new_format(soup, unique_tabs, player_order, settings)
    else:
        body_parts = _build_body_old_format(soup, unique_tabs, player_order, settings)

    # f-string内でのバックスラッシュ使用回避のため、事前に結合する
    css_content = '\n'.join('\t\t' + l for l in css_lines)
    body_content = '\n'.join('\t' + p for p in body_parts)

    # 4. HTML結合フェーズ
    title = _esc(settings.get('html_title', '整形済みログ'))
    full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
\t<meta charset="UTF-8">
\t<meta name="viewport" content="width=device-width, initial-scale=1.0">
\t<title>{title}</title>
\t<style>
{css_content}
\t</style>
</head>
<body>
\t<h1>{title}</h1>
{body_content}
</body>
</html>
"""
    return full_html

def _extract_unique_tabs(soup, has_div_tabs):
    """HTMLからユニークなタブ名のリストを抽出する"""
    unique_tabs = []
    if has_div_tabs:
        # 新フォーマット: div.tab から抽出
        for tab in soup.find_all("div", class_="tab"):
            ttitle = tab.find("div", class_="tabtitle")
            if ttitle:
                tt = ttitle.get_text(strip=True)
                if tt not in unique_tabs:
                    unique_tabs.append(tt)
    else:
        # 旧フォーマット: p > span[0] から抽出
        for p in soup.find_all("p"):
            spans = p.find_all("span")
            if spans and len(spans) >= 2:
                tab_name = spans[0].get_text(strip=True).strip(" []")
                if tab_name not in unique_tabs:
                    unique_tabs.append(tab_name)
    return unique_tabs

def _extract_players_and_colors(soup, settings):
    """プレイヤーの順序リストと色マップを抽出する"""
    player_order = []
    player_color_map = {}

    for p in soup.find_all("p"):
        name = _extract_player_name(p)
        if not name:
            continue
        if name not in player_order:
            player_order.append(name)

        # HTML内の色情報を取得
        c = _safe_color(extract_color_from_p_or_spans(p))
        if c:
            player_color_map[name] = c

    # 設定ファイルの色情報を優先適用
    for name in player_order:
        cfgc = _safe_color(settings.get('players', {}).get(name, {}).get('color'))
        if cfgc:
            player_color_map[name] = cfgc

    return player_order, player_color_map

def _extract_player_name(p_tag):
    """pタグからプレイヤー名を抽出するヘルパー関数"""
    b_tag = p_tag.find("b")
    spans = p_tag.find_all("span")
    if spans and len(spans) >= 2:
        return spans[1].get_text(strip=True)
    elif b_tag:
        return b_tag.get_text(strip=True)
    return None

def _generate_css(settings, unique_tabs, player_order, player_color_map):
    """CSS定義のリストを生成する"""
    global_bg = _setting_color(settings, 'global_background', '#ffffff')
    global_color = _setting_color(settings, 'global_color', '#000000')
    tab_default_bg = _setting_color(settings, 'tab_default_background', '#ffffff')
    tab_default_border = _setting_color(settings, 'tab_default_border', '#999999')

    css_lines = [
        "html { font-size: 14px; }",
        f"body {{ -webkit-text-size-adjust: 100%; background-color: {global_bg}; color: {global_color}; }}",
        f"h1 {{ font-size: 20px; margin: 1rem 1rem 0; color: {global_color}; }}",
        ".tab { border: 1px solid #999; margin: 2rem 1rem 1rem; line-height: 1.5; position: relative; }",
        ".tabtitle { border: 1px solid transparent; border-color: inherit; background-color: inherit; position: absolute; top: -.8rem; left: 1rem; min-width: 7rem; padding: 0 .5rem; text-align: center; font-size: 1rem; z-index: 9999; line-height: 1.4rem; }",
        ".player { margin: 0; padding: 0 .5rem; padding-left: 10.5rem; border-bottom: 1px dotted transparent; border-color: inherit; position: relative; }",
        ".player:last-child { border-bottom: 0; }",
        ".player b { display: block; height: 100%; width: 9rem; padding: 0 .5rem; border-right: 1px solid transparent; border-color: inherit; position: absolute; top: 0; left: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }",
        ".tabtitle + .player { padding-top: .7rem; }",
        ".tabtitle + .player b { padding-top: .7rem; height: calc(100% - .7rem); }",
        ".diceroll { padding: 0 .5em; color: #ffffff; }",
        "@media screen and (max-width: 600px) {",
        "\thtml { font-size: 12px; }",
        "\t.tab { margin: 2rem 0.2rem 1rem; }",
        "\t.player { padding-left: 7rem; }",
        "\t.player b { width: 6rem; }",
        "}",
    ]

    # タブごとのスタイル
    for idx, t in enumerate(unique_tabs):
        tconf = settings.get('tabs', {}).get(t, {})
        bg = _safe_color(tconf.get('background'), tab_default_bg) if tconf else tab_default_bg
        border = _safe_color(tconf.get('border'), tab_default_border) if tconf else tab_default_border
        color = _safe_color(tconf.get('color'), global_color) if tconf else global_color
        font_size = _safe_font_size(tconf.get('font_size')) if tconf else None
        css_lines.append(f"/* [{_css_comment_text(t)}] タブ */")
        css_lines.append(f".t{idx} {{ background-color: {bg}; border-color: {border}; color: {color};{' font-size: ' + font_size + ';' if font_size else ''} }}")

    # プレイヤーごとのスタイル
    for idx, name in enumerate(player_order):
        col = player_color_map.get(name, '#888888')
        css_lines.append(f"/* 発言者：{_css_comment_text(name)} */")
        css_lines.append(f".p{idx} {{ color: {col}; }}")
        css_lines.append(f".p{idx} .diceroll {{ background-color: {col}; }}")

    return css_lines

def _tab_style_attr(settings, tab_name):
    """タブ個別の背景色が設定されていれば、検証済みのstyle属性文字列を返す。"""
    tconf = settings.get('tabs', {}).get(tab_name, {})
    bg = _safe_color(tconf.get('background')) if tconf else None
    return f' style="background-color: {bg};"' if bg else ''

def _build_body_new_format(soup, unique_tabs, player_order, settings):
    """新フォーマット(div.tab)のHTMLボディを生成"""
    body_parts = []
    all_tabs = soup.find_all('div', class_='tab')

    for tab_div in all_tabs:
        title_tag = tab_div.find('div', class_='tabtitle')
        t = title_tag.get_text(strip=True) if title_tag else "ログ"
        t_idx = unique_tabs.index(t) if t in unique_tabs else 0

        # タブのスタイル設定
        tab_style = _tab_style_attr(settings, t)

        part = [f'<div class="tab t{t_idx}"{tab_style}>', f'<div class="tabtitle">{_esc(t)}</div>']

        for p in tab_div.find_all('p', recursive=False):
            name = _extract_player_name(p) or ''
            pidx = player_order.index(name) if name in player_order else -1
            pclass = f'p{pidx}' if pidx >= 0 else ''

            # 行ごとの色を取得し、あればstyle属性に設定
            p_color = _safe_color(extract_color_from_p_or_spans(p))
            style_attr = f' style="color: {p_color};"' if p_color else ''

            escaped_name = _esc(name)
            part.append(f'<p class="player {pclass}"{style_attr}><b>{escaped_name}</b>')
            text = _esc(p.get_text("\n", strip=True))
            text = re.sub(r'＞\s*(\d{1,3})', r'＞ <span class="diceroll">\1</span>', text)

            for line in text.splitlines():
                if line.strip() == escaped_name:
                    continue
                part.append(line + '<br>')
            part.append('</p>')

        part.append('</div>')
        body_parts.append('\n'.join(part))
    return body_parts

def _build_body_old_format(soup, unique_tabs, player_order, settings):
    """旧フォーマット(p span)のHTMLボディを生成"""
    body_parts = []
    all_p_elements = soup.find_all('p')
    current_tab = None
    current_speaker = None
    current_color = None
    current_pclass = ''
    current_text_lines = []
    part = None

    for p_elem in all_p_elements:
        spans = p_elem.find_all("span")
        if not spans or len(spans) < 2:
            continue

        tab_name = spans[0].get_text(strip=True).strip(" []")
        speaker_name = spans[1].get_text(strip=True)

        # 本文の抽出
        text_parts = [sp.get_text() for sp in spans[2:]]
        text = _esc(''.join(text_parts).strip())
        text = re.sub(r'＞\s*(\d{1,3})', r'＞ <span class="diceroll">\1</span>', text)

        # この行の色を取得
        this_color = _safe_color(extract_color_from_p_or_spans(p_elem))

        # タブが変わった場合
        if tab_name != current_tab:
            # 前のスピーカーブロックを閉じる
            if current_speaker is not None and part is not None:
                style_attr = f' style="color: {current_color};"' if current_color else ''
                part.append(f'<p class="player {current_pclass}"{style_attr}><b>{_esc(current_speaker)}</b>')
                for line in current_text_lines:
                    part.append(line + '<br>')
                part.append('</p>')
                current_text_lines = []

            # 前のタブブロックを閉じる
            if part is not None:
                part.append('</div>')
                body_parts.append('\n'.join(part))

            # 新しいタブを開始
            current_tab = tab_name
            t_idx = unique_tabs.index(tab_name) if tab_name in unique_tabs else 0
            tab_style = _tab_style_attr(settings, tab_name)
            part = [f'<div class="tab t{t_idx}"{tab_style}>', f'<div class="tabtitle">{_esc(tab_name)}</div>']
            current_speaker = None
            current_color = None
            current_text_lines = []

        # スピーカーが変わった場合、または色が変わった場合
        if speaker_name != current_speaker or this_color != current_color:
            # 前のスピーカーブロックを閉じる
            if current_speaker is not None and part is not None:
                style_attr = f' style="color: {current_color};"' if current_color else ''
                part.append(f'<p class="player {current_pclass}"{style_attr}><b>{_esc(current_speaker)}</b>')
                for line in current_text_lines:
                    part.append(line + '<br>')
                part.append('</p>')
                current_text_lines = []

            # 新しいスピーカーを開始
            current_speaker = speaker_name
            current_color = this_color
            pidx = player_order.index(speaker_name) if speaker_name in player_order else -1
            current_pclass = f'p{pidx}' if pidx >= 0 else ''

        # テキストを追加
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line:
                current_text_lines.append(line)

    # 最後のブロックを閉じる
    if current_speaker is not None and part is not None:
        style_attr = f' style="color: {current_color};"' if current_color else ''
        part.append(f'<p class="player {current_pclass}"{style_attr}><b>{_esc(current_speaker)}</b>')
        for line in current_text_lines:
            part.append(line + '<br>')
        part.append('</p>')

    if part is not None:
        part.append('</div>')
        body_parts.append('\n'.join(part))

    return body_parts