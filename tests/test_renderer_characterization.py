import pytest
from bs4 import BeautifulSoup

from renderer import build_formatted_html


def parse(html):
    return BeautifulSoup(html, "html.parser")


@pytest.fixture
def new_soup(fixture_path, default_settings):
    return parse(build_formatted_html(fixture_path("sample_log.html"), default_settings))


@pytest.fixture
def old_soup(fixture_path, default_settings):
    return parse(build_formatted_html(fixture_path("sample_log_old.html"), default_settings))


def test_document_skeleton(fixture_path, default_settings):
    html = build_formatted_html(fixture_path("sample_log.html"), default_settings)
    assert html.startswith("<!DOCTYPE html>")
    soup = parse(html)
    assert soup.title.get_text() == "Test Title"
    assert soup.h1.get_text() == "Test Title"
    assert "background-color: #ffffff" in soup.style.get_text()


def test_new_format_tabs(new_soup):
    tabs = new_soup.find_all("div", class_="tab")
    assert [t.find("div", class_="tabtitle").get_text() for t in tabs] == ["main", "sub"]
    assert "t0" in tabs[0]["class"]
    assert "t1" in tabs[1]["class"]


def test_new_format_players_and_inline_colors(new_soup):
    rows = new_soup.find_all("p", class_="player")
    assert [r.b.get_text() for r in rows] == ["KP", "PC1", "PC2", "KP"]
    assert [r["class"][1] for r in rows] == ["p0", "p1", "p2", "p0"]
    assert [r["style"] for r in rows] == [
        "color: #ff0000;",
        "color: #0000ff;",
        "color: #00aa00;",
        "color: #0a0;",
    ]


def test_new_format_css_uses_last_color_per_player_and_normalizes_rgb(new_soup):
    css = new_soup.style.get_text()
    assert ".p0 { color: #0a0; }" in css
    assert ".p1 { color: #0000ff; }" in css
    assert ".p2 { color: #00aa00; }" in css


def test_new_format_dice_roll_wrapped(new_soup):
    rolls = new_soup.find_all("span", class_="diceroll")
    assert [r.get_text() for r in rolls] == ["42"]


def test_new_format_body_text(new_soup):
    rows = new_soup.find_all("p", class_="player")
    assert "探索を開始します" in rows[0].get_text()
    assert "1D100<=50" in rows[1].get_text()
    assert "雑談です" in rows[2].get_text()


def test_old_format_tabs(old_soup):
    tabs = old_soup.find_all("div", class_="tab")
    assert [t.find("div", class_="tabtitle").get_text() for t in tabs] == ["main", "sub"]


def test_old_format_merges_consecutive_same_speaker(old_soup):
    main_rows = old_soup.find_all("div", class_="tab")[0].find_all("p", class_="player")
    assert [r.b.get_text() for r in main_rows] == ["Alice", "Bob"]
    lines = [line for line in main_rows[0].get_text().splitlines() if line]
    assert lines == ["Alice", "hi ＞ 12", "more"]


def test_old_format_dice_and_color(old_soup):
    assert [r.get_text() for r in old_soup.find_all("span", class_="diceroll")] == ["12", "77"]
    alice = old_soup.find("p", class_="player")
    assert alice["style"] == "color: #f00;"
    assert ".p1 { color: #888888; }" in old_soup.style.get_text()


def test_settings_background_and_title_applied(fixture_path, default_settings):
    default_settings["global_background"] = "#202020"
    default_settings["global_color"] = "#fafafa"
    default_settings["html_title"] = "Custom"
    soup = parse(build_formatted_html(fixture_path("sample_log.html"), default_settings))
    css = soup.style.get_text()
    assert "background-color: #202020; color: #fafafa;" in css
    assert soup.title.get_text() == "Custom"


def test_tab_settings_applied(fixture_path, default_settings):
    default_settings["tabs"] = {"main": {"background": "#112233", "border": "#445566", "color": "#778899"}}
    soup = parse(build_formatted_html(fixture_path("sample_log.html"), default_settings))
    css = soup.style.get_text()
    assert ".t0 { background-color: #112233; border-color: #445566; color: #778899; }" in css
    assert soup.find("div", class_="tab")["style"] == "background-color: #112233;"


def test_player_setting_color_overrides_html_color(fixture_path, default_settings):
    default_settings["players"] = {"PC1": {"color": "#123456"}}
    soup = parse(build_formatted_html(fixture_path("sample_log.html"), default_settings))
    assert ".p1 { color: #123456; }" in soup.style.get_text()


def test_settings_none_falls_back_to_config(fixture_path, monkeypatch):
    import config as config_module

    monkeypatch.setitem(config_module.config, "html_title", "From Config")
    soup = parse(build_formatted_html(fixture_path("sample_log.html")))
    assert soup.title.get_text() == "From Config"


def test_accepts_str_path(fixture_path, default_settings):
    html = build_formatted_html(str(fixture_path("sample_log.html")), default_settings)
    assert "<!DOCTYPE html>" in html


def test_empty_log_produces_valid_skeleton(tmp_path, default_settings):
    p = tmp_path / "empty.html"
    p.write_text("<html><body></body></html>", encoding="utf-8")
    soup = parse(build_formatted_html(p, default_settings))
    assert soup.find("div", class_="tab") is None
    assert soup.h1.get_text() == "Test Title"


def test_from_string_matches_file_wrapper(fixture_path, default_settings):
    from renderer import build_formatted_html_from_string

    path = fixture_path("sample_log.html")
    text = path.read_text(encoding="utf-8")
    assert build_formatted_html_from_string(text, default_settings) == build_formatted_html(path, default_settings)


def test_from_string_old_format_matches_file_wrapper(fixture_path, default_settings):
    from renderer import build_formatted_html_from_string

    path = fixture_path("sample_log_old.html")
    text = path.read_text(encoding="utf-8")
    assert build_formatted_html_from_string(text, default_settings) == build_formatted_html(path, default_settings)
