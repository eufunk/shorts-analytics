"""Ranking-Stage: sortiert bereits berechnete Gruppen-Statistiken.

Deterministisch - reine Sortierung/Filterung der Ergebnisse aus stats.py.
"""

from __future__ import annotations

from shorts_analytics.models import GroupStats, RankingEntry


def rank_groups(groups: list[GroupStats], top_n: int = 10) -> list[RankingEntry]:
    """Rankt Gruppen nach mittlerer Zuschauerbindung, falls verfuegbar,
    sonst nach mittleren Aufrufen als Naeherung (klar benannt ueber metric_name).

    Unzuverlaessige Gruppen (zu kleine Stichprobe) werden NICHT verschwiegen,
    sondern hinter den zuverlaessigen einsortiert und explizit als
    is_reliable=False markiert.
    """
    if not groups:
        return []

    has_retention = any(g.mean_retention is not None for g in groups)
    metric_name = "mean_retention" if has_retention else "mean_views"

    def metric_value(group: GroupStats) -> float | None:
        return group.mean_retention if has_retention else group.mean_views

    scored = [(group, metric_value(group)) for group in groups]
    scored = [item for item in scored if item[1] is not None]
    scored.sort(key=lambda item: (item[0].is_reliable, item[1]), reverse=True)

    entries: list[RankingEntry] = []
    for rank, (group, value) in enumerate(scored[:top_n], start=1):
        entries.append(
            RankingEntry(
                rank=rank,
                group=group.group,
                metric_name=metric_name,
                metric_value=value,
                sample_size=group.sample_size,
                is_reliable=group.is_reliable,
            )
        )
    return entries
