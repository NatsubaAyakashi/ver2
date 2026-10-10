import ast
import io
import json
import zipfile
from pathlib import Path

import pytest

import bot_logic
from bot_logic import (
    COLOR_COMMANDS,
    MAX_ATTACHMENT_BYTES,
    apply_color_setting,
    apply_preset,
    build_bot_settings,
    display_filename,
    get_auto_delete_time,
    get_guild_key,
    is_attachment_too_large,
    is_html_filename,
    is_valid_color,
    package_output,
    parse_auto_delete_seconds,
    parse_command,
    reset_guild_settings,
)
from renderer import build_formatted_html_from_string


def test_bot_logic_does_not_import_discord():
    tree = ast.parse(Path(bot_logic.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "discord" not in imported


@pytest.mark.parametrize("value", ["#fff", "#FFF", "#000000", "#a1B2c3"])
def test_valid_colors(value):
    assert is_valid_color(value)


@pytest.mark.parametrize(
    "value",
    ["", "fff", "#ff", "#ffff", "#fffff", "#fffffff", "#ggg", "red", "#fff;", "#fff\n",
     "rgb(0,0,0)", "#fff }</style>", None, 123],
)
def test_invalid_colors(value):
    assert not is_valid_color(value)


def test_apply_color_setting_saves_valid_only():
    cache = {}
    assert apply_color_setting(cache, "1", "global_background", "#123456")
    assert cache == {"1": {"global_background": "#123456"}}
    assert not apply_color_setting(cache, "1", "global_background", "red;}")
    assert not apply_color_setting(cache, "2", "global_background", "bad")
    assert cache == {"1": {"global_background": "#123456"}}


def test_apply_color_setting_rejects_unknown_key():
    cache = {}
    assert not apply_color_setting(cache, "1", "auto_delete_time", "#fff")
    assert cache == {}


def test_color_commands_cover_expected_keys():
    assert {c.setting_key for c in COLOR_COMMANDS.values()} == {
        "global_background", "global_color", "tab_default_background", "tab_default_border",
    }
    assert all(is_valid_color(c.example) for c in COLOR_COMMANDS.values())


def test_apply_preset():
    cache = {"1": {"auto_delete_time": 5}}
    preset = apply_preset(cache, "1", "dark")
    assert preset["description"].startswith("ダーク")
    assert cache["1"]["global_background"] == "#202020"
    assert cache["1"]["auto_delete_time"] == 5
    assert "description" not in cache["1"]
    assert apply_preset(cache, "1", "nope") is None


def test_reset_guild_settings():
    cache = {"1": {"global_color": "#fff"}}
    assert reset_guild_settings(cache, "1")
    assert not reset_guild_settings(cache, "1")
    assert cache == {}


@pytest.mark.parametrize("text, expected", [("0", 0), ("60", 60), ("007", 7)])
def test_parse_auto_delete_seconds_ok(text, expected):
    assert parse_auto_delete_seconds(text) == expected


@pytest.mark.parametrize("text", ["-1", "abc", "1.5", ""])
def test_parse_auto_delete_seconds_invalid(text):
    with pytest.raises(ValueError):
        parse_auto_delete_seconds(text)


@pytest.mark.parametrize(
    "config, expected",
    [({}, 60), ({"auto_delete_time": 0}, 0), ({"auto_delete_time": 30}, 30),
     ({"auto_delete_time": -5}, 60), ({"auto_delete_time": "x"}, 60), ({"auto_delete_time": True}, 60)],
)
def test_get_auto_delete_time(config, expected):
    assert get_auto_delete_time(config) == expected


def test_get_guild_key_and_parse_command():
    assert get_guild_key(123) == "123"
    assert get_guild_key(None) == "dm"
    assert parse_command("!set_bg #000") == ("!set_bg", ["#000"])
    assert parse_command("  ") == (None, [])
    assert parse_command(None) == (None, [])


def test_build_bot_settings_defaults_and_title():
    s = build_bot_settings({}, "log.html")
    assert s["global_background"] == "#ffffff"
    assert s["global_color"] == "#000000"
    assert s["tab_default_background"] == "#ffffff"
    assert s["tab_default_border"] == "#999999"
    assert s["html_title"] == "Converted: log.html"
    assert s["tabs"] == {} and s["players"] == {}


def test_build_bot_settings_applies_guild_config_and_drops_invalid_stored_values():
    s = build_bot_settings(
        {"global_background": "#202020", "global_color": "red;}</style>", "tab_default_border": "#555"},
        "x.html",
    )
    assert s["global_background"] == "#202020"
    assert s["global_color"] == "#000000"
    assert s["tab_default_border"] == "#555"


def test_built_settings_work_with_renderer():
    html = build_formatted_html_from_string(
        '<div class="tab"><div class="tabtitle">t</div><p><b>A</b><span>x</span></p></div>',
        build_bot_settings({"global_background": "#202020"}, "<b>x</b>.html"),
    )
    assert "background-color: #202020" in html
    assert "<b>x</b>.html" not in html
    assert "Converted: &lt;b&gt;x&lt;/b&gt;.html" in html


def test_attachment_size_check():
    assert not is_attachment_too_large(0)
    assert not is_attachment_too_large(MAX_ATTACHMENT_BYTES)
    assert is_attachment_too_large(MAX_ATTACHMENT_BYTES + 1)
    assert is_attachment_too_large(None)
    assert is_attachment_too_large(-1)


def test_is_html_filename():
    assert is_html_filename("a.html")
    assert is_html_filename("A.HTML")
    assert not is_html_filename("a.txt")
    assert not is_html_filename(None)


def test_display_filename_neutralizes_markdown_and_newlines():
    assert display_filename("a`b\nc.html") == "a_b_c.html"
    assert display_filename("x" * 200).endswith("…")
    assert len(display_filename("x" * 200)) == 101


def test_package_output_small_is_plain():
    out = package_output("<html>あ</html>", "log.html")
    assert out.filename == "formatted_log.html"
    assert not out.zipped
    assert out.data == "<html>あ</html>".encode()


def test_package_output_large_is_zipped(monkeypatch):
    monkeypatch.setattr(bot_logic, "ZIP_THRESHOLD_BYTES", 100)
    text = "あ" * 1000
    out = package_output(text, "log.html")
    assert out.zipped
    assert out.filename == "formatted_log.html.zip"
    with zipfile.ZipFile(io.BytesIO(out.data)) as zf:
        assert zf.namelist() == ["formatted_log.html"]
        assert zf.read("formatted_log.html").decode("utf-8") == text


def test_settings_round_trip_and_error_handling(tmp_path):
    path = tmp_path / "s.json"
    assert bot_logic.load_settings(path) == {}
    assert bot_logic.save_settings(path, {"1": {"global_color": "#fff"}})
    assert bot_logic.load_settings(path) == {"1": {"global_color": "#fff"}}
    path.write_text("{broken", encoding="utf-8")
    assert bot_logic.load_settings(path) == {}
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert bot_logic.load_settings(path) == {}
    assert not bot_logic.save_settings(tmp_path / "missing_dir" / "s.json", {})
