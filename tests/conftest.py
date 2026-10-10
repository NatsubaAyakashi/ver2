from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_path():
    def _get(name: str) -> Path:
        return FIXTURES / name

    return _get


@pytest.fixture
def default_settings():
    return {
        "html_title": "Test Title",
        "global_background": "#ffffff",
        "global_color": "#000000",
        "tab_default_background": "#ffffff",
        "tab_default_border": "#999999",
        "tabs": {},
        "players": {},
    }
