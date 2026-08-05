from datetime import datetime, timezone

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, PhotoSize

from bot.forward_capture import _buttons, _html_text, _title, extract_media


def message_with_text(**kwargs):
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat={'id': 100, 'type': 'private'},
        **kwargs,
    )


def test_forward_text_becomes_safe_html_and_title():
    message = message_with_text(text='Заголовок\nЦена < 100 ₽')
    assert _title(message, []) == 'Заголовок'
    assert '&lt; 100' in _html_text(message)


def test_forward_photo_extracts_largest_photo():
    message = message_with_text(
        caption='Фото дня',
        photo=[
            PhotoSize(file_id='small', file_unique_id='small-1', width=100, height=100),
            PhotoSize(file_id='large', file_unique_id='large-1', width=1000, height=1000),
        ],
    )
    media = extract_media(message)
    assert len(media) == 1
    assert media[0].file_id == 'large'
    assert media[0].file_type == 'image/jpeg'
    assert _title(message, media) == 'Фото дня'


def test_forwarded_url_buttons_are_copied():
    message = message_with_text(
        text='Пост',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='Открыть', url='https://example.com'),
            InlineKeyboardButton(text='Callback', callback_data='skip'),
        ]]),
    )
    assert _buttons(message) == [[{'text': 'Открыть', 'url': 'https://example.com'}]]
