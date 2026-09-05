"""Integrationstest: kompletter Pipeline-Lauf ohne echte API-Calls.

Prueft die Verdrahtung aller Stages (Research -> ... -> Report) sowie die
Kernregel, dass fehlende Retention-Daten als 'nicht verfuegbar' im Report
landen statt geschaetzt zu werden.
"""

from __future__ import annotations

from pathlib import Path

from shorts_analytics.agent import ResearchAgent
from shorts_analytics.config import MIN_RELIABLE_SAMPLE_SIZE
from tests.fakes import FakeLLMClient, FakePublicCollector


def test_full_pipeline_runs_and_persists_report(tmp_path: Path):
    queries_per_category = 2  # "Wissen / Bildung" hat 2 Suchbegriffe in config.DEFAULT_SEARCH_QUERIES
    videos_per_query = MIN_RELIABLE_SAMPLE_SIZE // queries_per_category + 1  # reliable sample size erreichen

    agent = ResearchAgent(
        public_collector=FakePublicCollector(videos_per_query=videos_per_query),
        llm_client=FakeLLMClient(),
        data_dir=tmp_path,
    )

    report = agent.run(categories=["Wissen / Bildung"], max_results_per_query=videos_per_query)

    expected_video_count = queries_per_category * videos_per_query
    assert report.run_metadata.videos_examined == expected_video_count
    assert report.run_metadata.videos_valid == expected_video_count
    assert report.run_metadata.errors == []

    # Kernregel: keine eigenen Analytics-Daten konfiguriert -> Retention MUSS als
    # nicht verfuegbar erscheinen, nicht geschaetzt werden.
    assert report.analysis.data_completeness.get("retention") == 0.0
    assert any("Ebene 2" in limitation for limitation in report.run_metadata.limitations)

    assert len(report.analysis.by_topic) == 1
    assert report.analysis.by_topic[0].is_reliable is True
    assert report.analysis.by_topic[0].sample_size == expected_video_count

    assert report.executive_summary
    assert report.recommendations

    # Persistenz: alle Lauf-Artefakte muessen unter data_dir/<run_id>/ liegen.
    run_dir = tmp_path / report.run_metadata.run_id
    assert (run_dir / "raw.json").exists()
    assert (run_dir / "clean.csv").exists()
    assert (run_dir / "classifications.json").exists()
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "report.json").exists()

    report_markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "Executive Summary" in report_markdown
    assert "Einschränkungen der Daten" in report_markdown
    assert "Konkrete Handlungsempfehlungen" in report_markdown


def test_pipeline_handles_small_sample_as_unreliable(tmp_path: Path):
    agent = ResearchAgent(
        public_collector=FakePublicCollector(videos_per_query=1),
        llm_client=FakeLLMClient(),
        data_dir=tmp_path,
    )

    report = agent.run(categories=["Finanzen"], max_results_per_query=1)

    assert report.analysis.by_topic[0].is_reliable is False
    assert any("nicht statistisch belastbar" in limitation for limitation in report.limitations)
