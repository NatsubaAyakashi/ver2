import discord
import os
import tempfile
import io
import zipfile
import json
from renderer import build_formatted_html
from dotenv import load_dotenv
from keep_alive import keep_alive

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

        await message.channel.send(f"🎨 このサーバーの背景色を `{color}` に設定しました。")
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

        await message.channel.send(f"🎨 タブのデフォルト背景色を `{color}` に設定しました。")
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

        await message.channel.send(f"🎨 タブのデフォルトボーダー色を `{color}` に設定しました。")
        return

    # 自動削除時間の設定: !set_auto_delete seconds
    if message.content.startswith('!set_auto_delete'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("ℹ️ 使用法: `!set_auto_delete 秒数` (例: `!set_auto_delete 60`)\n※0を指定すると自動削除が無効になります。")
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
            await message.channel.send("⏱️ 変換結果の自動削除を **無効** にしました。")
        else:
            await message.channel.send(f"⏱️ 変換結果の自動削除時間を `{seconds}` 秒に設定しました。")
        return

    # 設定リセット: !reset_settings
    if message.content == '!reset_settings':
        guild_id = str(message.guild.id) if message.guild else "dm"
        if guild_id in server_settings_cache:
            del server_settings_cache[guild_id]
            save_all_settings(server_settings_cache)
            await message.channel.send("⚙️ このサーバーの設定を初期化しました。")
        else:
            await message.channel.send("ℹ️ カスタム設定は保存されていません。")
        return

    # ヘルプコマンド: !help
    if message.content == '!help':
        help_text = (
            "**TRPGログ整形Botの使い方**\n"
            "ココフォリアなどのHTMLログファイルをアップロードすると、自動で色設定を行い整形して返します。\n\n"
            "**設定コマンド** (サーバーごとに保存されます)\n"
            "`!set_bg #RRGGBB` : 全体の背景色を変更 (例: `!set_bg #202020`)\n"
            "`!set_tab_bg #RRGGBB` : タブの背景色を変更\n"
            "`!set_tab_border #RRGGBB` : タブの枠線色を変更\n"
            "`!set_auto_delete 秒数` : 結果の自動削除時間を設定 (0で無効)\n"
            "`!reset_settings` : 設定を初期状態(白背景)に戻す\n"
        )
        await message.channel.send(help_text)
        return

    # 添付ファイルがあるか確認
    if message.attachments:
        for attachment in message.attachments:
            # HTMLファイルのみ対象（拡張子チェック）
            if attachment.filename.lower().endswith('.html'):
                await message.channel.send(f'🔄 `{attachment.filename}` を変換しています...')

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

                    bot_settings = {
                        # 保存された設定があれば使い、なければデフォルト(#ffffff)を使う
                        "global_background": guild_config.get("global_background", "#ffffff"),
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
                        delete_msg = f"\n※このメッセージは{auto_delete_time}秒後に自動削除されます。"
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
                    # 5. 入力用の一時ファイルを削除（後始末）
                    if tmp_input_path and os.path.exists(tmp_input_path):
                        os.remove(tmp_input_path)

# Webサーバーを起動してポートをリッスン（Render等のWeb Service用）
keep_alive()
client.run(TOKEN)