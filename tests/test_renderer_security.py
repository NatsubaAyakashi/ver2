import re

import pytest
from bs4 import BeautifulSoup

from renderer import build_formatted_html

SCRIPT_TEXT = "<script>alert('tab')</script>"
IMG_TEXT = "<img src=x onerror=alert('name')>"


def render(path, settings):
    return build_formatted_html(path, settings)


def parse(html):
    return BeautifulSoup(html, "html.parser")


def strip_css_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def assert_no_active_content(soup):
    assert soup.find("script") is None
    assert soup.find("img") is None
    for tag in soup.find_all(True):
        assert not [a for a in tag.attrs if a.lower().startswith("on")], tag


def test_new_format_text_is_escaped(fixture_path, default_settings):
    soup = parse(render(fixture_path("xss_log.html"), default_settings))
    assert_no_active_content(soup)
    assert soup.find("div", class_="tabtitle").get_text() == SCRIPT_TEXT
    assert soup.find("p", class_="player").b.get_text() == IMG_TEXT
    assert "<script>alert('body')</script>" in soup.find("p", class_="player").get_text()


def test_old_format_text_is_escaped(fixture_path, default_settings):
    soup = parse(render(fixture_path("xss_log_old.html"), default_settings))
    assert_no_active_content(soup)
    assert soup.find("div", class_="tabtitle").get_text() == SCRIPT_TEXT
    assert soup.find("p", class_="player").b.get_text() == IMG_TEXT


def test_html_title_is_escaped(fixture_path, default_settings):
    default_settings["html_title"] = "</title><script>alert(1)</script>"
    html = render(fixture_path("sample_log.html"), default_settings)
    soup = parse(html)
    assert_no_active_content(soup)
    assert soup.title.get_text() == "</title><script>alert(1)</script>"
    assert soup.h1.get_text() == "</title><script>alert(1)</script>"


def test_attachment_style_title_with_quotes_is_escaped(fixture_path, default_settings):
    default_settings["html_title"] = 'Converted: "><svg onload=alert(1)>.html'
    soup = parse(render(fixture_path("sample_log.html"), default_settings))
    assert soup.find("svg") is None
    assert soup.title.get_text() == 'Converted: "><svg onload=alert(1)>.html'


def test_names_cannot_break_out_of_css_comments(tmp_path, default_settings):
    p = tmp_path / "log.html"
    p.write_text(
        '<div class="tab"><div class="tabtitle">t*/ body{display:none} /*</div>'
        "<p><b>n*/ body{display:none} /*</b><span>x</span></p></div>",
        encoding="utf-8",
    )
    css = parse(render(p, default_settings)).style.get_text()
    assert "display:none" not in strip_css_comments(css)


def test_names_cannot_close_style_element_via_css_comment(tmp_path, default_settings):
    p = tmp_path / "log.html"
    payload = "&lt;/style&gt;&lt;script&gt;alert(1)&lt;/script&gt;"
    p.write_text(
        f'<div class="tab"><div class="tabtitle">{payload}</div>'
        f"<p><b>{payload}</b><span>x</span></p></div>",
        encoding="utf-8",
    )
    html = render(p, default_settings)
    assert "</style><script>" not in html
    assert_no_active_content(parse(html))
    assert len(re.findall(r"</style>", html)) == 1


@pytest.mark.parametrize(
    "key",
    ["global_background", "global_color", "tab_default_background", "tab_default_border"],
)
def test_global_css_values_are_validated(fixture_path, default_settings, key):
    default_settings[key] = "red;}</style><script>alert(1)</script>"
    html = render(fixture_path("sample_log.html"), default_settings)
    assert "<script>" not in html
    assert_no_active_content(parse(html))


@pytest.mark.parametrize("field", ["background", "border", "color", "font_size"])
def test_tab_css_values_are_validated(fixture_path, default_settings, field):
    default_settings["tabs"] = {"main": {field: "1px;}</style><script>alert(1)</script>"}}
    html = render(fixture_path("sample_log.html"), default_settings)
    assert "<script>" not in html
    assert_no_active_content(parse(html))


def test_player_setting_color_is_validated(fixture_path, default_settings):
    default_settings["players"] = {"PC1": {"color": "red;}</style><script>alert(1)</script>"}}
    html = render(fixture_path("sample_log.html"), default_settings)
    assert "<script>" not in html


def test_font_color_attribute_cannot_inject_attributes(tmp_path, default_settings):
    p = tmp_path / "log.html"
    p.write_text(
        "<div class=\"tab\"><div class=\"tabtitle\">t</div>"
        "<p><b>A</b><font color='red\" onmouseover=\"alert(1)'>x</font></p></div>",
        encoding="utf-8",
    )
    soup = parse(render(p, default_settings))
    assert_no_active_content(soup)


def test_literal_br_text_is_not_converted(tmp_path, default_settings):
    p = tmp_path / "log.html"
    p.write_text(
        "<p><span>[main]</span><span>A</span><span>a&lt;br&gt;b</span></p>",
        encoding="utf-8",
    )
    soup = parse(render(p, default_settings))
    assert "a<br>b" in soup.find("p", class_="player").get_text()


# 以下は修正後も維持されるべき正当な値
def test_named_font_color_is_preserved(tmp_path, default_settings):
    p = tmp_path / "log.html"
    p.write_text(
        '<div class="tab"><div class="tabtitle">t</div><p><b>A</b><font color="red">x</font></p></div>',
        encoding="utf-8",
    )
    soup = parse(render(p, default_settings))
    assert soup.find("p", class_="player")["style"] == "color: red;"


def test_valid_tab_font_size_is_preserved(fixture_path, default_settings):
    default_settings["tabs"] = {"main": {"background": "#111111", "border": "#222222", "color": "#333333", "font_size": "12px"}}
    css = parse(render(fixture_path("sample_log.html"), default_settings)).style.get_text()
    assert "font-size: 12px;" in css


def test_non_ascii_and_ampersand_text_round_trips(tmp_path, default_settings):
    p = tmp_path / "log.html"
    p.write_text(
        '<div class="tab"><div class="tabtitle">卓 &amp; 部屋</div>'
        "<p><b>探索者 &amp; 友</b><span>こんにちは &amp; ＞ 3</span></p></div>",
        encoding="utf-8",
    )
    soup = parse(render(p, default_settings))
    assert soup.find("div", class_="tabtitle").get_text() == "卓 & 部屋"
    assert soup.find("p", class_="player").b.get_text() == "探索者 & 友"
    assert "こんにちは & ＞" in soup.find("p", class_="player").get_text()
