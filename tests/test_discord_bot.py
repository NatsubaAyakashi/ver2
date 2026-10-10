import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import discord_bot
from bot_logic import MAX_ATTACHMENT_BYTES

ROOT = Path(__file__).resolve().parent.parent
LOG_HTML = (ROOT / "tests" / "fixtures" / "sample_log.html").read_bytes()
XSS_HTML = (ROOT / "tests" / "fixtures" / "xss_log.html").read_bytes()


class FakeSent:
    def __init__(self):
        self.deleted = False

    async def delete(self):
        self.deleted = True


class FakeChannel:
    id = 1

    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        sent = FakeSent()
        self.sent.append((content, kwargs, sent))
        return sent

    @property
    def texts(self):
        return [c for c, _, _ in self.sent]


class FakeAttachment:
    def __init__(self, filename="log.html", data=LOG_HTML, size=None):
        self.filename = filename
        self.data = data
        self.size = len(data) if size is None else size
        self.read_called = False

    async def read(self):
        self.read_called = True
        return self.data


def make_message(content="", attachments=(), guild_id=42):
    return SimpleNamespace(
        author=SimpleNamespace(mention="<@1>"),
        channel=FakeChannel(),
        guild=SimpleNamespace(id=guild_id) if guild_id is not None else None,
        content=content,
        attachments=list(attachments),
        mentions=[],
    )


def run(message):
    asyncio.run(discord_bot.on_message(message))


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    settings_file = tmp_path / "server_settings.json"
    monkeypatch.setattr(discord_bot, "SETTINGS_FILE", str(settings_file))
    monkeypatch.setattr(discord_bot, "server_settings_cache", {})
    monkeypatch.setattr(discord_bot, "schedule_message_delete", lambda msg, delay: None)
    return settings_file


def test_import_has_no_side_effects(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "DISCORD_BOT_TOKEN"}
    code = (
        "import sys, threading;"
        "import discord_bot;"
        "print(threading.active_count(), 'flask' in sys.modules, 'dotenv' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["1", "False", "False"]
    assert list(tmp_path.iterdir()) == []


def test_main_requires_token(monkeypatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.setattr(discord_bot.client, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError):
        discord_bot.main()


def test_main_starts_keep_alive_and_client_with_token(monkeypatch, isolated_state):
    import dotenv

    import keep_alive

    calls = []
    isolated_state.write_text(json.dumps({"1": {"global_color": "#fff"}}), encoding="utf-8")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "dummy-token")
    monkeypatch.setattr(keep_alive, "keep_alive", lambda: calls.append("keep_alive"))
    monkeypatch.setattr(discord_bot.client, "run", lambda token: calls.append(("run", token)))
    discord_bot.main()
    assert calls == ["keep_alive", ("run", "dummy-token")]
    assert discord_bot.server_settings_cache == {"1": {"global_color": "#fff"}}


def test_valid_color_command_is_saved(isolated_state):
    msg = make_message("!set_bg #112233")
    run(msg)
    assert discord_bot.server_settings_cache["42"]["global_background"] == "#112233"
    assert json.loads(isolated_state.read_text(encoding="utf-8")) == {"42": {"global_background": "#112233"}}
    assert "`#112233`" in msg.channel.texts[0]


@pytest.mark.parametrize("bad", ["red", "#12", "#12345", "red;}</style><script>", "#ggg"])
def test_invalid_color_is_rejected_and_not_saved(isolated_state, bad):
    msg = make_message(f"!set_text_color {bad}")
    run(msg)
    assert discord_bot.server_settings_cache == {}
    assert not isolated_state.exists()
    assert "#RGB" in msg.channel.texts[0]


def test_color_command_without_argument_shows_usage():
    msg = make_message("!set_tab_border")
    run(msg)
    assert "使用法" in msg.channel.texts[0]
    assert discord_bot.server_settings_cache == {}


def test_auto_delete_command():
    run(make_message("!set_auto_delete 30"))
    assert discord_bot.server_settings_cache["42"]["auto_delete_time"] == 30
    bad = make_message("!set_auto_delete -3")
    run(bad)
    assert discord_bot.server_settings_cache["42"]["auto_delete_time"] == 30
    assert "0以上" in bad.channel.texts[0]


def test_preset_and_reset_and_settings_commands():
    run(make_message("!preset dark"))
    assert discord_bot.server_settings_cache["42"]["global_background"] == "#202020"
    shown = make_message("!settings")
    run(shown)
    assert "#202020" in shown.channel.texts[0]
    unknown = make_message("!preset nope")
    run(unknown)
    assert "存在しません" in unknown.channel.texts[0]
    run(make_message("!reset_settings"))
    assert "42" not in discord_bot.server_settings_cache


def test_dm_uses_dm_key():
    run(make_message("!set_bg #000", guild_id=None))
    assert "dm" in discord_bot.server_settings_cache


def test_help_command():
    msg = make_message("!help")
    run(msg)
    assert "TRPGログ整形Bot" in msg.channel.texts[0]


def test_attachment_without_mention_or_command_is_ignored():
    att = FakeAttachment()
    msg = make_message("hello", [att])
    run(msg)
    assert msg.channel.sent == []
    assert not att.read_called


def test_html_attachment_is_converted():
    att = FakeAttachment()
    msg = make_message("!convert", [att])
    run(msg)
    done = [s for s in msg.channel.sent if s[1].get("file") is not None]
    assert len(done) == 1
    content, kwargs, _ = done[0]
    assert "変換が完了しました" in content
    assert kwargs["file"].filename == "formatted_log.html"
    assert kwargs["delete_after"] == 60
    body = kwargs["file"].fp.read().decode("utf-8")
    assert "<!DOCTYPE html>" in body and "Converted: log.html" in body
    # 変換中メッセージは削除される
    assert msg.channel.sent[0][2].deleted


def test_non_html_attachment_is_ignored():
    att = FakeAttachment(filename="log.txt")
    msg = make_message("!convert", [att])
    run(msg)
    assert msg.channel.sent == []
    assert not att.read_called


def test_oversized_attachment_is_rejected_before_download():
    att = FakeAttachment(size=MAX_ATTACHMENT_BYTES + 1)
    msg = make_message("!convert", [att])
    run(msg)
    assert not att.read_called
    assert len(msg.channel.sent) == 1
    assert "大きすぎ" in msg.channel.texts[0]


def test_attachment_with_unknown_size_is_rejected():
    att = FakeAttachment(size=None)
    att.size = None
    msg = make_message("!convert", [att])
    run(msg)
    assert not att.read_called


def test_non_utf8_attachment_gets_friendly_error():
    att = FakeAttachment(data="あ".encode("shift_jis"))
    msg = make_message("!convert", [att])
    run(msg)
    assert any("UTF-8" in t for t in msg.channel.texts if t)
    assert msg.channel.sent[0][2].deleted


def test_internal_exception_details_are_not_sent(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("secret-internal-detail C:\\Users\\x\\token")

    monkeypatch.setattr(discord_bot, "build_formatted_html_from_string", boom)
    msg = make_message("!convert", [FakeAttachment()])
    with caplog.at_level("ERROR"):
        run(msg)
    joined = "\n".join(t for t in msg.channel.texts if t)
    assert "secret-internal-detail" not in joined
    assert "変換中にエラー" in joined
    assert "secret-internal-detail" in caplog.text
    assert msg.channel.sent[0][2].deleted


def test_xss_log_is_escaped_in_sent_file():
    att = FakeAttachment(filename='<img src=x onerror=alert(1)>.html', data=XSS_HTML)
    msg = make_message("!convert", [att])
    run(msg)
    sent = next(s for s in msg.channel.sent if s[1].get("file") is not None)
    body = sent[1]["file"].fp.read().decode("utf-8")
    assert "<script>" not in body
    assert "<img" not in body


def test_filename_cannot_break_message_formatting():
    att = FakeAttachment(filename="a`b@everyone.html")
    msg = make_message("!convert", [att])
    run(msg)
    assert "a_b@everyone.html" in msg.channel.sent[0][0]


def test_client_disallows_everyone_and_role_mentions():
    allowed = discord_bot.client._connection.allowed_mentions
    assert allowed.everyone is False
    assert allowed.roles is False
