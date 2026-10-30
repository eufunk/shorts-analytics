"""Kommandozeilen-Einstiegspunkt fuer den Research-Agenten."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv

from shorts_analytics import config
from shorts_analytics.agent import ResearchAgent
from shorts_analytics.run_status import RunCancelled, RunState, RunStatus, StatusReporter, new_run_id

app = typer.Typer(add_completion=False, help="YouTube Shorts Research-Agent")


@app.command()
def run(
    categories: list[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Zu untersuchende Kategorie(n) (mehrfach angebbar). Ohne Angabe: alle Standardkategorien.",
    ),
    max_results: int = typer.Option(
        config.DEFAULT_MAX_RESULTS_PER_QUERY,
        "--max-results",
        help="Maximale Suchergebnisse pro Suchanfrage (steuert API-Quota-Verbrauch).",
    ),
    env_file: Path = typer.Option(Path(".env"), "--env-file", help="Pfad zur .env-Datei mit API-Keys."),
    run_id: str = typer.Option(
        None,
        "--run-id",
        help="Vorgegebene Lauf-ID (setzt das Control Panel, um den Lauf-Ordner vorab zu kennen).",
    ),
) -> None:
    """Fuehrt einen vollstaendigen Research-Lauf durch und schreibt den Report nach data/runs/<run_id>/report.md.

    Fortschritt und Zustand werden laufend in data/runs/<run_id>/status.json festgehalten.
    """
    load_dotenv(env_file)
    run_id = run_id or new_run_id()
    status = StatusReporter(
        Path.cwd() / "data" / "runs" / run_id,
        RunStatus(run_id=run_id, categories=categories or [], max_results_per_query=max_results, pid=os.getpid()),
    )

    youtube_api_key = os.environ.get("YOUTUBE_API_KEY")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not youtube_api_key or not anthropic_api_key:
        typer.secho(
            "YOUTUBE_API_KEY und ANTHROPIC_API_KEY muessen gesetzt sein (siehe .env.example).",
            fg=typer.colors.RED,
        )
        status.finish(RunState.FAILED, error="YOUTUBE_API_KEY und/oder ANTHROPIC_API_KEY fehlen in der .env-Datei.")
        raise typer.Exit(code=1)

    model = os.environ.get("SHORTS_ANALYTICS_MODEL", config.DEFAULT_MODEL)
    agent = ResearchAgent(youtube_api_key=youtube_api_key, anthropic_api_key=anthropic_api_key, model=model)

    typer.echo(f"Starte Research-Lauf ueber Kategorien: {categories or 'alle Standardkategorien'}")
    try:
        report = agent.run(
            categories=categories or None,
            max_results_per_query=max_results,
            run_id=run_id,
            progress=status.progress,
            should_stop=status.should_stop,
        )
    except RunCancelled:
        status.finish(RunState.CANCELLED)
        typer.echo("Lauf wurde auf Wunsch angehalten. Es wurde kein Report gespeichert.")
        raise typer.Exit(code=2)
    except Exception as exc:
        status.finish(RunState.FAILED, error=f"{type(exc).__name__}: {exc}")
        raise
    status.finish(RunState.FINISHED)

    typer.echo(f"\nLauf abgeschlossen: {report.run_metadata.run_id}")
    typer.echo(
        f"Untersuchte Shorts: {report.run_metadata.videos_valid} "
        f"(davon geprueft: {report.run_metadata.videos_examined})"
    )
    typer.echo(f"Report gespeichert unter: data/runs/{report.run_metadata.run_id}/report.md")


if __name__ == "__main__":
    app()
