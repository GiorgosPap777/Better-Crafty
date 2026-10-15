from unittest.mock import MagicMock

import pytest

from app.classes.controllers import passkey_controller
from app.classes.controllers.passkey_controller import PasskeyController


@pytest.mark.parametrize("others_left, expect_reset", [(False, True), (True, False)])
def test_deleting_last_passkey_re_enables_password_login(
    monkeypatch, others_left, expect_reset
) -> None:
    passkey = MagicMock()
    passkey.user.user_id = 7
    monkeypatch.setattr(
        passkey_controller.PasskeyData, "get_or_none", lambda *_: passkey
    )
    remaining = MagicMock()
    remaining.exists.return_value = others_left
    monkeypatch.setattr(
        passkey_controller.HelperPasskey,
        "get_user_passkeys",
        staticmethod(lambda _user_id: remaining),
    )
    update_user = MagicMock()
    monkeypatch.setattr(
        passkey_controller.HelperUsers, "update_user", staticmethod(update_user)
    )
    helper = MagicMock()
    controller = PasskeyController(helper, MagicMock())

    assert controller.delete_passkey("pk-1", 7)
    helper.delete_passkey.assert_called_once_with("pk-1")
    if expect_reset:
        update_user.assert_called_once_with(7, {"disable_password_auth": False})
    else:
        update_user.assert_not_called()


def test_cannot_delete_someone_elses_passkey(monkeypatch) -> None:
    passkey = MagicMock()
    passkey.user.user_id = 8
    monkeypatch.setattr(
        passkey_controller.PasskeyData, "get_or_none", lambda *_: passkey
    )
    helper = MagicMock()
    controller = PasskeyController(helper, MagicMock())
    assert controller.delete_passkey("pk-1", 7) is False
    helper.delete_passkey.assert_not_called()
