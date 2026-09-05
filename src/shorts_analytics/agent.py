"""ResearchAgent: orchestriert den vollstaendigen Analyse-Workflow.

Der Agent ist bewusst KEIN autonomer Tool-Calling-Loop, sondern eine feste
Pipeline aus klar benannten Stages:

    Research -> Datensammlung -> Validierung -> Bereinigung -> Klassifizierung
    -> Quantitative Analyse -> Mustererkennung -> Ranking -> Report

Ein LLM wird nur an einzelnen, klar markierten Stages aufgerufen
(Klassifizierung, Musterinterpretation, Report-Formulierung). Alle Stages
tauschen ausschliesslich typisierte Modelle aus (models.py). Fehler werden
pro Stage/Item protokolliert statt den ganzen Lauf abzubrechen, wo immer das
sinnvoll ist - nur wenn eine Stage gar keine verwertbaren Daten liefert,
bricht der jeweilige Teil ab.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

from shorts_analytics import config, persistence
from shorts_analytics.analysis import patterns as patterns_stage
from shorts_analytics.analysis import ranking as ranking_stage
from shorts_analytics.analysis import stats as stats_stage
from shorts_analytics.classification.hook_classifier import classify_hook
from shorts_analytics.classification.llm_client import LLMClient
from shorts_analytics.classification.topic_classifier import classify_topic
from shorts_analytics.collectors.youtube_public import YouTubePublicCollector
from shorts_analytics.collectors.youtube_studio import NotConfiguredOwnAnalyticsCollector, OwnAnalyticsCollector
from shorts_analytics.models import (
    AnalysisResult,
    ClassificationResult,
    DataSource,
    Report,
    RunMetadata,
    ShortVideo,
    Sourced,
)
from shorts_analytics.preprocessing.cleaning import clean_videos
from shorts_analytics.reporting.markdown_renderer import render_markdown
from shorts_analytics.reporting.report_builder import build_report
from shorts_analytics.validation.validators import validate_videos


class ResearchAgent:
    """Fuehrt einen kompletten Research-Lauf ueber YouTube Shorts durch."""

    def __init__(
        self,
        youtube_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        model: str = config.DEFAULT_MODEL,
        own_analytics_collector: OwnAnalyticsCollector | None = None,
        data_dir: Path | None = None,
        public_collector: YouTubePublicCollector | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        """youtube_api_key/anthropic_api_key werden nur benoetigt, wenn kein
        public_collector bzw. llm_client injiziert wird (siehe Tests fuer
        Dependency-Injection ohne echte API-Keys/Netzwerkzugriff)."""
        self._public_collector = public_collector or YouTubePublicCollector(youtube_api_key)
        self._own_analytics_collector = own_analytics_collector or NotConfiguredOwnAnalyticsCollector()
        self._llm = llm_client or LLMClient(anthropic_api_key, model=model)
        self._data_dir = data_dir or (Path.cwd() / "data" / "runs")

    def run(
        self,
        categories: list[str] | None = None,
        max_results_per_query: int = config.DEFAULT_MAX_RESULTS_PER_QUERY,
    ) -> Report:
        categories = categories or list(config.DEFAULT_SEARCH_QUERIES.keys())
        run_id = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        metadata = RunMetadata(
            run_id=run_id,
            started_at=dt.datetime.now(dt.timezone.utc),
            categories_used=categories,
            model_used=self._llm.model,
            filters={"max_results_per_query": str(max_results_per_query)},
        )

        raw_videos = self._collect(categories, max_results_per_query, metadata)
        metadata.videos_examined = len(raw_videos)

        validated = validate_videos(raw_videos)
        metadata.videos_rejected = len(validated.rejected)
        for video_id, reason in validated.rejected:
            metadata.errors.append(f"validation[{video_id}]: {reason}")

        self._enrich_with_own_analytics(validated.valid, metadata)

        cleaning_result = clean_videos(validated.valid)
        metadata.videos_valid = len(cleaning_result.videos)
        if cleaning_result.duplicates_removed:
            metadata.limitations.append(f"{cleaning_result.duplicates_removed} Duplikate wurden entfernt.")
        if cleaning_result.outlier_video_ids:
            metadata.limitations.append(
                f"{len(cleaning_result.outlier_video_ids)} Shorts wurden als Aufrufe-Ausreisser markiert "
                "(nicht entfernt, siehe clean.csv)."
            )

        classifications = self._classify(cleaning_result.videos, metadata)

        analysis = stats_stage.analyze(cleaning_result.videos, classifications)

        top_topics = ranking_stage.rank_groups(analysis.by_topic)
        top_formats = ranking_stage.rank_groups(analysis.by_format)

        insights = self._interpret_patterns(analysis, metadata)
        limitations = self._collect_limitations(analysis)

        report = build_report(
            client=self._llm,
            run_metadata=metadata,
            analysis=analysis,
            top_topics=top_topics,
            top_formats=top_formats,
            patterns=insights,
            limitations=limitations,
        )

        metadata.finished_at = dt.datetime.now(dt.timezone.utc)
        report.run_metadata = metadata

        self._persist(run_id, raw_videos, cleaning_result.videos, classifications, metadata, report)

        return report

    def _collect(self, categories: list[str], max_results_per_query: int, metadata: RunMetadata) -> list[ShortVideo]:
        videos: list[ShortVideo] = []
        for category in categories:
            queries = config.DEFAULT_SEARCH_QUERIES.get(category, [])
            for query in queries:
                metadata.search_topics.append(f"{category}: {query}")
                try:
                    video_ids = self._public_collector.search_shorts(query, max_results=max_results_per_query)
                    videos.extend(self._public_collector.fetch_video_details(video_ids, search_topic=category))
                except RuntimeError as exc:
                    metadata.errors.append(f"collection[{category}/{query}]: {exc}")
        if videos and DataSource.PUBLIC not in metadata.data_sources:
            metadata.data_sources.append(DataSource.PUBLIC)
        return videos

    def _enrich_with_own_analytics(self, videos: list[ShortVideo], metadata: RunMetadata) -> None:
        if not videos:
            return
        try:
            retention_by_id = self._own_analytics_collector.fetch_retention_metrics([v.video_id for v in videos])
        except Exception as exc:
            metadata.errors.append(f"own_analytics: {exc}")
            retention_by_id = {}

        if retention_by_id and DataSource.OWN_ANALYTICS not in metadata.data_sources:
            metadata.data_sources.append(DataSource.OWN_ANALYTICS)
        elif not retention_by_id:
            metadata.limitations.append(
                "Keine eigenen YouTube-Analytics-Daten (Ebene 2) verfuegbar - Retention-Kennzahlen fehlen fuer "
                "alle untersuchten Shorts, da es sich um fremde Kanaele handelt bzw. keine OAuth-Anbindung "
                "konfiguriert ist. Es wurden KEINE Werte geschaetzt."
            )

        for video in videos:
            metrics = retention_by_id.get(video.video_id, {})
            if "average_view_percentage" in metrics:
                video.average_view_percentage = Sourced.own_analytics(metrics["average_view_percentage"])
            if "average_view_duration_seconds" in metrics:
                video.average_view_duration_seconds = Sourced.own_analytics(
                    metrics["average_view_duration_seconds"]
                )
            if "stayed_to_watch_ratio" in metrics:
                video.stayed_to_watch_ratio = Sourced.own_analytics(metrics["stayed_to_watch_ratio"])

            if video.views.is_available and video.views.value > 0:
                engagement = ((video.likes.value or 0) + (video.comments.value or 0)) / video.views.value
                video.engagement_rate = Sourced.derived(engagement)

    def _classify(self, videos: list[ShortVideo], metadata: RunMetadata) -> list[ClassificationResult]:
        results: list[ClassificationResult] = []
        new_topic_suggestions: set[str] = set()

        for video in videos:
            try:
                topic_raw = classify_topic(self._llm, video)
                hook_raw = classify_hook(self._llm, video)
            except ValueError as exc:
                metadata.errors.append(f"classification[{video.video_id}]: {exc}")
                continue

            if topic_raw.get("is_new_topic_suggestion"):
                new_topic_suggestions.add(str(topic_raw.get("topic")))

            try:
                results.append(
                    ClassificationResult(
                        video_id=video.video_id,
                        topic=topic_raw.get("topic", "Sonstige"),
                        subtopic=topic_raw.get("subtopic"),
                        is_new_topic_suggestion=bool(topic_raw.get("is_new_topic_suggestion", False)),
                        **hook_raw,
                    )
                )
            except Exception as exc:  # ungueltige LLM-Antwort (Schema-Verletzung) -> Video ueberspringen
                metadata.errors.append(f"classification_parse[{video.video_id}]: {exc}")

        if new_topic_suggestions:
            metadata.limitations.append(
                "Das Modell hat neue Themenvorschläge gemacht, die nicht in der Standard-Kategorienliste "
                f"enthalten sind: {', '.join(sorted(new_topic_suggestions))}. Diese wurden übernommen, sollten "
                "aber manuell geprüft und ggf. in config.DEFAULT_CATEGORIES aufgenommen werden."
            )
        return results

    def _interpret_patterns(self, analysis: AnalysisResult, metadata: RunMetadata):
        try:
            return patterns_stage.interpret_patterns(self._llm, analysis)
        except Exception as exc:
            metadata.errors.append(f"pattern_interpretation: {exc}")
            return []

    def _collect_limitations(self, analysis: AnalysisResult) -> list[str]:
        limitations = []
        unreliable_groups = [g.group for g in analysis.by_topic if not g.is_reliable]
        if unreliable_groups:
            limitations.append(
                f"Folgende Themen hatten eine Stichprobe unter {config.MIN_RELIABLE_SAMPLE_SIZE} Shorts und "
                f"gelten daher als nicht statistisch belastbar: {', '.join(unreliable_groups)}."
            )
        limitations.append(
            "Die Stichprobe wurde ueber die YouTube-Suche (order=viewCount) gebildet und ist damit tendenziell "
            "auf bereits erfolgreiche/virale Shorts verzerrt (Survivorship Bias) - kein Vergleich mit "
            "durchschnittlich erfolgreichen oder erfolglosen Shorts."
        )
        return limitations

    def _persist(
        self,
        run_id: str,
        raw_videos: list[ShortVideo],
        clean_videos_list: list[ShortVideo],
        classifications: list[ClassificationResult],
        metadata: RunMetadata,
        report: Report,
    ) -> None:
        directory = persistence.run_directory(self._data_dir, run_id)
        persistence.save_run(
            directory=directory,
            raw_videos=raw_videos,
            clean_videos=clean_videos_list,
            classifications=classifications,
            run_metadata=metadata,
            report=report,
            report_markdown=render_markdown(report),
        )
