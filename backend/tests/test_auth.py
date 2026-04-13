from app.auth import login, verify_token


def test_login_and_verify() -> None:
    token = login("admin", "admin123")
    payload = verify_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_login_finance_role() -> None:
    token = login("finance", "finance123")
    payload = verify_token(token)
    assert payload["role"] == "finance"
