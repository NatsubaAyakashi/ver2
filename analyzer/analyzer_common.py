import re
import unicodedata

# 集計用：全角半角・空白を揃える
def normalize_name(name: str) -> str:
    if not name:
        return "不明キャラ"
    normalized = unicodedata.normalize("NFKC", name).strip()
    return normalized

# 表示用：括弧を除去して見やすく
def display_name(name: str) -> str:
    if not name:
        return "不明キャラ"
    normalized = unicodedata.normalize("NFKC", name).strip()
    return re.sub(r"[\(（].*?[\)）]", "", normalized).strip()

# 技能名抽出
def extract_skill_name(text: str) -> str:
    # 【技能】形式
    m = re.search(r"【\s*(.+?)\s*】", text)
    if m:
        return m.group(1).strip()

    # CCB<=xx 技能名形式（xxが分数でもOK）
    m = re.search(r"CCB<=[\d/+\-*]+(?:\s*[-+*/]\s*\d+)?\s+([^\[\(＞\n\r]{2,})", text)
    if m:
        return m.group(1).strip()  # /3 などもそのまま返す → 別技能扱い

    # 能力値×n形式 (STR×3, DEX*2, INTx5, INT×3-10 など)
    m = re.search(r"(STR|DEX|INT|POW|CON|APP|SIZ|EDU|SAN)\s*[\*×x]\s*[\d\-]+", text, re.IGNORECASE)
    if m:
        return m.group(0).strip()

    # 正気度ロール
    if "正気度" in text:
        return "正気度ロール"

    # アイデア
    if "アイデア" in text:
        return "アイデア"

    # 幸運
    if "幸運" in text:
        return "幸運"

    return "不明技能"

# 全角対応で幅揃え
def pad_zen(text: str, width: int) -> str:
    count = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    pad = max(0, width - count)
    return text + " " * pad