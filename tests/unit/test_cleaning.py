from shorts_analytics.preprocessing.cleaning import clean_videos
from tests.factories import make_video


def test_deduplicates_by_video_id():
    videos = [make_video(video_id="a"), make_video(video_id="a"), make_video(video_id="b")]
    result = clean_videos(videos)
    assert len(result.videos) == 2
    assert result.duplicates_removed == 1


def test_normalizes_whitespace():
    video = make_video()
    video.title = "  Titel mit Leerzeichen  "
    result = clean_videos([video])
    assert result.videos[0].title == "Titel mit Leerzeichen"


def test_flags_view_outliers_without_removing_them():
    normal_videos = [make_video(video_id=f"v{i}", views=1000 + i) for i in range(10)]
    outlier = make_video(video_id="viral", views=10_000_000)
    result = clean_videos(normal_videos + [outlier])

    assert len(result.videos) == 11  # nichts wird entfernt
    assert "viral" in result.outlier_video_ids


def test_no_outliers_with_small_sample():
    result = clean_videos([make_video(video_id="a"), make_video(video_id="b")])
    assert result.outlier_video_ids == []
