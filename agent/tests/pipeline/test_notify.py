from unittest.mock import patch


@patch("scripts.pipeline.notify.telegram_notify")
def test_send_digest_no_failures(mock_tg):
    from scripts.pipeline.notify import send_daily_digest
    send_daily_digest()
    mock_tg.assert_not_called()


@patch("scripts.pipeline.notify.telegram_notify")
def test_send_digest_with_failures(mock_tg):
    from scripts.pipeline.notify import send_daily_digest
    send_daily_digest(
        enrich_failures=[(1, "timeout"), (2, "login wall")],
        screen_failures=[(3, "error")],
    )
    mock_tg.assert_called_once()
    msg = mock_tg.call_args[0][0]
    assert "enrich" in msg.lower()
    assert "screen" in msg.lower()
    assert "2" in msg
