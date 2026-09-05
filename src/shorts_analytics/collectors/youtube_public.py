"""Collector fuer oeffentliche YouTube-Daten (Ebene 1) ueber die YouTube Data API v3.

Reines API-Handling ohne semantisches Verstaendnis -> deterministischer
Python-Code, kein LLM noetig.
"""

from __future__ import annotations

import datetime as dt
import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from shorts_analytics.config import DEFAULT_MAX_RESULTS_PER_QUERY, MAX_SHORT_DURATION_SECONDS
from shorts_analytics.models import ShortVideo, Sourced

_ISO8601_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def parse_iso8601_duration(value: str) -> int:
    """Wandelt eine ISO-8601-Dauer (z.B. 'PT45S') in Sekunden um."""
    match = _ISO8601_DURATION_RE.fullmatch(value)
    if not match:
        return 0
    parts = match.groupdict(default="0")
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YouTubePublicCollector:
    """Sammelt oeffentlich sichtbare Metadaten und Statistiken fuer YouTube Shorts.

    Verwendet ausschliesslich die YouTube Data API v3 (search.list + videos.list),
    liefert also Ebene-1-Daten (Views, Likes, Kommentare, Laenge, Titel usw.).
    Retention-Daten (Ebene 2) sind hierueber grundsaetzlich NICHT erreichbar,
    siehe collectors/youtube_studio.py.
    """

    def __init__(self, api_key: str) -> None:
        self._youtube = build("youtube", "v3", developerKey=api_key)

    def search_shorts(self, query: str, max_results: int = DEFAULT_MAX_RESULTS_PER_QUERY) -> list[str]:
        """Sucht nach Videos zu einer Suchanfrage und gibt Video-IDs zurueck."""
        try:
            response = (
                self._youtube.search()
                .list(
                    q=query,
                    part="id",
                    type="video",
                    videoDuration="short",
                    order="viewCount",
                    maxResults=min(max_results, 50),
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"YouTube-Suche fuer '{query}' fehlgeschlagen: {exc}") from exc

        return [
            item["id"]["videoId"]
            for item in response.get("items", [])
            if "videoId" in item.get("id", {})
        ]

    def fetch_video_details(self, video_ids: list[str], search_topic: str) -> list[ShortVideo]:
        """Holt Statistik- und Metadaten fuer eine Liste von Video-IDs."""
        if not video_ids:
            return []

        videos: list[ShortVideo] = []
        # videos.list erlaubt maximal 50 IDs pro Aufruf.
        for batch_start in range(0, len(video_ids), 50):
            batch = video_ids[batch_start : batch_start + 50]
            try:
                response = (
                    self._youtube.videos()
                    .list(part="snippet,statistics,contentDetails", id=",".join(batch))
                    .execute()
                )
            except HttpError as exc:
                raise RuntimeError(f"Abruf der Video-Details fehlgeschlagen: {exc}") from exc

            for item in response.get("items", []):
                video = self._parse_video_item(item, search_topic)
                if video is not None:
                    videos.append(video)
        return videos

    def _parse_video_item(self, item: dict, search_topic: str) -> ShortVideo | None:
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})

        duration_raw = content_details.get("duration")
        if not duration_raw:
            return None
        duration_seconds = parse_iso8601_duration(duration_raw)
        if duration_seconds <= 0 or duration_seconds > MAX_SHORT_DURATION_SECONDS:
            return None

        published_at_raw = snippet.get("publishedAt")
        try:
            published_at = dt.datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            return None

        views = (
            Sourced.public(int(statistics["viewCount"])) if "viewCount" in statistics else Sourced.unavailable()
        )
        likes = (
            Sourced.public(int(statistics["likeCount"])) if "likeCount" in statistics else Sourced.unavailable()
        )
        comments = (
            Sourced.public(int(statistics["commentCount"]))
            if "commentCount" in statistics
            else Sourced.unavailable()
        )

        return ShortVideo(
            video_id=item["id"],
            channel_id=snippet.get("channelId", ""),
            channel_title=snippet.get("channelTitle", ""),
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            published_at=published_at,
            duration_seconds=duration_seconds,
            thumbnail_url=(snippet.get("thumbnails", {}).get("high", {}) or {}).get("url"),
            search_topic=search_topic,
            views=views,
            likes=likes,
            comments=comments,
        )
