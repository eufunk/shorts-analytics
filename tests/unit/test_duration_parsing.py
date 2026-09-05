from shorts_analytics.collectors.youtube_public import parse_iso8601_duration


def test_parses_seconds_only():
    assert parse_iso8601_duration("PT45S") == 45


def test_parses_minutes_and_seconds():
    assert parse_iso8601_duration("PT1M30S") == 90


def test_parses_hours_minutes_seconds():
    assert parse_iso8601_duration("PT1H2M3S") == 3723


def test_invalid_format_returns_zero():
    assert parse_iso8601_duration("garbage") == 0


def test_zero_duration():
    assert parse_iso8601_duration("PT0S") == 0
