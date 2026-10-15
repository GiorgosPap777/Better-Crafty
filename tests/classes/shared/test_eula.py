import pytest

from app.classes.shared.server import is_eula_accepted


@pytest.mark.parametrize(
    "content, expected",
    [
        ("eula=true", True),
        ("eula=true\n", True),
        ("eula = TRUE\n", True),
        (
            "#By changing the setting below to TRUE you are indicating your"
            " agreement to our EULA (https://aka.ms/MinecraftEULA).\n"
            "#Tue Oct 15 07:38:41 UTC 2026\n"
            "eula=true\n",
            True,
        ),
        ("eula=false\n", False),
        ("#eula=true\neula=false\n", False),
        ("", False),
    ],
)
def test_is_eula_accepted(tmp_path, content, expected) -> None:
    eula = tmp_path / "eula.txt"
    eula.write_text(content, encoding="utf-8")
    assert is_eula_accepted(str(eula)) is expected


def test_is_eula_accepted_missing_file(tmp_path) -> None:
    assert is_eula_accepted(str(tmp_path / "eula.txt")) is False
