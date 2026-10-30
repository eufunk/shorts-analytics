from __future__ import annotations

import datetime as dt
import json
import os
import stat
from pathlib import Path

import pytest

from shorts_analytics import run_control
from shorts_analytics.run_status import RunState, RunStatus, read_status, write_status


def test_status_roundtrip_and_fraction(tmp_path: Path):
    status = RunStatus(run_id="r1", stage_index=4, current=5, total=10, categories=["Sport"])
    write_status(tmp_path, status)

    loaded = read_status(tmp_path)
    assert loaded.run_id == "r1"
    assert loaded.stage_name == "Klassifizierung"
    assert abs(loaded.fraction_done - 4.5 / 9) < 1e-9
    assert read_status(tmp_path / "missing") is None


def test_estimate_usage_counts_queries_per_category():
    # "Wissen / Bildung" hat 2 Suchbegriffe, "Sport" 1
    usage = run_control.estimate_usage(["Wissen / Bildung", "Sport"], max_results_per_query=5)

    assert usage.search_queries == 3
    assert usage.max_videos == 15
    assert usage.youtube_quota_units == 3 * 101
    assert usage.max_llm_calls == 15 * 2 + 3


def test_list_runs_handles_new_legacy_and_dead_runs(tmp_path: Path):
    base = tmp_path / "data" / "runs"

    # fertiger Lauf mit Statusdatei
    write_status(base / "20261030T100000Z_a", RunStatus(run_id="a", state=RunState.FINISHED))

    # aelterer Lauf ohne status.json, aber mit Report
    legacy = base / "20260905T105718Z_b"
    legacy.mkdir(parents=True)
    (legacy / "report.json").write_text("{}", encoding="utf-8")
    (legacy / "run_metadata.json").write_text(
        json.dumps({"started_at": "2026-09-05T10:57:18+00:00", "categories_used": ["Finanzen"], "videos_valid": 12}),
        encoding="utf-8",
    )

    # "laeuft" laut Datei, Prozess existiert aber nicht mehr
    write_status(base / "20261030T110000Z_c", RunStatus(run_id="c", pid=2**22 + 12345))

    runs = {run.run_id: run for run in run_control.list_runs(tmp_path)}

    assert runs["20261030T100000Z_a"].state == RunState.FINISHED
    assert runs["20260905T105718Z_b"].state == RunState.FINISHED
    assert runs["20260905T105718Z_b"].videos_valid == 12
    assert runs["20260905T105718Z_b"].categories == ["Finanzen"]
    assert runs["20261030T110000Z_c"].state == RunState.FAILED
    assert [r.run_id for r in run_control.list_runs(tmp_path)][0] == "20261030T110000Z_c"  # neueste zuerst
    assert run_control.active_run(tmp_path) is None


def test_run_without_process_counts_as_running_only_during_startup():
    started = dt.datetime(2026, 10, 30, 10, 0, tzinfo=dt.timezone.utc)
    status = RunStatus(run_id="x", started_at=started)

    assert run_control.effective_state(status, now=started + dt.timedelta(seconds=10))[0] == RunState.RUNNING
    assert run_control.effective_state(status, now=started + dt.timedelta(minutes=5))[0] == RunState.FAILED


def test_missing_api_keys(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert run_control.missing_api_keys(tmp_path) == ["YOUTUBE_API_KEY", "ANTHROPIC_API_KEY"]

    (tmp_path / ".env").write_text("YOUTUBE_API_KEY=abc\n", encoding="utf-8")
    assert run_control.missing_api_keys(tmp_path) == ["ANTHROPIC_API_KEY"]


def test_delete_run_removes_finished_run(tmp_path: Path):
    run_dir = tmp_path / "data" / "runs" / "20261030T100000Z_a"
    write_status(run_dir, RunStatus(run_id="a", state=RunState.FINISHED))
    (run_dir / "report.json").write_text("{}", encoding="utf-8")

    run_control.delete_run(tmp_path, "20261030T100000Z_a")

    assert not run_dir.exists()


def test_delete_run_refuses_running_run(tmp_path: Path):
    run_dir = tmp_path / "data" / "runs" / "20261030T100000Z_b"
    write_status(run_dir, RunStatus(run_id="b"))  # laeuft, Prozess startet gerade

    with pytest.raises(ValueError, match="läuft noch"):
        run_control.delete_run(tmp_path, "20261030T100000Z_b")
    assert run_dir.exists()


def test_delete_run_refuses_paths_outside_runs_dir(tmp_path: Path):
    (tmp_path / "data" / "runs").mkdir(parents=True)
    outside = tmp_path / "data" / "wichtig"
    outside.mkdir()

    for bad_id in ["../wichtig", "..", "", "gibt-es-nicht"]:
        with pytest.raises(ValueError):
            run_control.delete_run(tmp_path, bad_id)
    assert outside.exists()


def test_delete_run_removes_read_only_folders(tmp_path: Path):
    # OneDrive markiert synchronisierte Ordner als schreibgeschuetzt
    run_dir = tmp_path / "data" / "runs" / "20261030T100000Z_c"
    write_status(run_dir, RunStatus(run_id="c", state=RunState.FAILED))
    (run_dir / "log.txt").write_text("x", encoding="utf-8")
    os.chmod(run_dir / "log.txt", stat.S_IREAD)
    os.chmod(run_dir, stat.S_IREAD)

    run_control.delete_run(tmp_path, "20261030T100000Z_c")

    assert not run_dir.exists()
