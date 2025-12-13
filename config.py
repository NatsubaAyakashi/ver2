import json
from pathlib import Path

CONFIG_FILE = Path("config.json")

DEFAULT_CONFIG = {
    "html_title": "整形済みログ",
    "global_background": "#ffffff",
    "tab_default_background": "#ffffff",
    "tab_default_border": "#999999",
    "players": {},
    "tabs": {},
}

def load_config():
    """設定ファイルを読み込む。ファイルがなければデフォルト値を返す。"""
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            try:
                # デフォルト値とマージして、新しいキーに対応
                user_config = json.load(f)
                config_data = DEFAULT_CONFIG.copy()
                config_data.update(user_config)
                return config_data
            except (json.JSONDecodeError, TypeError):
                return DEFAULT_CONFIG.copy() # ファイルが不正な場合はデフォルト
    return DEFAULT_CONFIG.copy()

def save_config(data):
    """設定をファイルに保存する。"""
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# アプリケーション起動時に設定を読み込む
config = load_config()