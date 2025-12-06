# config.py
# Ver2 初期設定（解析オプションのデフォルトを含む）

config = {
    "global_background": "#ffffff",  # 全体背景色
    "html_title": "ゆめうつつ",      # 出力HTML のタイトル（<title> と <h1>）
    "tabs": {},                        # タブは解析時に追加
    "players": {},                     # プレイヤーは解析時に追加
    "tab_default_background": "#ffffff",  # タブのデフォルト背景色
    "tab_default_border": "#999999",     # タブのデフォルトボーダー色

    # 解析オプション（デフォルト）
    "exclude_tags": [],                # 除外するタブタイトル名のリスト
    "min_rolls": 1,                    # 判定数がこれ未満のキャラは集計対象外
    "show_skill_stats": True,          # 技能別集計を表示するか
    "show_unknown_details": True      # 不明技能の詳細表示を行うか
}