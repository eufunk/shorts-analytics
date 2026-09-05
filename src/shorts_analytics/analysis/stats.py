"""Quantitative Analyse-Stage: rein deterministische Berechnungen (pandas).

Mittelwerte, Mediane, Quantile, Korrelationen und Gruppierungen werden hier
bewusst NICHT vom LLM berechnet - das waere teurer, langsamer und
fehleranfaelliger als exakte Python-Arithmetik.
"""

from __future__ import annotations

import pandas as pd

from shorts_analytics.config import DURATION_BUCKETS, MIN_RELIABLE_SAMPLE_SIZE
from shorts_analytics.models import AnalysisResult, ClassificationResult, GroupStats, ShortVideo


def build_dataframe(videos: list[ShortVideo], classifications: list[ClassificationResult]) -> pd.DataFrame:
    """Verknuepft Rohdaten und Klassifizierung zu einem flachen DataFrame fuer die Analyse."""
    classification_by_id = {c.video_id: c for c in classifications}

    rows = []
    for video in videos:
        classification = classification_by_id.get(video.video_id)
        rows.append(
            {
                "video_id": video.video_id,
                "views": video.views.value if video.views.is_available else None,
                "likes": video.likes.value if video.likes.is_available else None,
                "comments": video.comments.value if video.comments.is_available else None,
                "duration_seconds": video.duration_seconds,
                "retention": video.retention_proxy(),
                "topic": classification.topic if classification else None,
                "hook_type": classification.hook_type.value if classification else None,
                "format_type": classification.format_type if classification else None,
            }
        )
    return pd.DataFrame(rows)


def analyze(videos: list[ShortVideo], classifications: list[ClassificationResult]) -> AnalysisResult:
    df = build_dataframe(videos, classifications)

    return AnalysisResult(
        by_topic=_group_stats(df, "topic"),
        by_hook_type=_group_stats(df, "hook_type"),
        by_format=_group_stats(df, "format_type"),
        by_duration_bucket=_duration_bucket_stats(df),
        correlations=_correlations(df),
        data_completeness=_data_completeness(df),
    )


def _group_stats(df: pd.DataFrame, group_column: str) -> list[GroupStats]:
    if group_column not in df.columns or df.empty:
        return []

    results: list[GroupStats] = []
    grouped = df.dropna(subset=[group_column]).groupby(group_column)
    for group_value, group_df in grouped:
        sample_size = len(group_df)
        retention_series = group_df["retention"].dropna()
        views_series = group_df["views"].dropna()

        results.append(
            GroupStats(
                group=str(group_value),
                sample_size=sample_size,
                mean_views=float(views_series.mean()) if not views_series.empty else None,
                median_views=float(views_series.median()) if not views_series.empty else None,
                mean_retention=float(retention_series.mean()) if not retention_series.empty else None,
                median_retention=float(retention_series.median()) if not retention_series.empty else None,
                p25_retention=float(retention_series.quantile(0.25)) if not retention_series.empty else None,
                p75_retention=float(retention_series.quantile(0.75)) if not retention_series.empty else None,
                is_reliable=sample_size >= MIN_RELIABLE_SAMPLE_SIZE,
            )
        )
    return sorted(results, key=lambda g: g.sample_size, reverse=True)


def _duration_bucket_stats(df: pd.DataFrame) -> list[GroupStats]:
    if "duration_seconds" not in df.columns or df.empty:
        return []

    def bucket_for(duration: int) -> str | None:
        for label, lower, upper in DURATION_BUCKETS:
            if lower <= duration < upper:
                return label
        return None

    df = df.copy()
    df["duration_bucket"] = df["duration_seconds"].apply(bucket_for)
    return _group_stats(df, "duration_bucket")


def _correlations(df: pd.DataFrame) -> dict[str, float]:
    correlations: dict[str, float] = {}
    if df.empty or "retention" not in df.columns or df["retention"].dropna().empty:
        return correlations

    for column in ("views", "likes", "comments", "duration_seconds"):
        if column not in df.columns:
            continue
        subset = df[[column, "retention"]].dropna()
        if len(subset) < MIN_RELIABLE_SAMPLE_SIZE:
            continue
        correlation = subset[column].corr(subset["retention"])
        if correlation is not None and not pd.isna(correlation):
            correlations[f"{column}_vs_retention"] = float(correlation)
    return correlations


def _data_completeness(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    completeness: dict[str, float] = {}
    for column in ("views", "likes", "comments", "retention", "topic", "hook_type"):
        if column not in df.columns:
            continue
        completeness[column] = float(df[column].notna().mean())
    return completeness
