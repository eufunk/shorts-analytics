import datetime as dt

from shorts_analytics.validation.validators import validate_videos
from tests.factories import make_video


def test_valid_video_passes():
    result = validate_videos([make_video()])
    assert len(result.valid) == 1
    assert result.rejected == []


def test_rejects_zero_duration():
    video = make_video(duration_seconds=0)
    result = validate_videos([video])
    assert result.valid == []
    assert result.rejected[0][1] == "ungueltige Videolaenge (<= 0s)"


def test_rejects_negative_views():
    video = make_video(views=-5)
    result = validate_videos([video])
    assert result.valid == []
    assert "negative Aufrufzahl" in result.rejected[0][1]


def test_rejects_future_publish_date():
    video = make_video()
    video.published_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    result = validate_videos([video])
    assert result.valid == []
    assert "Zukunft" in result.rejected[0][1]


def test_rejects_empty_title():
    video = make_video(title="   ")
    result = validate_videos([video])
    assert result.valid == []
    assert "Titel" in result.rejected[0][1]
