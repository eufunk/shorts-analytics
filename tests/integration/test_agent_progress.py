"""Integrationstest: Fortschrittsmeldungen und Anhalten eines Laufs (Control Panel)."""

from __future__ import annotations

from pathlib import Path

import pytest

from shorts_analytics.agent import ResearchAgent
from shorts_analytics.run_status import (
    PIPELINE_STAGES,
    RunCancelled,
    RunState,
    RunStatus,
    StatusReporter,
    read_status,
    request_stop,
)
from tests.fakes import FakeLLMClient, FakePublicCollector


def make_agent(tmp_path: Path) -> ResearchAgent:
    return ResearchAgent(
        public_collector=FakePublicCollector(videos_per_query=3),
        llm_client=FakeLLMClient(),
        data_dir=tmp_path,
    )


def test_run_reports_every_stage_in_order(tmp_path: Path):
    events: list[tuple[int, str, int | None, int | None]] = []

    report = make_agent(tmp_path).run(
        categories=["Wissen / Bildung"],
        max_results_per_query=3,
        run_id="fixed-id",
        progress=lambda *event: events.append(event),
    )

    stages = [stage for stage, *_ in events]
    assert stages == sorted(stages), "Stages muessen in Pipeline-Reihenfolge gemeldet werden"
    assert set(stages) == set(range(len(PIPELINE_STAGES)))
    assert report.run_metadata.run_id == "fixed-id"
    assert (tmp_path / "fixed-id" / "report.json").exists()

    # Klassifizierung meldet jedes Video einzeln (2 Suchbegriffe x 3 Videos).
    classification = [(current, total) for stage, _, current, total in events if stage == 4]
    assert classification == [(i, 6) for i in range(6)]


def test_stop_request_cancels_run_without_report(tmp_path: Path):
    calls = {"n": 0}

    def stop_during_classification() -> bool:
        calls["n"] += 1
        return calls["n"] > 6  # Research, 2 Suchanfragen, Pruefen, Bereinigen und das erste Video laufen lassen

    with pytest.raises(RunCancelled):
        make_agent(tmp_path).run(
            categories=["Wissen / Bildung"],
            max_results_per_query=3,
            run_id="stopped",
            should_stop=stop_during_classification,
        )

    assert not (tmp_path / "stopped" / "report.json").exists()


def test_status_reporter_writes_progress_and_honours_stop_file(tmp_path: Path):
    run_dir = tmp_path / "run"
    reporter = StatusReporter(run_dir, RunStatus(run_id="run", categories=["Finanzen"]))

    make_agent(tmp_path).run(
        categories=["Finanzen"], max_results_per_query=1, run_id="run",
        progress=reporter.progress, should_stop=reporter.should_stop,
    )
    reporter.finish(RunState.FINISHED)

    status = read_status(run_dir)
    assert status.state == RunState.FINISHED
    assert status.stage_index == len(PIPELINE_STAGES) - 1
    assert status.fraction_done == 1.0

    stopped_dir = tmp_path / "stopped"
    stopped = StatusReporter(stopped_dir, RunStatus(run_id="stopped"))
    request_stop(stopped_dir)
    with pytest.raises(RunCancelled):
        make_agent(tmp_path).run(
            categories=["Finanzen"], max_results_per_query=1, run_id="stopped",
            progress=stopped.progress, should_stop=stopped.should_stop,
        )
