"""Bereinigungs-Stage: Duplikate entfernen, Texte normalisieren, Ausreisser markieren.

Deterministisch (kein LLM) - reine Datenhygiene.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shorts_analytics.models import ShortVideo


@dataclass
class CleaningResult:
    videos: list[ShortVideo] = field(default_factory=list)
    duplicates_removed: int = 0
    outlier_video_ids: list[str] = field(default_factory=list)


def clean_videos(videos: list[ShortVideo]) -> CleaningResult:
    deduped, duplicates_removed = _deduplicate(videos)
    normalized = [_normalize(video) for video in deduped]
    outlier_ids = _flag_view_outliers(normalized)
    return CleaningResult(videos=normalized, duplicates_removed=duplicates_removed, outlier_video_ids=outlier_ids)


def _deduplicate(videos: list[ShortVideo]) -> tuple[list[ShortVideo], int]:
    seen: dict[str, ShortVideo] = {}
    duplicates = 0
    for video in videos:
        if video.video_id in seen:
            duplicates += 1
            continue
        seen[video.video_id] = video
    return list(seen.values()), duplicates


def _normalize(video: ShortVideo) -> ShortVideo:
    video.title = video.title.strip()
    video.description = video.description.strip()
    video.channel_title = video.channel_title.strip()
    return video


def _flag_view_outliers(videos: list[ShortVideo]) -> list[str]:
    """Markiert Videos, deren Aufrufzahl per IQR-Methode als Ausreisser gilt.

    Ausreisser werden NICHT entfernt (koennten gerade die interessanten
    viralen Faelle sein), nur zur Transparenz im Report markiert.
    """
    values = sorted(v.views.value for v in videos if v.views.is_available)
    if len(values) < 4:
        return []

    q1 = _percentile(values, 25)
    q3 = _percentile(values, 75)
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr

    return [v.video_id for v in videos if v.views.is_available and v.views.value > upper_bound]


def _percentile(sorted_values: list[int], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (percentile / 100)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)
