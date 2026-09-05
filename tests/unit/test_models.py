from shorts_analytics.models import DataSource, Sourced
from tests.factories import make_video


def test_sourced_unavailable_is_not_available():
    sourced = Sourced.unavailable()
    assert sourced.is_available is False
    assert sourced.value is None
    assert sourced.source == DataSource.UNAVAILABLE


def test_sourced_public_value_is_available():
    sourced = Sourced.public(42)
    assert sourced.is_available is True
    assert sourced.value == 42


def test_retention_proxy_returns_none_when_no_own_analytics():
    video = make_video(retention=None)
    assert video.retention_proxy() is None


def test_retention_proxy_returns_own_analytics_value():
    video = make_video(retention=0.75)
    assert video.retention_proxy() == 0.75


def test_retention_proxy_never_falls_back_to_views():
    """Views/Likes duerfen NIEMALS als Retention-Ersatz verwendet werden."""
    video = make_video(views=1_000_000, likes=100_000, retention=None)
    assert video.retention_proxy() is None
