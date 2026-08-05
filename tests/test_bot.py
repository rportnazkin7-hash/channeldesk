from bot.main import extract_invite_token, welcome_keyboard


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


def test_welcome_keyboard_has_inline_navigation(monkeypatch):
    monkeypatch.setenv('MINI_APP_URL', 'https://channeldesk.vercel.app')
    keyboard = welcome_keyboard(True)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert 'О ChannelDesk' in labels
    assert 'Как пользоваться' in labels
    assert 'Переслать → черновик' in labels
    assert 'Открыть Mini App' in labels
    assert 'Канал обновлений' in labels


def test_closed_welcome_keyboard_hides_mini_app(monkeypatch):
    monkeypatch.setenv('MINI_APP_URL', 'https://channeldesk.vercel.app')
    keyboard = welcome_keyboard(False)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert 'Открыть Mini App' not in labels
    assert 'Канал обновлений' in labels
