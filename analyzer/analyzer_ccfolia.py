import re
from collections import defaultdict
from bs4 import BeautifulSoup
from analyzer.analyzer_common import normalize_name, display_name, extract_skill_name, pad_zen

ROLL_RE = re.compile(r"＞\s*(\d{1,3})")
D100_FLAG_RE = re.compile(r"1D100", re.IGNORECASE)
COLOR_RE = re.compile(r"color\s*:\s*(#[0-9A-Fa-f]{6})")

def extract_color_from_p_or_spans(p):
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

def analyze_ccfolia(content, config):
    stats = defaultdict(lambda: {"total":0, "critical":0, "fumble":0})
    skill_stats = defaultdict(lambda: defaultdict(lambda: {"total":0, "critical":0, "fumble":0, "raw_names": set()}))
    unknown_skills = []
    colored_entries = []
    display_names = {}
    character_colors = {}

    soup = BeautifulSoup(content, "html.parser")

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

        norm_name = normalize_name(name)
        disp_name = display_name(name)
        if norm_name not in display_names:
            display_names[norm_name] = disp_name

        # 色抽出
        color = extract_color_from_p_or_spans(p)
        if color and disp_name not in character_colors:
            character_colors[disp_name] = color

        # タグ抽出
        tag = None
        if spans and len(spans) >= 1:
            tag = spans[0].get_text(strip=True).strip(" []")
        tab = p.find_parent("div", class_="tab")
        if tab:
            title = tab.find("div", class_="tabtitle")
            if title:
                tag = title.get_text(strip=True)
        if config["exclude_tags"] and tag in config["exclude_tags"]:
            continue

        # 技能名抽出
        skill_name = extract_skill_name(text)
        raw_name = skill_name
        if len(skill_name.strip()) <= 1:
            skill_name = "不明技能"
            raw_name = "不明技能"

        has_crit = False
        has_fumble = False
        for roll_str in rolls:
            roll = int(roll_str)
            s = stats[norm_name]
            s["total"] += 1
            if 1 <= roll <= 5:
                s["critical"] += 1
                has_crit = True
            elif 96 <= roll <= 100:
                s["fumble"] += 1
                has_fumble = True

            ss = skill_stats[norm_name][skill_name]
            ss["total"] += 1
            ss["raw_names"].add(raw_name)
            if 1 <= roll <= 5:
                ss["critical"] += 1
            elif 96 <= roll <= 100:
                ss["fumble"] += 1

        if skill_name == "不明技能" and (has_crit or has_fumble):
            entry = {"name": norm_name, "tag": tag, "rolls": rolls, "text": text}
            colored_entries.append(entry)
            unknown_skills.append(entry)

    # キャラ毎集計
    pl_stats = {n:d for n,d in stats.items() if d["total"] >= config["min_rolls"]}
    result = []
    result.append("=== 集計結果（キャラ毎） ===")
    if not pl_stats:
        result.append("集計結果なし")
    else:
        result.append(
            f"{pad_zen('名前', 16)}  {pad_zen('判定数', 8)}  {pad_zen('クリティカル', 12)}  {pad_zen('ファンブル', 10)}  {pad_zen('クリ率', 8)}  {pad_zen('ファン率', 8)}"
        )
        result.append("-"*72)
        for n, d in pl_stats.items():
            name_out = display_names.get(n, n)
            total, crit, fumble = d["total"], d["critical"], d["fumble"]
            crit_rate = crit/total*100 if total else 0
            fumble_rate = fumble/total*100 if total else 0
            result.append(
                f"{pad_zen(name_out, 16)}  "
                f"{str(total).rjust(8)}  "
                f"{str(crit).rjust(12)}  "
                f"{str(fumble).rjust(10)}  "
                f"{f'{crit_rate:.2f}'.rjust(8)}  "
                f"{f'{fumble_rate:.2f}'.rjust(8)}"
            )

    # 技能別集計
    if config["show_skill_stats"]:
        result.append("\n=== 技能別集計（キャラ毎） ===")
        for n in pl_stats.keys():
            name_out = display_names.get(n, n)
            skills = skill_stats.get(n, {})
            if not skills:
                continue
            result.append(f"\n{name_out} の技能判定：")
            result.append(
                f"{pad_zen('技能名', 20)}  {pad_zen('判定数', 8)}  {pad_zen('クリティカル', 12)}  {pad_zen('ファンブル', 10)}"
            )
            result.append("-"*60)
            for skill, sdata in skills.items():
                # 修正後: クリファンが1以上なら表示
                if sdata["critical"] == 0 and sdata["fumble"] == 0:
                    continue
                raw_display = next(iter(sdata["raw_names"])) if sdata["raw_names"] else skill
                result.append(
                    f"{pad_zen(raw_display, 20)}  "
                    f"{str(sdata['total']).rjust(8)}  "
                    f"{str(sdata['critical']).rjust(12)}  "
                    f"{str(sdata['fumble']).rjust(10)}"
                )

    # 不明技能詳細
    if config["show_unknown_details"]:
        result.append("\n=== 不明技能詳細（キャラ毎） ===")
        filtered = [
            u for u in unknown_skills
            if u["name"] in pl_stats and (not config["exclude_tags"] or u["tag"] not in config["exclude_tags"])
        ]
        if not filtered:
            result.append("不明技能なし")
        else:
            for u in filtered:
                name_out = display_names.get(u["name"], u["name"])
                result.append(f"{name_out} ({u['tag']}) ＞ {','.join(u['rolls'])} {u['text']}")

    return {
        "summary_text": "\n".join(result),
        "colored_entries": colored_entries,
        "character_colors": character_colors,
        "display_names": display_names
    }