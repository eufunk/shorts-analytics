"""Starten, Anhalten und Auflisten von Agenten-Laeufen (fuer das Control Panel).

Ein Lauf wird als eigener Prozess ueber die CLI gestartet
(`python -m shorts_analytics.cli --run-id ...`). Dadurch bleibt die
Oberflaeche bedienbar und der Lauf geht nicht verloren, wenn der Browser-Tab
geschlossen wird. Kommuniziert wird ausschliesslich ueber die Dateien im
Lauf-Ordner (siehe run_status.py).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from shorts_analytics import config
from shorts_analytics.run_status import (
    LOG_FILE,
    RunState,
    RunStatus,
    new_run_id,
    read_status,
    write_status,
)

REQUIRED_API_KEYS = ("YOUTUBE_API_KEY", "ANTHROPIC_API_KEY")

# Kosten der YouTube Data API v3 in Quota-Einheiten (Tageskontingent: 10.000).
YOUTUBE_DAILY_QUOTA = 10_000
QUOTA_SEARCH_LIST = 100
QUOTA_VIDEOS_LIST = 1

# Ein Prozess, der nach dieser Zeit noch keine eigene Statusmeldung geschrieben hat, gilt als nicht gestartet.
STARTUP_TIMEOUT = dt.timedelta(minutes=2)

# Gestartete Prozesse, damit sie nach Ende sauber eingesammelt werden (kein Zombie unter Linux/macOS).
_children: list[subprocess.Popen] = []


@dataclass
class UsageEstimate:
    search_queries: int
    max_videos: int
    youtube_quota_units: int
    max_llm_calls: int


@dataclass
class RunInfo:
    run_id: str
    run_dir: Path
    state: RunState
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    categories: list[str] = field(default_factory=list)
    videos_valid: int | None = None
    has_report: bool = False
    error: str | None = None
    status: RunStatus | None = None


def runs_dir(project_root: Path) -> Path:
    return project_root / "data" / "runs"


def missing_api_keys(project_root: Path) -> list[str]:
    values = {**dotenv_values(project_root / ".env"), **os.environ}
    return [key for key in REQUIRED_API_KEYS if not values.get(key)]


def estimate_usage(categories: list[str], max_results_per_query: int) -> UsageEstimate:
    """Obergrenze fuer den API-Verbrauch eines Laufs (Duplikate und Nicht-Shorts senken die echten Werte)."""
    queries = sum(len(config.DEFAULT_SEARCH_QUERIES.get(c, [])) for c in categories)
    max_videos = queries * min(max_results_per_query, 50)
    return UsageEstimate(
        search_queries=queries,
        max_videos=max_videos,
        youtube_quota_units=queries * (QUOTA_SEARCH_LIST + QUOTA_VIDEOS_LIST),
        # je Video Themen- und Hook-Klassifizierung, dazu Muster, Empfehlungen und Zusammenfassung
        max_llm_calls=max_videos * 2 + 3,
    )


def start_run(project_root: Path, categories: list[str], max_results_per_query: int) -> str:
    """Startet einen Lauf im Hintergrund und gibt die Lauf-ID zurueck.

    Leere `categories` bedeuten: alle Standardkategorien.
    """
    run_id = new_run_id()
    run_dir = runs_dir(project_root) / run_id
    write_status(run_dir, RunStatus(run_id=run_id, categories=categories, max_results_per_query=max_results_per_query))

    command = [sys.executable, "-m", "shorts_analytics.cli", "--run-id", run_id, "--max-results", str(max_results_per_query)]
    for category in categories:
        command += ["--category", category]

    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    with open(run_dir / LOG_FILE, "w", encoding="utf-8") as log:
        if os.name == "nt":
            process = subprocess.Popen(
                command, cwd=project_root, stdout=log, stderr=subprocess.STDOUT, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            process = subprocess.Popen(
                command, cwd=project_root, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True,
            )
    _children.append(process)
    return run_id


def kill_run(run_dir: Path) -> None:
    """Notfall: beendet den Prozess sofort und markiert den Lauf als abgebrochen."""
    status = read_status(run_dir)
    if status is None:
        return
    if status.pid:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(status.pid), "/T", "/F"], capture_output=True)
        else:
            try:
                os.kill(status.pid, 15)
            except ProcessLookupError:
                pass
    status.state = RunState.CANCELLED
    status.detail = "Lauf wurde sofort beendet"
    status.finished_at = dt.datetime.now(dt.timezone.utc)
    write_status(run_dir, status)


def delete_run(project_root: Path, run_id: str) -> None:
    """Loescht einen Lauf mit allen Dateien. Laufende Laeufe werden nicht geloescht."""
    base = runs_dir(project_root).resolve()
    run_dir = (base / run_id).resolve()
    if run_dir.parent != base or not run_dir.is_dir():
        raise ValueError(f"Kein Lauf-Ordner unter data/runs/: {run_id!r}")
    if load_run(run_dir).state == RunState.RUNNING:
        raise ValueError(f"Lauf {run_id} läuft noch und kann nicht gelöscht werden. Bitte zuerst anhalten.")
    if sys.version_info >= (3, 12):
        shutil.rmtree(run_dir, onexc=_clear_readonly_and_retry)
    else:
        shutil.rmtree(run_dir, onerror=_clear_readonly_and_retry)


def _clear_readonly_and_retry(func, path, _exc) -> None:
    """OneDrive setzt synchronisierte Ordner/Dateien schreibgeschuetzt - Schutz aufheben und erneut loeschen."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def is_process_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def effective_state(status: RunStatus, now: dt.datetime | None = None) -> tuple[RunState, str | None]:
    """Zustand laut status.json, korrigiert um Prozesse, die unbemerkt beendet wurden."""
    if status.state != RunState.RUNNING:
        return status.state, status.error
    now = now or dt.datetime.now(dt.timezone.utc)
    if status.pid is None:
        if now - status.started_at > STARTUP_TIMEOUT:
            return RunState.FAILED, "Der Agent-Prozess ist nicht gestartet (Details in log.txt)."
        return RunState.RUNNING, None
    if not is_process_alive(status.pid):
        return RunState.FAILED, "Der Agent-Prozess wurde unerwartet beendet (Details in log.txt)."
    return RunState.RUNNING, None


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_time(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


def load_run(run_dir: Path) -> RunInfo:
    status = read_status(run_dir)
    metadata = _load_json(run_dir / "run_metadata.json") or {}
    has_report = (run_dir / "report.json").exists()

    if status is not None:
        state, error = effective_state(status)
        return RunInfo(
            run_id=run_dir.name,
            run_dir=run_dir,
            state=state,
            started_at=status.started_at,
            # abgestuerzte Prozesse haben kein finished_at: letzte Meldung als Ende verwenden
            finished_at=status.finished_at or (status.updated_at if state != RunState.RUNNING else None),
            categories=status.categories or metadata.get("categories_used", []),
            videos_valid=metadata.get("videos_valid"),
            has_report=has_report,
            error=error,
            status=status,
        )

    # Aeltere Laeufe (vor dem Control Panel) haben keine status.json.
    return RunInfo(
        run_id=run_dir.name,
        run_dir=run_dir,
        state=RunState.FINISHED if has_report else RunState.FAILED,
        started_at=_parse_time(metadata.get("started_at")),
        finished_at=_parse_time(metadata.get("finished_at")),
        categories=metadata.get("categories_used", []),
        videos_valid=metadata.get("videos_valid"),
        has_report=has_report,
        error=None if has_report else "Kein Report und keine Statusdatei vorhanden.",
    )


def list_runs(project_root: Path) -> list[RunInfo]:
    """Alle Laeufe, neueste zuerst."""
    for process in list(_children):
        if process.poll() is not None:
            _children.remove(process)
    base = runs_dir(project_root)
    if not base.exists():
        return []
    return [load_run(p) for p in sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)]


def active_run(project_root: Path) -> RunInfo | None:
    return next((run for run in list_runs(project_root) if run.state == RunState.RUNNING), None)
