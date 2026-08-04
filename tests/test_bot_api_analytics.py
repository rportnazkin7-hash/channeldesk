from datetime import date

from bot.bot_api_analytics import _metric_date, _reaction_total


def test_reaction_total():
    class Reaction:
        def __init__(self, total_count):
            self.total_count = total_count

    assert _reaction_total([Reaction(3), Reaction(7)]) == 10
    assert _reaction_total([]) == 0


def test_metric_date_uses_utc_date():
    assert _metric_date() == date.today()
