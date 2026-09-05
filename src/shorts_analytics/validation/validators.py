"""Validierungs-Stage: prueft rohe ShortVideo-Objekte auf Plausibilitaet.

Rein regelbasiert (kein LLM) - Datenintegritaet ist eine Frage von
Grenzwerten und Konsistenzchecks, nicht von semantischem Verstaendnis.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from shorts_analytics.models import ShortVideo


@dataclass
class ValidationResult:
    valid: list[ShortVideo] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (video_id, reason)


def validate_videos(videos: list[ShortVideo]) -> ValidationResult:
    result = ValidationResult()
    now = dt.datetime.now(dt.timezone.utc)

    for video in videos:
        reason = _find_rejection_reason(video, now)
        if reason is None:
            result.valid.append(video)
        else:
            result.rejected.append((video.video_id or "<ohne id>", reason))

    return result


def _find_rejection_reason(video: ShortVideo, now: dt.datetime) -> str | None:
    if not video.video_id:
        return "fehlende video_id"
    if not video.title.strip():
        return "fehlender Titel"
    if video.duration_seconds <= 0:
        return "ungueltige Videolaenge (<= 0s)"
    if video.published_at > now:
        return "Veroeffentlichungsdatum liegt in der Zukunft"
    if video.views.is_available and video.views.value < 0:
        return "negative Aufrufzahl"
    if video.likes.is_available and video.likes.value < 0:
        return "negative Like-Anzahl"
    return None
