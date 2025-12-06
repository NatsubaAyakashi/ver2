import tkinter as tk
from tkinter import colorchooser
from config import config
import controller
from controller import re_run_analysis

def open_settings(root):
    """Main settings dialog showing tabs, frequently-appearing players, and detailed players."""
    win = tk.Toplevel(root)
    win.title("色・設定")
    win.grab_set()
    win.geometry("700x600")

    # スクロール可能な領域を作る
    container = tk.Frame(win)
    container.pack(fill='both', expand=True)
    canvas = tk.Canvas(container)
    vscroll = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
    vscroll.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=vscroll.set)
    inner = tk.Frame(canvas)
    canvas.create_window((0, 0), window=inner, anchor='nw')
    def _on_config(e):
        canvas.configure(scrollregion=canvas.bbox('all'))
    inner.bind('<Configure>', _on_config)

    # マウスホイールでスクロール（ウィンドウクローズ時に自動削除）
    def _on_mousewheel(event):
        try:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        except Exception:
            pass

    canvas.bind('<MouseWheel>', _on_mousewheel)
    canvas.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
    canvas.bind('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

    def cleanup_bindings():
        """ウィンドウクローズ時にバインドをクリア"""
        canvas.unbind('<MouseWheel>')
        canvas.unbind('<Button-4>')
        canvas.unbind('<Button-5>')

    win.protocol("WM_DELETE_WINDOW", lambda: (cleanup_bindings(), win.destroy()))

    # 全体背景色（上部に配置）
    tk.Label(inner, text="全体背景色").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    bg_var = tk.StringVar(inner, value=config.get("global_background", ""))
    tk.Entry(inner, textvariable=bg_var, width=10).grid(row=0, column=1)
    tk.Button(inner, text="選択", command=lambda: choose_color(bg_var)).grid(row=0, column=2)

    # 行カウンタ
    row_counter = {'r': 1}

    def make_section(title):
        """折りたたみ可能なセクションを作る"""
        hdr = tk.Frame(inner)
        r = row_counter['r']
        hdr.grid(row=r, column=0, columnspan=3, sticky='we', pady=(8,0), padx=4)
        lbl = tk.Label(hdr, text=title, font=('Arial', 10, 'bold'))
        lbl.pack(side='left')
        toggle = tk.Button(hdr, text='−', width=2)
        toggle.pack(side='left', padx=6)
        row_counter['r'] += 1
        content = tk.Frame(inner, relief='flat', borderwidth=0)
        content.grid(row=row_counter['r'], column=0, columnspan=3, sticky='we', padx=8)
        collapsed = {'state': False}
        def _toggle():
            if collapsed['state']:
                content.grid()
                toggle.config(text='−')
                collapsed['state'] = False
            else:
                content.grid_remove()
                toggle.config(text='+')
                collapsed['state'] = True
        toggle.config(command=_toggle)
        row_counter['r'] += 1
        return content, toggle, collapsed

    def make_section_collapsed(title):
        """折りたたみ可能なセクションを作る（デフォルトで閉じた状態）"""
        hdr = tk.Frame(inner)
        r = row_counter['r']
        hdr.grid(row=r, column=0, columnspan=3, sticky='we', pady=(8,0), padx=4)
        lbl = tk.Label(hdr, text=title, font=('Arial', 10, 'bold'))
        lbl.pack(side='left')
        toggle = tk.Button(hdr, text='+', width=2)
        toggle.pack(side='left', padx=6)
        row_counter['r'] += 1
        content = tk.Frame(inner, relief='flat', borderwidth=0)
        content.grid(row=row_counter['r'], column=0, columnspan=3, sticky='we', padx=8)
        content.grid_remove()  # 初期状態で非表示
        collapsed = {'state': True}
        def _toggle():
            if collapsed['state']:
                content.grid()
                toggle.config(text='−')
                collapsed['state'] = False
            else:
                content.grid_remove()
                toggle.config(text='+')
                collapsed['state'] = True
        toggle.config(command=_toggle)
        row_counter['r'] += 1
        return content, toggle, collapsed

    def add_color_item(parent, name, initial_color, var_map):
        """色設定アイテムを追加"""
        row = tk.Frame(parent)
        row.pack(fill='x', pady=2)
        name_lbl = tk.Label(row, text=name, width=32, anchor='w')
        name_lbl.pack(side='left')
        v = tk.StringVar(row, value=initial_color or "")
        ent = tk.Entry(row, textvariable=v, width=12)
        ent.pack(side='left', padx=6)
        btn = tk.Button(row, text='選択', command=lambda vv=v: choose_color(vv))
        btn.pack(side='left')
        sw = tk.Label(row, text='   ', bg=(initial_color or row.cget('bg')))
        sw.pack(side='left', padx=6)
        # 変更時にスウォッチ更新
        def _update_sw(*args):
            try:
                col = v.get()
                if col:
                    sw.config(bg=col)
                else:
                    sw.config(bg=row.cget('bg'))
            except Exception:
                pass
        v.trace_add('write', _update_sw)
        var_map[name] = v

    tab_vars = {}
    player_vars = {}
    struct = getattr(controller, 'current_structure', None)
    tabs = struct.get('tabs', []) if struct else []
    players = struct.get('players', {}) if struct else {}
    tab_colors = struct.get('tab_colors', {}) if struct else {}

    # タブセクション
    if tabs:
        tab_section, _, _ = make_section('タブ色・ボーダー')
        for t in tabs:
            # タブの色設定フレーム
            t_frame = tk.Frame(tab_section)
            t_frame.pack(fill='x', pady=4)

            t_label = tk.Label(t_frame, text=t, width=20, anchor='w', font=('Arial', 9, 'bold'))
            t_label.pack(side='left')

            # 背景色
            bg_label = tk.Label(t_frame, text='背景:', width=4)
            bg_label.pack(side='left', padx=(6, 0))
            bg_initial = tab_colors.get(t) or config.get('tabs', {}).get(t, {}).get('background', '') or config.get('tab_default_background', '#ffffff')
            bg_var = tk.StringVar(t_frame, value=bg_initial)
            bg_entry = tk.Entry(t_frame, textvariable=bg_var, width=10)
            bg_entry.pack(side='left', padx=2)
            bg_btn = tk.Button(t_frame, text='選択', command=lambda v=bg_var: choose_color(v))
            bg_btn.pack(side='left')
            bg_swatch = tk.Label(t_frame, text='   ', bg=bg_initial)
            bg_swatch.pack(side='left', padx=2)

            # 背景色変更時にスウォッチ更新
            def _update_bg_swatch(v, sw, *args):
                try:
                    col = v.get()
                    if col:
                        sw.config(bg=col)
                except Exception:
                    pass
            bg_var.trace_add('write', lambda *args, v=bg_var, sw=bg_swatch: _update_bg_swatch(v, sw))

            # ボーダー色
            border_label = tk.Label(t_frame, text='ボーダー:', width=8)
            border_label.pack(side='left', padx=(12, 0))
            border_initial = config.get('tabs', {}).get(t, {}).get('border', '') or config.get('tab_default_border', '#999999')
            border_var = tk.StringVar(t_frame, value=border_initial)
            border_entry = tk.Entry(t_frame, textvariable=border_var, width=10)
            border_entry.pack(side='left', padx=2)
            border_btn = tk.Button(t_frame, text='選択', command=lambda v=border_var: choose_color(v))
            border_btn.pack(side='left')
            border_swatch = tk.Label(t_frame, text='   ', bg=border_initial)
            border_swatch.pack(side='left', padx=2)

            # ボーダー色変更時にスウォッチ更新
            def _update_border_swatch(v, sw, *args):
                try:
                    col = v.get()
                    if col:
                        sw.config(bg=col)
                except Exception:
                    pass
            border_var.trace_add('write', lambda *args, v=border_var, sw=border_swatch: _update_border_swatch(v, sw))

            # 変数マップに保存（キーは "タブ名_background" と "タブ名_border" の形式）
            tab_vars[f"{t}_background"] = bg_var
            tab_vars[f"{t}_border"] = border_var

    # プレイヤーセクション（出現回数でソート）
    sorted_players = sorted(
        players.items(),
        key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0,
        reverse=True
    )

    # 上位10人をメインセクションにし、それ以外を詳細セクションへ
    top_n = 10
    main_players = [ (n,i) for n,i in sorted_players if isinstance(i, dict) ][:top_n]
    detail_players = [ (n,i) for n,i in sorted_players if isinstance(i, dict) ][top_n:]

    if main_players:
        player_section = make_section('プレイヤー色')[0]
        for name, info in main_players:
            initial = config.get('players', {}).get(name, {}).get('color', info.get('color') or '')
            add_color_item(player_section, name, initial, player_vars)

    if detail_players:
        detail_section, _, _ = make_section_collapsed('詳細 - 低頻出プレイヤー')
        for name, info in detail_players:
            initial = config.get('players', {}).get(name, {}).get('color', info.get('color') or '')
            add_color_item(detail_section, name, initial, player_vars)

    def save():
        config["global_background"] = bg_var.get()
        # save tab colors (both background and border)
        for key, v in tab_vars.items():
            if '_background' in key:
                tname = key.replace('_background', '')
            elif '_border' in key:
                tname = key.replace('_border', '')
            else:
                continue

            if 'tabs' not in config:
                config['tabs'] = {}
            if tname not in config['tabs']:
                config['tabs'][tname] = {}

            if '_background' in key and v.get().strip():
                config['tabs'][tname]['background'] = v.get().strip()
            elif '_border' in key and v.get().strip():
                config['tabs'][tname]['border'] = v.get().strip()

        # save player colors
        if 'players' not in config:
            config['players'] = {}
        for pname, v in player_vars.items():
            if pname not in config['players']:
                config['players'][pname] = {}
            if v.get().strip():
                config['players'][pname]['color'] = v.get().strip()

        # re-run analysis to refresh stored structure
        cleanup_bindings()
        win.destroy()
        re_run_analysis()

    # Export formatted HTML button
    def do_export():
        cleanup_bindings()
        win.destroy()
        controller.export_formatted_html()

    # 下部に操作ボタンを配置
    btn_frame = tk.Frame(win)
    btn_frame.pack(fill='x', pady=6)
    tk.Button(btn_frame, text="整形HTMLを保存", command=do_export).pack(side='left', padx=6)
    tk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=6)
    tk.Button(btn_frame, text="キャンセル", command=lambda: (cleanup_bindings(), win.destroy())).pack(side='left', padx=6)

def choose_color(var):
    color_code = colorchooser.askcolor(title="色を選択")[1]
    if color_code:
        var.set(color_code)
