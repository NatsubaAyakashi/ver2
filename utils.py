import re

def normalize_name(name: str) -> str:
    # キャラ名から全角・半角のフリガナを除去
    return re.sub(r"[（(][^）)]+[）)]", "", name).strip()

def clean_skill_name(name: str) -> str:
    # 記号・演算子・数字・空白を除去（例：STR*3 → STR）
    return re.sub(r"[*/×÷／・\d\s\-]+", "", name).strip()

def extract_skill_name(text: str) -> str:
    # 【技能名】形式を優先
    bracket_re = re.compile(r"【\s*(.+?)】")
    # CCB<=数式 技能名 の形式に対応（数式混在でも技能名を拾う）
    ccb_re = re.compile(r"CCB<=.*?\s+([^\[\(＞\n\r]{2,})")
    
    m = bracket_re.search(text)
    if m:
        return clean_skill_name(m.group(1).strip())
    
    m2 = ccb_re.search(text)
    if m2:
        return clean_skill_name(m2.group(1).strip())
    
    return "不明技能"