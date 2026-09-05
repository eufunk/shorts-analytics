from shorts_analytics.analysis.stats import analyze
from shorts_analytics.config import MIN_RELIABLE_SAMPLE_SIZE
from tests.factories import make_classification, make_video


def test_group_stats_marks_small_samples_as_unreliable():
    videos = [make_video(video_id=f"a{i}", topic="Wissen") for i in range(3)]
    classifications = [make_classification(video_id=f"a{i}", topic="Wissen") for i in range(3)]

    result = analyze(videos, classifications)

    assert len(result.by_topic) == 1
    assert result.by_topic[0].sample_size == 3
    assert result.by_topic[0].is_reliable is False


def test_group_stats_marks_large_samples_as_reliable():
    n = MIN_RELIABLE_SAMPLE_SIZE
    videos = [make_video(video_id=f"b{i}", topic="Wissen", views=1000 + i * 10) for i in range(n)]
    classifications = [make_classification(video_id=f"b{i}", topic="Wissen") for i in range(n)]

    result = analyze(videos, classifications)

    assert result.by_topic[0].sample_size == n
    assert result.by_topic[0].is_reliable is True
    assert result.by_topic[0].mean_views is not None


def test_retention_stats_are_none_when_no_own_analytics_data():
    videos = [make_video(video_id=f"c{i}", retention=None) for i in range(5)]
    classifications = [make_classification(video_id=f"c{i}") for i in range(5)]

    result = analyze(videos, classifications)

    assert result.by_topic[0].mean_retention is None
    assert result.data_completeness.get("retention") == 0.0


def test_data_completeness_reflects_available_retention():
    videos = [make_video(video_id=f"d{i}", retention=0.5) for i in range(4)]
    classifications = [make_classification(video_id=f"d{i}") for i in range(4)]

    result = analyze(videos, classifications)

    assert result.data_completeness["retention"] == 1.0
    assert result.by_topic[0].mean_retention == 0.5
