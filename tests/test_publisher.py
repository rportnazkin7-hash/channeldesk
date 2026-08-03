import io
import json
from urllib.error import HTTPError

import pytest

from bot.publisher import _telegram_request, datetime_now_iso, is_retryable_error


def test_retryable_network_errors():
    assert is_retryable_error('Network error: timed out')
    assert is_retryable_error('Network error: [Errno 111] Connection refused')
    assert is_retryable_error('HTTP 500: Internal Server Error')
    assert is_retryable_error('HTTP 503: Service Unavailable')
    assert is_retryable_error('HTTP 429: Too Many Requests')


def test_final_errors_not_retryable():
    assert not is_retryable_error("HTTP 400: cannot parse entities")
    assert not is_retryable_error('HTTP 403: Forbidden: bot is not a member')
    assert not is_retryable_error('HTTP 404: chat not found')


def test_empty_error_is_retryable():
    assert is_retryable_error('')
    assert is_retryable_error(None)


def test_telegram_request_success(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({'ok': True, 'result': {'message_id': 42}}).encode()

    def fake_urlopen(req, timeout):
        assert req.full_url.startswith('https://api.telegram.org/botTOKEN/sendMessage')
        assert timeout == 15
        return FakeResp()

    monkeypatch.setattr('bot.publisher.urlopen', fake_urlopen)
    result = _telegram_request('TOKEN', 'sendMessage', {'chat_id': -100, 'text': 'hi'})
    assert result['ok'] is True
    assert result['result']['message_id'] == 42


def test_telegram_request_http_error(monkeypatch):
    def fake_urlopen(req, timeout):
        raise HTTPError(req.full_url, 400, 'Bad Request', None, io.BytesIO(b'{"ok":false,"description":"bad html"}'))

    monkeypatch.setattr('bot.publisher.urlopen', fake_urlopen)
    with pytest.raises(RuntimeError) as exc:
        _telegram_request('TOKEN', 'sendMessage', {'chat_id': -100, 'text': '<bad'})
    assert 'HTTP 400' in str(exc.value)


def test_now_iso_is_utc():
    value = datetime_now_iso()
    assert value.endswith('+00:00') or value.endswith('Z') or '+' in value
