import asyncio
import io
import logging
import os

import discord

from bot_logic import (
    COLOR_COMMANDS,
    DEFAULT_SETTINGS,
    MAX_ATTACHMENT_BYTES,
    PRESETS,
    apply_auto_delete_time,
    apply_color_setting,
    apply_preset,
    build_bot_settings,
    color_or_default,
    display_filename,
    get_auto_delete_time,
    get_guild_key,
    is_attachment_too_large,
    is_html_filename,
    is_valid_color,
    load_settings,
    package_output,
    parse_auto_delete_seconds,
    parse_command,
    reset_guild_settings,
    save_settings,
)
from renderer import build_formatted_html_from_string

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

# 反応するチャンネルIDのリスト (空の場合は全チャンネルで反応)
# 例: ALLOWED_CHANNEL_IDS = [123456789012345678, 987654321098765432]
ALLOWED_CHANNEL_IDS = []

# サーバーごとの設定を保存するファイル
SETTINGS_FILE = "server_settings.json"

# サーバー設定のキャッシュ。起動時に main() で読み込む
server_settings_cache = {}

# Intentsの設定（メッセージ内容と添付ファイルの読み取り権限が必要）
intents = discord.Intents.default()
intents.message_content = True

# 変換結果のメンションはユーザーにのみ反応させる（@everyone等は無効）
client = discord.Client(
    intents=intents,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
)

_background_tasks = set()

COLOR_FORMAT_ERROR = "❌ 色は `#RGB` または `#RRGGBB` の形式で指定してください。"
CONVERT_ERROR = "❌ 変換中にエラーが発生しました。ログのHTML形式を確認してください。"
DECODE_ERROR = "❌ ファイルを読み取れませんでした。UTF-8形式のHTMLファイルをアップロードしてください。"
DISCORD_ERROR = "❌ Discordとの通信でエラーが発生しました。しばらくしてからもう一度お試しください。"


# プレビュー画像を生成する関数
def generate_preview_image(preset_data):
    if not HAS_PIL:
        return None

    width, height = 400, 150
    bg_color = color_or_default(preset_data.get("global_background"), "global_background")
    tab_bg = color_or_default(preset_data.get("tab_default_background"), "tab_default_background")
    tab_border = color_or_default(preset_data.get("tab_default_border"), "tab_default_border")
    text_color = color_or_default(preset_data.get("global_color"), "global_color")

    image = Image.new('RGB', (width, height), color=bg_color)
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
    except OSError:
        font = ImageFont.load_default()

    draw.text((title_x + 10, title_y + 5), "Main Tab", fill=text_color, font=font)
    draw.text((rect_x + 10, rect_y + 15), "Player Name", fill=text_color, font=font)
    draw.text((rect_x + 10, rect_y + 35), "This is a preview log.", fill=text_color, font=font)
    draw.text((rect_x + 10, rect_y + 55), "1d100 <= 50 -> Success", fill=text_color, font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def persist_settings():
    save_settings(SETTINGS_FILE, server_settings_cache)


async def send_with_preview(channel, text, preview_data, preview_filename):
    preview_buf = generate_preview_image(preview_data)
    if preview_buf:
        await channel.send(text, file=discord.File(preview_buf, filename=preview_filename))
    else:
        await channel.send(text)


async def delete_message_later(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except discord.Forbidden:
        logger.warning("権限エラー: メッセージを削除できませんでした。Botに「メッセージの管理」権限を与えてください。")
    except discord.HTTPException:
        logger.debug("元のメッセージを削除できませんでした", exc_info=True)


def schedule_message_delete(msg, delay):
    task = asyncio.create_task(delete_message_later(msg, delay))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@client.event
async def on_ready():
    logger.info('Logged in as %s', client.user)
    logger.info('準備完了: HTMLファイルをアップロードすると自動で変換します。')
    await client.change_presence(activity=discord.Game(name="!help | ログ変換"))


async def handle_color_command(message, command, args, guild_key):
    spec = COLOR_COMMANDS[command]
    if not args:
        await message.channel.send(f"ℹ️ 使用法: `{command} #RRGGBB` (例: `{command} {spec.example}`)")
        return

    color = args[0]
    if not apply_color_setting(server_settings_cache, guild_key, spec.setting_key, color):
        await message.channel.send(f"{COLOR_FORMAT_ERROR} (例: `{command} {spec.example}`)")
        return

    persist_settings()
    await send_with_preview(
        message.channel,
        spec.success_message.format(color=color),
        server_settings_cache[guild_key],
        spec.preview_filename,
    )


async def handle_auto_delete_command(message, args, guild_key):
    if not args:
        await message.channel.send("ℹ️ 使用法: `!set_auto_delete 秒数` (例: `!set_auto_delete 60`)\n※0を指定すると自動削除が無効になります。\n※有効にすると、変換結果と元のメッセージの両方が削除されます。")
        return

    try:
        seconds = parse_auto_delete_seconds(args[0])
    except ValueError:
        await message.channel.send("❌ 秒数は0以上の整数で指定してください。")
        return

    apply_auto_delete_time(server_settings_cache, guild_key, seconds)
    persist_settings()

    if seconds == 0:
        await message.channel.send("⏱️ 自動削除を **無効** にしました。")
    else:
        await message.channel.send(f"⏱️ 自動削除時間を `{seconds}` 秒に設定しました。\n（変換結果と元のメッセージが対象です）")


async def handle_preset_command(message, args, guild_key):
    if not args:
        preset_list = "\n".join([f"- `{k}` : {v['description']}" for k, v in PRESETS.items()])
        await message.channel.send(f"ℹ️ 使用法: `!preset プリセット名`\n**利用可能なプリセット:**\n{preset_list}")
        return

    preset_name = args[0].lower()
    preset = apply_preset(server_settings_cache, guild_key, preset_name)
    if preset is None:
        await message.channel.send(f"❌ プリセット `{display_filename(preset_name)}` は存在しません。")
        return

    persist_settings()
    await send_with_preview(
        message.channel,
        f"🎨 設定をプリセット `{preset_name}` ({preset['description']}) に変更しました。",
        preset,
        f"preview_{preset_name}.png",
    )


async def handle_reset_command(message, guild_key):
    if reset_guild_settings(server_settings_cache, guild_key):
        persist_settings()
        await send_with_preview(message.channel, "⚙️ このサーバーの設定を初期化しました。", {}, "preview_reset.png")
    else:
        await message.channel.send("ℹ️ カスタム設定は保存されていません。")


async def handle_settings_command(message, guild_key):
    guild_config = server_settings_cache.get(guild_key, {})

    def shown(key):
        value = guild_config.get(key)
        return value if is_valid_color(value) else f"{DEFAULT_SETTINGS[key]} (デフォルト)"

    auto_delete = get_auto_delete_time(guild_config)
    auto_delete_str = f"{auto_delete}秒" if auto_delete > 0 else "無効"

    settings_text = (
        f"**現在の設定**\n"
        f"🎨 全体背景色: `{shown('global_background')}`\n"
        f"🎨 文字色: `{shown('global_color')}`\n"
        f"🎨 タブ背景色: `{shown('tab_default_background')}`\n"
        f"🎨 タブ枠線色: `{shown('tab_default_border')}`\n"
        f"⏱️ 自動削除: `{auto_delete_str}`"
    )
    await send_with_preview(message.channel, settings_text, guild_config, "preview_settings.png")


async def handle_help_command(message):
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


async def convert_attachment(message, attachment, guild_key):
    """添付されたHTMLログを変換して返信する。内部例外の詳細は返信せずログに出力する。"""
    shown_name = display_filename(attachment.filename)

    # 変換前にサイズを検査する
    if is_attachment_too_large(attachment.size):
        limit_mb = MAX_ATTACHMENT_BYTES // (1024 * 1024)
        await message.channel.send(f"{message.author.mention} ❌ `{shown_name}` はファイルサイズが大きすぎます（上限 {limit_mb}MB）。")
        return

    processing_msg = await message.channel.send(f'🔄 `{shown_name}` を変換しています...')
    try:
        raw = await attachment.read()
        if len(raw) > MAX_ATTACHMENT_BYTES:
            await message.channel.send(f"{message.author.mention} ❌ `{shown_name}` はファイルサイズが大きすぎます。")
            return
        html_text = raw.decode("utf-8")

        guild_config = server_settings_cache.get(guild_key, {})
        bot_settings = build_bot_settings(guild_config, attachment.filename)
        logger.info("Converting: %s (Guild: %s)", attachment.filename, guild_key)

        # 大きいログでもイベントループを止めないよう、別スレッドで変換する
        formatted_html = await asyncio.to_thread(build_formatted_html_from_string, html_text, bot_settings)
        output = package_output(formatted_html, attachment.filename)

        auto_delete_time = get_auto_delete_time(guild_config)
        delete_param = auto_delete_time if auto_delete_time > 0 else None
        delete_msg = ""
        if delete_param:
            delete_msg = f"\n※このメッセージは{auto_delete_time}秒後に自動削除されます。（元のメッセージも削除されます）"

        zip_note = "(サイズ調整のためZIP圧縮済み)" if output.zipped else ""
        content_msg = f"{message.author.mention} ✅ `{shown_name}` の変換が完了しました！{zip_note}{delete_msg}"

        discord_file = discord.File(fp=io.BytesIO(output.data), filename=output.filename)
        await message.channel.send(content=content_msg, file=discord_file, delete_after=delete_param)

        # 元のメッセージも設定時間後に削除
        if delete_param:
            schedule_message_delete(message, delete_param)

    except UnicodeDecodeError:
        logger.warning("UTF-8として読み取れないファイル: %s", attachment.filename, exc_info=True)
        await message.channel.send(f"{message.author.mention} {DECODE_ERROR}")

    except discord.HTTPException as e:
        logger.exception("Discord HTTP Error converting %s", attachment.filename)
        if e.status == 413:
            await message.channel.send(f"{message.author.mention} ❌ ファイルサイズが大きすぎて送信できませんでした（圧縮後も制限超過）。")
        else:
            await message.channel.send(f"{message.author.mention} {DISCORD_ERROR}")

    except Exception:
        logger.exception("Error converting %s", attachment.filename)
        await message.channel.send(f"{message.author.mention} {CONVERT_ERROR}")

    finally:
        # 変換中メッセージを削除
        try:
            await processing_msg.delete()
        except discord.HTTPException:
            logger.debug("変換中メッセージを削除できませんでした", exc_info=True)


@client.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == client.user:
        return

    # 特定のチャンネルのみ許可する場合のチェック
    if ALLOWED_CHANNEL_IDS and message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    command, args = parse_command(message.content)
    # サーバーIDを取得 (DMの場合は 'dm')
    guild_key = get_guild_key(message.guild.id if message.guild else None)

    # --- 設定コマンドの処理 ---
    if command in COLOR_COMMANDS:
        await handle_color_command(message, command, args, guild_key)
        return

    if command == '!set_auto_delete':
        await handle_auto_delete_command(message, args, guild_key)
        return

    if command == '!preset':
        await handle_preset_command(message, args, guild_key)
        return

    if command == '!reset_settings' and not args:
        await handle_reset_command(message, guild_key)
        return

    if command == '!settings' and not args:
        await handle_settings_command(message, guild_key)
        return

    if command == '!help' and not args:
        await handle_help_command(message)
        return

    # 添付ファイルがあるか確認
    if message.attachments:
        # メンションまたはコマンド(!で始まる)が含まれていない場合は無視
        if not (client.user in message.mentions or message.content.strip().startswith('!')):
            return

        for attachment in message.attachments:
            # HTMLファイルのみ対象（拡張子チェック）
            if is_html_filename(attachment.filename):
                await convert_attachment(message, attachment, guild_key)


def main():
    # 起動時にのみ .env とサーバー設定を読み込み、Webサーバーを起動する
    from dotenv import load_dotenv

    from keep_alive import keep_alive

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError("Botトークンが設定されていません。.envファイルを作成し、DISCORD_BOT_TOKENを設定してください。")

    server_settings_cache.clear()
    server_settings_cache.update(load_settings(SETTINGS_FILE))

    # Webサーバーを起動してポートをリッスン（Render等のWeb Service用）
    keep_alive()
    client.run(token)


if __name__ == "__main__":
    main()
