import pytest
from bs4 import BeautifulSoup

from analyzer.analyzer import (
    extract_color_from_p_or_spans,
    extract_players_and_tabs,
    extract_roll_lines,
)


def p_tag(html):
    return BeautifulSoup(html, "html.parser").find("p")


@pytest.mark.parametrize(
    "html, expected",
    [
        ('<p style="color:#ff0000"><b>A</b></p>', "#ff0000"),
        ('<p><b style="color:#abc">A</b></p>', "#abc"),
        ('<p><span>x</span><span style="color: rgb(255, 0, 16)">y</span></p>', "#ff0010"),
        ('<p><font color="#00aa00">x</font></p>', "#00aa00"),
        ("<p><b>A</b></p>", None),
        ('<p style="color:#111111"><b style="color:#222222">A</b></p>', "#111111"),
        ('<p><b style="color:#222222">A</b><span style="color:#333333">x</span></p>', "#222222"),
    ],
)
def test_extract_color_from_p_or_spans(html, expected):
    assert extract_color_from_p_or_spans(p_tag(html)) == expected


def test_extract_players_and_tabs_new_format(fixture_path):
    result = extract_players_and_tabs(fixture_path("sample_log.html"))
    assert result["tabs"] == ["main", "sub"]
    assert result["players"] == {
        "KP": {"color": "#ff0000", "count": 2},
        "PC1": {"color": "#0000ff", "count": 1},
        "PC2": {"color": "#00aa00", "count": 1},
    }
    assert result["tab_colors"] == {"main": "#eeeeee", "sub": "#ddeeff"}
    assert "<html" in result["html"]


def test_extract_players_and_tabs_old_format(fixture_path):
    result = extract_players_and_tabs(fixture_path("sample_log_old.html"))
    assert result["tabs"] == ["main", "sub"]
    assert result["players"] == {
        "Alice": {"color": "#f00", "count": 2},
        "Bob": {"color": None, "count": 2},
    }
    assert result["tab_colors"] == {}


def test_extract_roll_lines_new_format(fixture_path):
    entries = extract_roll_lines(fixture_path("sample_log.html"))
    assert entries == [
        {
            "tab": "main",
            "name": "PC1",
            "text": "PC1 1D100<=50 ＞ 42 ＞ 成功",
            "rolls": ["42"],
        }
    ]


def test_extract_roll_lines_old_format_has_no_tab(fixture_path):
    entries = extract_roll_lines(fixture_path("sample_log_old.html"))
    assert len(entries) == 1
    assert entries[0]["name"] == "Bob"
    assert entries[0]["tab"] is None
    assert entries[0]["rolls"] == ["77"]


def test_extract_players_empty_document(tmp_path):
    p = tmp_path / "e.html"
    p.write_text("<html></html>", encoding="utf-8")
    result = extract_players_and_tabs(p)
    assert result["players"] == {}
    assert result["tabs"] == []
