"""Persistiert die Artefakte eines einzelnen Agenten-Laufs.

Jeder Lauf schreibt in einen eigenen Ordner unter data/runs/, damit jeder
vergangene Lauf spaeter vollstaendig nachvollzogen werden kann, ohne die
APIs erneut aufzurufen (Reproduzierbarkeit).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from shorts_analytics.models import ClassificationResult, Report, RunMetadata, ShortVideo


def run_directory(base_dir: Path, run_id: str) -> Path:
    directory = base_dir / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_run(
    directory: Path,
    raw_videos: list[ShortVideo],
    clean_videos: list[ShortVideo],
    classifications: list[ClassificationResult],
    run_metadata: RunMetadata,
    report: Report,
    report_markdown: str,
) -> None:
    (directory / "raw.json").write_text(
        json.dumps([v.model_dump(mode="json") for v in raw_videos], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pd.DataFrame([v.model_dump(mode="json") for v in clean_videos]).to_csv(
        directory / "clean.csv", index=False, encoding="utf-8"
    )

    (directory / "classifications.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in classifications], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (directory / "run_metadata.json").write_text(run_metadata.model_dump_json(indent=2), encoding="utf-8")
    (directory / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (directory / "report.md").write_text(report_markdown, encoding="utf-8")
