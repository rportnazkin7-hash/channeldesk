from bot.main import extract_invite_token


def test_plain_start_has_no_token():
    assert extract_invite_token('/start') is None


def test_non_invite_payload_ignored():
    assert extract_invite_token('/start hello') is None


def test_invite_token_extracted():
    assert extract_invite_token('/start invite_AbC123xYz') == 'AbC123xYz'


def test_empty_invite_token_rejected():
    assert extract_invite_token('/start invite_') is None


def test_surrounding_whitespace_tolerated():
    assert extract_invite_token('  /start  invite_token123  ') == 'token123'
