import discord
import os
import tempfile
import io
import zipfile
import json
from renderer import build_formatted_html
from dotenv import load_dotenv
from keep_alive import keep_alive

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# .envファイルから環境変数を読み込む
load_dotenv()

# ==========================================
# Botのトークンを環境変数から取得
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Botトークンが設定されていません。.envファイルを作成し、DISCORD_BOT_TOKENを設定してください。")

# 反応するチャンネルIDのリスト (空の場合は全チャンネルで反応)
# 例: ALLOWED_CHANNEL_IDS = [123456789012345678, 987654321098765432]
ALLOWED_CHANNEL_IDS = []
# ==========================================

# プリセット定義
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

# サーバーごとの設定を保存するファイル
SETTINGS_FILE = "server_settings.json"

# 設定を読み込む関数
def load_all_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"設定読み込みエラー: {e}")
    return {}

# 設定を保存する関数
def save_all_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"設定保存エラー: {e}")

# プレビュー画像を生成する関数
def generate_preview_image(preset_data):
    if not HAS_PIL:
        return None

    width, height = 400, 150
    bg_color = preset_data.get("global_background", "#ffffff")
    tab_bg = preset_data.get("tab_default_background", "#ffffff")
    tab_border = preset_data.get("tab_default_border", "#999999")

    try:
        image = Image.new('RGB', (width, height), color=bg_color)
    except ValueError:
        image = Image.new('RGB', (width, height), color="#ffffff")

    draw = ImageDraw.Draw(image)

    # タブの描画
    rect_x, rect_y, rect_w, rect_h = 20, 40, 360, 90
    draw.rectangle([rect_x, rect_y, rect_x + rect_w, rect_y + rect_h], fill=tab_bg, outline=tab_border, width=2)

    # タブタイトルの描画
    title_x, title_y, title_w, title_h = 30, 25, 80, 25
    draw.rectangle([title_x, title_y, title_x + title_w, title_y + title_h], fill=tab_bg, outline=tab_border, width=1)

    # フォント設定
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font = ImageFont.load_default()

    text_color = preset_data.get("global_color", "#000000")

    draw.text((title_x + 10, title_y + 5), "Main Tab", fill=text_color, font=font)
    draw.text((rect_x + 10, rect_y + 15), "Player Name", fill=text_color, font=font)
    draw.text((rect_x + 10, rect_y + 35), "This is a preview log.", fill=text_color, font=font)
    draw.text((rect_x + 10, rect_y + 55), "1d100 <= 50 -> Success", fill=text_color, font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# 起動時に設定をロード
server_settings_cache = load_all_settings()

# Intentsの設定（メッセージ内容と添付ファイルの読み取り権限が必要）
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print('準備完了: HTMLファイルをアップロードすると自動で変換します。')
    await client.change_presence(activity=discord.Game(name="!help | ログ変換"))

@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # 特定のチャンネルのみ許可する場合のチェック
    if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    # --- 設定コマンドの処理 ---

    # 背景色の設定: !set_bg #RRGGBB
    if message.content.startswith('!set_bg'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("ℹ️ 使用法: `!set_bg #RRGGBB` (例: `!set_bg #000000`)")
            return

        color = parts[1]
        # サーバーIDを取得 (DMの場合は 'dm')
        guild_id = str(message.guild.id) if message.guild else "dm"

        if guild_id not in server_settings_cache:
            server_settings_cache[guild_id] = {}

        server_settings_cache[guild_id]["global_background"] = color
        save_all_settings(server_settings_cache)

        msg_text = f"🎨 このサーバーの背景色を `{color}` に設定しました。"
        preview_buf = generate_preview_image(server_settings_cache[guild_id])
        if preview_buf:
            file = discord.File(preview_buf, filename="preview_bg.png")
            await message.channel.send(msg_text, file=file)
        else:
            await message.channel.send(msg_text)
        return

    # 文字色の設定: !set_text_color #RRGGBB
    if message.content.startswith('!set_text_color'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("ℹ️ 使用法: `!set_text_color #RRGGBB` (例: `!set_text_color #ffffff`)")
            return

        color = parts[1]
        # サーバーIDを取得 (DMの場合は 'dm')
        guild_id = str(message.guild.id) if message.guild else "dm"

        if guild_id not in server_settings_cache:
            server_settings_cache[guild_id] = {}

        server_settings_cache[guild_id]["global_color"] = color
        save_all_settings(server_settings_cache)

        msg_text = f"🎨 このサーバーの文字色を `{color}` に設定しました。"
        preview_buf = generate_preview_image(server_settings_cache[guild_id])
        if preview_buf:
            file = discord.File(preview_buf, filename="preview_text_color.png")
            await message.channel.send(msg_text, file=file)
        else:
            await message.channel.send(msg_text)
        return

    # タブ背景色の設定: !set_tab_bg #RRGGBB
    if message.content.startswith('!set_tab_bg'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("ℹ️ 使用法: `!set_tab_bg #RRGGBB` (例: `!set_tab_bg #ffffff`)")
            return

        color = parts[1]
        # サーバーIDを取得 (DMの場合は 'dm')
        guild_id = str(message.guild.id) if message.guild else "dm"

        if guild_id not in server_settings_cache:
            server_settings_cache[guild_id] = {}

        server_settings_cache[guild_id]["tab_default_background"] = color
        save_all_settings(server_settings_cache)

        msg_text = f"🎨 タブのデフォルト背景色を `{color}` に設定しました。"
        preview_buf = generate_preview_image(server_settings_cache[guild_id])
        if preview_buf:
            file = discord.File(preview_buf, filename="preview_tab_bg.png")
            await message.channel.send(msg_text, file=file)
        else:
            await message.channel.send(msg_text)
        return

    # タブボーダー色の設定: !set_tab_border #RRGGBB
    if message.content.startswith('!set_tab_border'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("ℹ️ 使用法: `!set_tab_border #RRGGBB` (例: `!set_tab_border #999999`)")
            return

        color = parts[1]
        # サーバーIDを取得 (DMの場合は 'dm')
        guild_id = str(message.guild.id) if message.guild else "dm"

        if guild_id not in server_settings_cache:
            server_settings_cache[guild_id] = {}

        server_settings_cache[guild_id]["tab_default_border"] = color
        save_all_settings(server_settings_cache)

        msg_text = f"🎨 タブのデフォルトボーダー色を `{color}` に設定しました。"
        preview_buf = generate_preview_image(server_settings_cache[guild_id])
        if preview_buf:
            file = discord.File(preview_buf, filename="preview_tab_border.png")
            await message.channel.send(msg_text, file=file)
        else:
            await message.channel.send(msg_text)
        return

    # 自動削除時間の設定: !set_auto_delete seconds
    if message.content.startswith('!set_auto_delete'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("ℹ️ 使用法: `!set_auto_delete 秒数` (例: `!set_auto_delete 60`)\n※0を指定すると自動削除が無効になります。\n※有効にすると、変換結果と元のメッセージの両方が削除されます。")
            return

        try:
            seconds = int(parts[1])
            if seconds < 0:
                raise ValueError
        except ValueError:
            await message.channel.send("❌ 秒数は0以上の整数で指定してください。")
            return

        guild_id = str(message.guild.id) if message.guild else "dm"
        if guild_id not in server_settings_cache:
            server_settings_cache[guild_id] = {}

        server_settings_cache[guild_id]["auto_delete_time"] = seconds
        save_all_settings(server_settings_cache)

        if seconds == 0:
            await message.channel.send("⏱️ 自動削除を **無効** にしました。")
        else:
            await message.channel.send(f"⏱️ 自動削除時間を `{seconds}` 秒に設定しました。\n（変換結果と元のメッセージが対象です）")
        return

    # プリセット設定: !preset name
    if message.content.startswith('!preset'):
        parts = message.content.split()
        if len(parts) < 2:
            preset_list = "\n".join([f"- `{k}` : {v['description']}" for k, v in PRESETS.items()])
            await message.channel.send(f"ℹ️ 使用法: `!preset プリセット名`\n**利用可能なプリセット:**\n{preset_list}")
            return

        preset_name = parts[1].lower()
        if preset_name not in PRESETS:
            await message.channel.send(f"❌ プリセット `{preset_name}` は存在しません。")
            return

        preset = PRESETS[preset_name]
        guild_id = str(message.guild.id) if message.guild else "dm"

        if guild_id not in server_settings_cache:
            server_settings_cache[guild_id] = {}

        server_settings_cache[guild_id]["global_background"] = preset["global_background"]
        server_settings_cache[guild_id]["global_color"] = preset["global_color"]
        server_settings_cache[guild_id]["tab_default_background"] = preset["tab_default_background"]
        server_settings_cache[guild_id]["tab_default_border"] = preset["tab_default_border"]
        save_all_settings(server_settings_cache)

        preview_buf = generate_preview_image(preset)
        if preview_buf:
            file = discord.File(preview_buf, filename=f"preview_{preset_name}.png")
            await message.channel.send(f"🎨 設定をプリセット `{preset_name}` ({preset['description']}) に変更しました。", file=file)
        else:
            await message.channel.send(f"🎨 設定をプリセット `{preset_name}` ({preset['description']}) に変更しました。")
        return

    # 設定リセット: !reset_settings
    if message.content == '!reset_settings':
        guild_id = str(message.guild.id) if message.guild else "dm"
        if guild_id in server_settings_cache:
            del server_settings_cache[guild_id]
            save_all_settings(server_settings_cache)
            msg_text = "⚙️ このサーバーの設定を初期化しました。"
            preview_buf = generate_preview_image({}) # デフォルト値でプレビュー
            if preview_buf:
                file = discord.File(preview_buf, filename="preview_reset.png")
                await message.channel.send(msg_text, file=file)
            else:
                await message.channel.send(msg_text)
        else:
            await message.channel.send("ℹ️ カスタム設定は保存されていません。")
        return

    # 設定確認: !settings
    if message.content == '!settings':
        guild_id = str(message.guild.id) if message.guild else "dm"
        guild_config = server_settings_cache.get(guild_id, {})

        bg_color = guild_config.get("global_background", "#ffffff (デフォルト)")
        text_color = guild_config.get("global_color", "#000000 (デフォルト)")
        tab_bg = guild_config.get("tab_default_background", "#ffffff (デフォルト)")
        tab_border = guild_config.get("tab_default_border", "#999999 (デフォルト)")
        auto_delete = guild_config.get("auto_delete_time", 60)

        auto_delete_str = f"{auto_delete}秒" if auto_delete > 0 else "無効"

        settings_text = (
            f"**現在の設定**\n"
            f"🎨 全体背景色: `{bg_color}`\n"
            f"🎨 文字色: `{text_color}`\n"
            f"🎨 タブ背景色: `{tab_bg}`\n"
            f"🎨 タブ枠線色: `{tab_border}`\n"
            f"⏱️ 自動削除: `{auto_delete_str}`"
        )
        preview_buf = generate_preview_image(guild_config)
        if preview_buf:
            file = discord.File(preview_buf, filename="preview_settings.png")
            await message.channel.send(settings_text, file=file)
        else:
            await message.channel.send(settings_text)
        return

    # ヘルプコマンド: !help
    if message.content == '!help':
        help_text = (
            "**TRPGログ整形Botの使い方**\n"
            "メンションまたはコマンド(!...)と共にHTMLログファイルをアップロードすると、自動で色設定を行い整形して返します。\n\n"
            "**設定コマンド** (サーバーごとに保存されます)\n"
            "`!settings` : 現在の設定を表示\n"
            "`!preset name` : プリセットを適用 (light/dark/black)\n"
            "`!set_bg #RRGGBB` : 全体の背景色を変更\n"
            "`!set_text_color #RRGGBB` : 文字色を変更\n"
            "`!set_tab_bg #RRGGBB` : タブの背景色を変更\n"
            "`!set_tab_border #RRGGBB` : タブの枠線色を変更\n"
            "`!set_auto_delete 秒数` : 結果と元メッセージの自動削除時間を設定 (0で無効)\n"
            "`!reset_settings` : 設定を初期状態(白背景)に戻す\n"
        )
        await message.channel.send(help_text)
        return

    # 添付ファイルがあるか確認
    if message.attachments:
        # メンションまたはコマンド(!で始まる)が含まれていない場合は無視
        if not (client.user in message.mentions or message.content.strip().startswith('!')):
            return

        for attachment in message.attachments:
            # HTMLファイルのみ対象（拡張子チェック）
            if attachment.filename.lower().endswith('.html'):
                processing_msg = await message.channel.send(f'🔄 `{attachment.filename}` を変換しています...')

                tmp_input_path = None
                try:
                    # 1. 添付ファイルを一時ファイルとして保存
                    # renderer.py はファイルパスを要求するため、一度ディスクに保存します
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_input:
                        await attachment.save(tmp_input.name)
                        tmp_input_path = tmp_input.name

                    # 2. Bot用の設定（サーバー設定を適用）
                    guild_id = str(message.guild.id) if message.guild else "dm"
                    guild_config = server_settings_cache.get(guild_id, {})

                    # 設定値の取得（デバッグ用に変数化してログ出力）
                    bg_color = guild_config.get("global_background", "#ffffff")
                    text_color = guild_config.get("global_color", "#000000")

                    print(f"[Log] Converting: {attachment.filename} (Guild: {guild_id})")
                    print(f"[Log] Apply Settings -> BG: {bg_color}, Text: {text_color}")

                    bot_settings = {
                        "global_background": bg_color,
                        "global_color": text_color,
                        "html_title": f"Converted: {attachment.filename}",
                        "tabs": {},    # 特定のタブ色を指定したい場合はここに記述
                        "players": {}, # 特定のプレイヤー色を指定したい場合はここに記述
                        "tab_default_background": guild_config.get("tab_default_background", "#ffffff"),
                        "tab_default_border": guild_config.get("tab_default_border", "#999999")
                    }

                    # 3. 変換処理を実行
                    # build_formatted_html はファイルパスを受け取り、HTML文字列を返します
                    formatted_html = build_formatted_html(tmp_input_path, settings=bot_settings)

                    # バイトデータに変換してサイズを確認
                    html_bytes = formatted_html.encode('utf-8')

                    # 自動削除設定の取得 (デフォルト60秒)
                    auto_delete_time = guild_config.get("auto_delete_time", 60)
                    delete_msg = ""
                    delete_param = None
                    if auto_delete_time > 0:
                        delete_msg = f"\n※このメッセージは{auto_delete_time}秒後に自動削除されます。（元のメッセージも削除されます）"
                        delete_param = auto_delete_time

                    # 4. 結果をDiscordに送信
                    # ファイルサイズが7.5MBを超える場合は自動的にZIP圧縮を行う
                    # (Discordの通常制限8MBに対する安全マージン)
                    LIMIT_SIZE = 7.5 * 1024 * 1024

                    send_buffer = io.BytesIO()
                    send_filename = f"formatted_{attachment.filename}"
                    content_msg = f"{message.author.mention} ✅ `{attachment.filename}` の変換が完了しました！{delete_msg}"

                    if len(html_bytes) > LIMIT_SIZE:
                        # ZIP圧縮 (最高圧縮率 compresslevel=9 を指定)
                        with zipfile.ZipFile(send_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                            zf.writestr(send_filename, html_bytes)
                        send_filename += ".zip"
                        content_msg = f"{message.author.mention} ✅ `{attachment.filename}` の変換が完了しました！(サイズ調整のためZIP圧縮済み){delete_msg}"
                    else:
                        # そのまま書き込み
                        send_buffer.write(html_bytes)

                    # バッファの先頭に戻す
                    send_buffer.seek(0)

                    discord_file = discord.File(fp=send_buffer, filename=send_filename)
                    await message.channel.send(
                        content=content_msg,
                        file=discord_file,
                        delete_after=delete_param
                    )

                    # 元のメッセージも設定時間後に削除
                    if delete_param:
                        try:
                            await message.delete(delay=delete_param)
                        except Exception:
                            pass

                except discord.HTTPException as e:
                    if e.status == 413:
                        await message.channel.send(f"{message.author.mention} ❌ ファイルサイズが大きすぎて送信できませんでした（圧縮後も制限超過）。")
                    else:
                        await message.channel.send(f"{message.author.mention} ❌ Discordエラーが発生しました: {e}")
                    print(f"Discord HTTP Error converting {attachment.filename}: {e}")

                except Exception as e:
                    await message.channel.send(f"{message.author.mention} ❌ エラーが発生しました: {e}")
                    print(f"Error converting {attachment.filename}: {e}")

                finally:
                    # 変換中メッセージを削除
                    try:
                        await processing_msg.delete()
                    except Exception:
                        pass

                    # 5. 入力用の一時ファイルを削除（後始末）
                    if tmp_input_path and os.path.exists(tmp_input_path):
                        os.remove(tmp_input_path)

# Webサーバーを起動してポートをリッスン（Render等のWeb Service用）
keep_alive()
client.run(TOKEN)