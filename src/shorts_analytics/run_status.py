"""Fortschritt und Steuerung eines laufenden Agenten-Laufs ueber Dateien.

Der Agent laeuft (z.B. vom Control Panel aus gestartet) als eigener Prozess.
Damit Oberflaeche und Agent ohne Server/Datenbank miteinander reden koennen,
liegen im Lauf-Ordner data/runs/<run_id>/ zwei kleine Dateien:

- status.json     - schreibt der Agent: aktueller Schritt, Zaehler, Zustand
- stop.requested  - legt die Oberflaeche an, wenn der Lauf anhalten soll

Der Agent prueft den Stopp-Wunsch zwischen zwei Arbeitsschritten (z.B. nach
jedem klassifizierten Video) und bricht dann sauber mit RunCancelled ab.
"""

from __future__ import annotations

import datetime as dt
import os
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field

# Die 9 Stages der Pipeline in fester Reihenfolge (siehe agent.py).
PIPELINE_STAGES: list[str] = [
    "Research",
    "Datensammlung",
    "Validierung",
    "Bereinigung",
    "Klassifizierung",
    "Quantitative Analyse",
    "Mustererkennung",
    "Ranking",
    "Report",
]

STATUS_FILE = "status.json"
STOP_FILE = "stop.requested"
LOG_FILE = "log.txt"

# (stage_index, detail, current, total) -> None
ProgressCallback = Callable[[int, str, Optional[int], Optional[int]], None]


class RunCancelled(Exception):
    """Wird geworfen, wenn ein Lauf auf Wunsch des Anwenders angehalten wurde."""


class RunState(str, Enum):
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    FAILED = "failed"


STATE_LABELS: dict[RunState, str] = {
    RunState.RUNNING: "läuft",
    RunState.FINISHED: "fertig",
    RunState.CANCELLED: "abgebrochen",
    RunState.FAILED: "fehlgeschlagen",
}


class RunStatus(BaseModel):
    """Inhalt von status.json."""

    run_id: str
    state: RunState = RunState.RUNNING
    stage_index: int = -1  # -1 = Prozess startet noch
    detail: str = ""
    current: Optional[int] = None
    total: Optional[int] = None
    categories: list[str] = Field(default_factory=list)
    max_results_per_query: Optional[int] = None
    pid: Optional[int] = None  # Prozess-ID des Agenten (fuer "Sofort beenden")
    started_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    finished_at: Optional[dt.datetime] = None
    error: Optional[str] = None

    @property
    def stage_name(self) -> str:
        if 0 <= self.stage_index < len(PIPELINE_STAGES):
            return PIPELINE_STAGES[self.stage_index]
        return "Wird gestartet"

    @property
    def fraction_done(self) -> float:
        """Gesamtfortschritt 0..1: abgeschlossene Stages plus Anteil der aktuellen Stage."""
        if self.state == RunState.FINISHED:
            return 1.0
        if self.stage_index < 0:
            return 0.0
        within = (self.current / self.total) if self.current is not None and self.total else 0.0
        return min(1.0, (self.stage_index + within) / len(PIPELINE_STAGES))


def new_run_id() -> str:
    return f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"


def read_status(run_dir: Path) -> RunStatus | None:
    path = run_dir / STATUS_FILE
    if not path.exists():
        return None
    # Der Agent ersetzt die Datei laufend; ein Lesezugriff genau im falschen
    # Moment wird einfach kurz wiederholt.
    for _ in range(5):
        try:
            return RunStatus.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.05)
    return None


def write_status(run_dir: Path, status: RunStatus) -> None:
    """Schreibt status.json atomar (temporaere Datei + Umbenennen)."""
    status.updated_at = dt.datetime.now(dt.timezone.utc)
    run_dir.mkdir(parents=True, exist_ok=True)
    tmp = run_dir / f"{STATUS_FILE}.{os.getpid()}.tmp"
    tmp.write_text(status.model_dump_json(indent=2), encoding="utf-8")
    # Unter Windows schlaegt os.replace fehl, solange ein Leser die Datei offen hat.
    for attempt in range(20):
        try:
            os.replace(tmp, run_dir / STATUS_FILE)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def request_stop(run_dir: Path) -> None:
    (run_dir / STOP_FILE).write_text(dt.datetime.now(dt.timezone.utc).isoformat(), encoding="utf-8")


def stop_requested(run_dir: Path) -> bool:
    return (run_dir / STOP_FILE).exists()


class StatusReporter:
    """Verbindet ResearchAgent.run() mit status.json und dem Stopp-Wunsch."""

    def __init__(self, run_dir: Path, status: RunStatus) -> None:
        self.run_dir = run_dir
        self.status = status
        write_status(run_dir, status)

    def progress(self, stage_index: int, detail: str, current: int | None, total: int | None) -> None:
        self.status.stage_index = stage_index
        self.status.detail = detail
        self.status.current = current
        self.status.total = total
        write_status(self.run_dir, self.status)

    def should_stop(self) -> bool:
        return stop_requested(self.run_dir)

    def finish(self, state: RunState, error: str | None = None) -> None:
        self.status.state = state
        self.status.error = error
        self.status.finished_at = dt.datetime.now(dt.timezone.utc)
        if state == RunState.FINISHED:
            self.status.detail = "Lauf abgeschlossen"
            self.status.current = self.status.total = None
        elif state == RunState.CANCELLED:
            self.status.detail = "Lauf auf Wunsch angehalten"
        write_status(self.run_dir, self.status)
