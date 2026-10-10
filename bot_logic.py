"""Discord Botの純粋ロジック。

discord.py や ネットワーク、環境変数に依存しないため、ローカルで単体テストできる。
"""
import io
import json
import logging
import re
import zipfile
from typing import NamedTuple

logger = logging.getLogger(__name__)

# 変換前に検査する添付ファイルの上限サイズ
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
# これを超える出力はZIP圧縮する（Discordの通常制限8MBに対する安全マージン）
ZIP_THRESHOLD_BYTES = 7.5 * 1024 * 1024
DEFAULT_AUTO_DELETE_SECONDS = 60

# 許可する色指定は #RGB または #RRGGBB のみ
_COLOR_RE = re.compile(r"#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})")

DEFAULT_SETTINGS = {
    "global_background": "#ffffff",
    "global_color": "#000000",
    "tab_default_background": "#ffffff",
    "tab_default_border": "#999999",
}

PRESETS = {
    "light": {
        "global_background": "#ffffff",
        "global_color": "#000000",
        "tab_default_background": "#ffffff",
        "tab_default_border": "#999999",
        "description": "ライトモード (デフォルト)"
    },
    "dark": {
        "global_background": "#202020",
        "global_color": "#ffffff",
        "tab_default_background": "#333333",
        "tab_default_border": "#555555",
        "description": "ダークモード (目に優しい暗色)"
    },
    "black": {
        "global_background": "#000000",
        "global_color": "#ffffff",
        "tab_default_background": "#000000",
        "tab_default_border": "#444444",
        "description": "ブラックモード (ハイコントラスト)"
    }
}


class ColorCommand(NamedTuple):
    setting_key: str
    example: str
    success_message: str
    preview_filename: str


COLOR_COMMANDS = {
    "!set_bg": ColorCommand(
        "global_background", "#000000",
        "🎨 このサーバーの背景色を `{color}` に設定しました。", "preview_bg.png"),
    "!set_text_color": ColorCommand(
        "global_color", "#ffffff",
        "🎨 このサーバーの文字色を `{color}` に設定しました。", "preview_text_color.png"),
    "!set_tab_bg": ColorCommand(
        "tab_default_background", "#ffffff",
        "🎨 タブのデフォルト背景色を `{color}` に設定しました。", "preview_tab_bg.png"),
    "!set_tab_border": ColorCommand(
        "tab_default_border", "#999999",
        "🎨 タブのデフォルトボーダー色を `{color}` に設定しました。", "preview_tab_border.png"),
}


class OutputFile(NamedTuple):
    data: bytes
    filename: str
    zipped: bool


def is_valid_color(value) -> bool:
    """#RGB または #RRGGBB のみ True。"""
    return isinstance(value, str) and _COLOR_RE.fullmatch(value) is not None


def color_or_default(value, key):
    """検証に通る色のみ返し、不正ならそのキーの既定色を返す。"""
    return value if is_valid_color(value) else DEFAULT_SETTINGS[key]


def parse_command(content):
    """メッセージ本文を (コマンド, 引数リスト) に分割する。空なら (None, [])。"""
    parts = (content or "").split()
    if not parts:
        return None, []
    return parts[0], parts[1:]


def get_guild_key(guild_id):
    """サーバーIDから設定キーを返す（DMは 'dm'）。"""
    return str(guild_id) if guild_id is not None else "dm"


def apply_color_setting(cache, guild_key, setting_key, color) -> bool:
    """色が正しい場合のみ設定を反映する。不正なら何も変更せず False を返す。"""
    if setting_key not in DEFAULT_SETTINGS or not is_valid_color(color):
        return False
    cache.setdefault(guild_key, {})[setting_key] = color
    return True


def apply_preset(cache, guild_key, preset_name):
    """プリセットを反映してプリセット定義を返す。存在しなければ None。"""
    preset = PRESETS.get(preset_name)
    if preset is None:
        return None
    guild_config = cache.setdefault(guild_key, {})
    for key in DEFAULT_SETTINGS:
        guild_config[key] = preset[key]
    return preset


def reset_guild_settings(cache, guild_key) -> bool:
    """サーバー設定を削除する。設定があった場合のみ True。"""
    if guild_key in cache:
        del cache[guild_key]
        return True
    return False


def parse_auto_delete_seconds(text) -> int:
    """自動削除秒数を解釈する。0以上の整数以外は ValueError。"""
    seconds = int(text)
    if seconds < 0:
        raise ValueError("negative seconds")
    return seconds


def apply_auto_delete_time(cache, guild_key, seconds):
    cache.setdefault(guild_key, {})["auto_delete_time"] = seconds


def get_auto_delete_time(guild_config) -> int:
    value = guild_config.get("auto_delete_time", DEFAULT_AUTO_DELETE_SECONDS)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return DEFAULT_AUTO_DELETE_SECONDS
    return value


def build_bot_settings(guild_config, filename) -> dict:
    """サーバー設定から renderer 用の設定dictを組み立てる。不正な保存値は既定値に戻す。"""
    colors = {key: color_or_default(guild_config.get(key), key) for key in DEFAULT_SETTINGS}
    return {
        **colors,
        "html_title": f"Converted: {filename}",
        "tabs": {},
        "players": {},
    }


def is_html_filename(filename) -> bool:
    return isinstance(filename, str) and filename.lower().endswith(".html")


def is_attachment_too_large(size) -> bool:
    """変換前のサイズ検査。サイズ不明(None)や不正値は安全側で拒否する。"""
    return not isinstance(size, int) or size < 0 or size > MAX_ATTACHMENT_BYTES


def display_filename(filename, max_length=100) -> str:
    """メッセージ表示用に、Markdownや改行を壊す文字を除いてファイル名を整える。"""
    cleaned = re.sub(r"[`\r\n]", "_", str(filename))
    return cleaned if len(cleaned) <= max_length else cleaned[:max_length] + "…"


def package_output(html_text, original_filename) -> OutputFile:
    """変換結果をバイト列にし、大きい場合はZIP圧縮して返す。"""
    html_bytes = html_text.encode("utf-8")
    send_filename = f"formatted_{original_filename}"
    if len(html_bytes) <= ZIP_THRESHOLD_BYTES:
        return OutputFile(html_bytes, send_filename, False)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(send_filename, html_bytes)
    return OutputFile(buffer.getvalue(), send_filename + ".zip", True)


def load_settings(path) -> dict:
    """サーバー設定JSONを読み込む。存在しない・不正な場合は空dict。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        logger.exception("設定読み込みエラー: %s", path)
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(path, settings) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        logger.exception("設定保存エラー: %s", path)
        return False
