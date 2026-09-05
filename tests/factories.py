"""Hilfsfunktionen zum Erzeugen von Test-Fixtures (keine echten API-Calls)."""

from __future__ import annotations

import datetime as dt

from shorts_analytics.models import ClassificationResult, HookType, ShortVideo, Sourced


def make_video(
    video_id: str = "vid1",
    topic: str = "Wissen / Bildung",
    views: int | None = 1000,
    likes: int | None = 100,
    comments: int | None = 10,
    duration_seconds: int = 30,
    retention: float | None = None,
    title: str = "Ein Test-Short",
) -> ShortVideo:
    return ShortVideo(
        video_id=video_id,
        channel_id="channel1",
        channel_title="Test Channel",
        title=title,
        description="Beschreibung",
        published_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        duration_seconds=duration_seconds,
        search_topic=topic,
        views=Sourced.public(views) if views is not None else Sourced.unavailable(),
        likes=Sourced.public(likes) if likes is not None else Sourced.unavailable(),
        comments=Sourced.public(comments) if comments is not None else Sourced.unavailable(),
        average_view_percentage=Sourced.own_analytics(retention) if retention is not None else Sourced.unavailable(),
    )


def make_classification(
    video_id: str = "vid1",
    topic: str = "Wissen / Bildung",
    hook_type: HookType = HookType.DIREKTE_FRAGE,
    format_type: str = "Erklaerung",
) -> ClassificationResult:
    return ClassificationResult(
        video_id=video_id,
        topic=topic,
        hook_type=hook_type,
        format_type=format_type,
        confidence=0.8,
    )
