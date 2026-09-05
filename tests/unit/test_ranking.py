from shorts_analytics.analysis.ranking import rank_groups
from shorts_analytics.models import GroupStats


def test_ranks_by_retention_when_available():
    groups = [
        GroupStats(group="A", sample_size=10, mean_retention=0.3, mean_views=500, is_reliable=True),
        GroupStats(group="B", sample_size=10, mean_retention=0.7, mean_views=100, is_reliable=True),
    ]
    entries = rank_groups(groups)
    assert entries[0].group == "B"
    assert entries[0].metric_name == "mean_retention"


def test_falls_back_to_views_when_no_retention_data():
    groups = [
        GroupStats(group="A", sample_size=10, mean_views=100, is_reliable=True),
        GroupStats(group="B", sample_size=10, mean_views=900, is_reliable=True),
    ]
    entries = rank_groups(groups)
    assert entries[0].group == "B"
    assert entries[0].metric_name == "mean_views"


def test_unreliable_groups_are_not_hidden_but_ranked_last():
    groups = [
        GroupStats(group="reliable", sample_size=10, mean_views=100, is_reliable=True),
        GroupStats(group="unreliable_but_high", sample_size=2, mean_views=99999, is_reliable=False),
    ]
    entries = rank_groups(groups)
    assert [e.group for e in entries] == ["reliable", "unreliable_but_high"]
    assert entries[1].is_reliable is False


def test_empty_groups_returns_empty_ranking():
    assert rank_groups([]) == []
