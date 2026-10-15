import pytest

from app.classes.web.public_handler import PublicHandler


@pytest.mark.parametrize(
    "next_url",
    [
        "/panel/dashboard",
        "/panel/server_detail?id=abc&subpage=term",
        "/panel/panel_config",
    ],
)
def test_safe_next_url_allows_local_paths(next_url) -> None:
    assert PublicHandler.safe_next_url(next_url) == next_url


@pytest.mark.parametrize(
    "next_url",
    [
        "",
        None,
        "https://evil.example/",
        "//evil.example/path",
        "/\\evil.example",
        "panel/dashboard",
        "javascript:alert(1)",
        "/panel/dashboard\nSet-Cookie: x=y",
        "/login",
        "/login?next=/login",
        "/logout",
    ],
)
def test_safe_next_url_rejects_unsafe_values(next_url) -> None:
    assert PublicHandler.safe_next_url(next_url) == ""
