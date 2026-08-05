from datetime import date

from bot.daily_pulse import render_pulse


def test_render_pulse_contains_actionable_summary():
    text = render_pulse({'id': 3, 'name': 'Моё агентство'}, date(2026, 8, 4), {
        'scheduled': 3, 'starts_today': 1, 'published': 2, 'review': 1,
        'due_today': 2, 'unpaid': 1, 'overdue': 1, 'failed': 0, 'income': 15000,
    })
    assert 'ChannelDesk Pulse' in text
    assert 'публикаций по плану: 3' in text
    assert 'неоплаченных броней: 1' in text
    assert '15 000.00 ₽' in text
