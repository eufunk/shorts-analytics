"""Streamlit-Control-Panel: Agenten-Laeufe starten, beobachten und auswerten.

Seiten:
- Neuer Lauf   - Themen und Stichprobengroesse waehlen, Lauf starten
- Fortschritt  - Live-Anzeige der 9 Pipeline-Schritte, Lauf anhalten
- Ergebnisse   - Visualisierung eines fertigen Reports
- Alle Laeufe  - Uebersicht aller Laeufe mit Status

Ein Lauf wird als eigener Hintergrundprozess ueber die CLI gestartet
(siehe shorts_analytics/run_control.py). Das Panel liest den Fortschritt aus
data/runs/<run_id>/status.json und die Ergebnisse aus den dort abgelegten
Artefakten; es ruft selbst keine YouTube- oder KI-Schnittstelle auf.

Start: streamlit run dashboard/app.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shorts_analytics import config, run_control
from shorts_analytics.models import GroupStats, PatternInsight, RankingEntry, Report
from shorts_analytics.run_status import (
    LOG_FILE,
    PIPELINE_STAGES,
    STATE_LABELS,
    RunState,
    request_stop,
    stop_requested,
)

# ---------------------------------------------------------------------------
# Farbpalette (Referenzpalette der dataviz-Skill, Light-Mode-Werte)
# ---------------------------------------------------------------------------
BLUE = "#2a78d6"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"

MIN_RELIABLE_SAMPLE_SIZE = 8  # nur fuer die Legenden-Beschriftung, siehe config.py

CONFIDENCE_ICON = {"hoch": "🟢", "mittel": "🟡", "niedrig": "⚪"}


# ---------------------------------------------------------------------------
# Daten laden - keine Netzwerkzugriffe, nur lokale Dateien unter data/runs/
# ---------------------------------------------------------------------------
def find_runs(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    return sorted(
        (p for p in data_dir.iterdir() if p.is_dir() and (p / "report.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    )


def load_report(run_dir: Path) -> Report:
    return Report.model_validate_json((run_dir / "report.json").read_text(encoding="utf-8"))


def load_clean_data(run_dir: Path) -> pd.DataFrame | None:
    path = run_dir / "clean.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Chart-Bausteine
# ---------------------------------------------------------------------------
def group_stats_dataframe(groups: list[GroupStats]) -> pd.DataFrame:
    return pd.DataFrame([g.model_dump() for g in groups])


def pick_metric(df: pd.DataFrame) -> tuple[str, str]:
    """Bevorzugt Zuschauerbindung, faellt sonst auf Aufrufe zurueck - wie in ranking.py."""
    if df["mean_retention"].notna().any():
        return "mean_retention", "Ø Zuschauerbindung"
    return "mean_views", "Ø Aufrufe"


def make_group_bar_chart(df: pd.DataFrame, metric_col: str, metric_label: str) -> go.Figure:
    plot_df = df.dropna(subset=[metric_col]).sort_values(metric_col, ascending=True)

    opacities = [1.0 if reliable else 0.35 for reliable in plot_df["is_reliable"]]
    tip_labels = [
        "" if reliable else f"n={n} · zu klein"
        for n, reliable in zip(plot_df["sample_size"], plot_df["is_reliable"])
    ]

    fig = go.Figure(
        go.Bar(
            x=plot_df[metric_col],
            y=plot_df["group"],
            orientation="h",
            marker=dict(color=BLUE, opacity=opacities, cornerradius=4),
            text=tip_labels,
            textposition="outside",
            textfont=dict(color=MUTED, size=11),
            customdata=plot_df["sample_size"],
            hovertemplate="<b>%{y}</b><br>" + metric_label + ": %{x:,.0f}<br>Stichprobe: n=%{customdata}<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK, family=FONT_FAMILY),
        xaxis=dict(title=metric_label, gridcolor=GRIDLINE, zeroline=False, showline=True, linecolor=BASELINE),
        yaxis=dict(title=None, showline=False),
        margin=dict(l=10, r=10, t=10, b=10),
        bargap=0.35,
        height=max(220, 52 * len(plot_df)),
        showlegend=False,
    )
    return fig


def make_completeness_chart(completeness: dict[str, float]) -> go.Figure:
    labels = {
        "views": "Aufrufe",
        "likes": "Likes",
        "comments": "Kommentare",
        "retention": "Zuschauerbindung",
        "topic": "Thema",
        "hook_type": "Hook-Typ",
    }
    df = pd.DataFrame(
        {"feld": [labels.get(k, k) for k in completeness], "anteil": list(completeness.values())}
    ).sort_values("anteil", ascending=True)

    fig = go.Figure(
        go.Bar(
            x=df["anteil"] * 100,
            y=df["feld"],
            orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            text=[f"{v:.0%}" for v in df["anteil"]],
            textposition="outside",
            textfont=dict(color=SECONDARY_INK, size=11),
            hovertemplate="<b>%{y}</b>: %{x:.0f}%<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK, family=FONT_FAMILY),
        xaxis=dict(title="Anteil verfügbarer Werte (%)", range=[0, 105], gridcolor=GRIDLINE, showline=True, linecolor=BASELINE),
        yaxis=dict(title=None, showline=False),
        margin=dict(l=10, r=10, t=10, b=10),
        bargap=0.4,
        height=max(200, 44 * len(df)),
        showlegend=False,
    )
    return fig


def reliability_column(groups: list[GroupStats]) -> pd.DataFrame:
    df = group_stats_dataframe(groups)
    df["Stichprobe"] = df["is_reliable"].map(
        lambda r: f"✓ ausreichend (n≥{MIN_RELIABLE_SAMPLE_SIZE})" if r else "○ zu klein, nicht belastbar"
    )
    return df


def render_group_section(title: str, groups: list[GroupStats]) -> None:
    if not groups:
        st.info(f"Keine Daten für „{title}“.")
        return

    df = group_stats_dataframe(groups)
    metric_col, metric_label = pick_metric(df)

    fig = make_group_bar_chart(df, metric_col, metric_label)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Kräftige Balken = ausreichende Stichprobe · blasse Balken mit „n=… · zu klein“ = "
        "nicht statistisch belastbar (siehe Kapitel 7 der Projektdokumentation)."
    )

    table = reliability_column(groups)
    display_cols = {
        "group": "Gruppe",
        "sample_size": "n",
        "Stichprobe": "Stichprobe",
        "mean_views": "Ø Aufrufe",
        "median_views": "Median Aufrufe",
        "mean_retention": "Ø Retention",
        "median_retention": "Median Retention",
    }
    table = table[[c for c in display_cols if c in table.columns]].rename(columns=display_cols)
    st.dataframe(table, use_container_width=True, hide_index=True)


def render_ranking_table(title: str, entries: list[RankingEntry]) -> None:
    st.markdown(f"**{title}**")
    if not entries:
        st.info("Keine belastbaren Daten für ein Ranking.")
        return
    df = pd.DataFrame([e.model_dump() for e in entries])
    df["Stichprobe"] = df["is_reliable"].map(lambda r: "✓" if r else "○")
    df = df.rename(
        columns={
            "rank": "Rang",
            "group": "Gruppe",
            "metric_name": "Kennzahl",
            "metric_value": "Wert",
            "sample_size": "n",
        }
    )[["Rang", "Gruppe", "Kennzahl", "Wert", "n", "Stichprobe"]]
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_patterns(patterns: list[PatternInsight]) -> None:
    if not patterns:
        st.info("Keine Muster identifiziert (zu wenig Daten oder LLM-Analyse fehlgeschlagen).")
        return
    for pattern in patterns:
        icon = CONFIDENCE_ICON.get(pattern.confidence, "⚪")
        with st.container(border=True):
            st.markdown(f"**{icon} {pattern.title}** — Konfidenz: {pattern.confidence}")
            st.write(pattern.description)
            st.caption(f"Beleg: {pattern.supporting_evidence}")


# ---------------------------------------------------------------------------
# Seiten des Control Panels
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "runs"
CATEGORIES = list(config.DEFAULT_SEARCH_QUERIES.keys())

STATE_ICON = {
    RunState.RUNNING: "⏳",
    RunState.FINISHED: "✅",
    RunState.CANCELLED: "⏹️",
    RunState.FAILED: "❌",
}

PAGES: dict[str, st.Page] = {}


def state_label(state: RunState) -> str:
    return f"{STATE_ICON[state]} {STATE_LABELS[state]}"


def format_duration(start: dt.datetime | None, end: dt.datetime | None) -> str:
    if start is None:
        return "–"
    seconds = int(((end or dt.datetime.now(dt.timezone.utc)) - start).total_seconds())
    minutes, seconds = divmod(max(seconds, 0), 60)
    return f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"


def format_local(timestamp: dt.datetime | None) -> str:
    return timestamp.astimezone().strftime("%d.%m.%Y %H:%M") if timestamp else "–"


def open_results(run_id: str) -> None:
    st.session_state["selected_run"] = run_id
    st.switch_page(PAGES["results"])


def open_progress(run_id: str) -> None:
    st.session_state["selected_run"] = run_id
    st.switch_page(PAGES["progress"])


def page_new_run() -> None:
    st.title("🚀 Neuer Analyse-Lauf")
    st.caption(
        "Der Agent sucht passende Shorts über die YouTube-Schnittstelle, lässt sie von der KI einordnen, "
        "wertet sie statistisch aus und schreibt einen Report. Der Lauf arbeitet im Hintergrund weiter, "
        "auch wenn du diese Seite verlässt."
    )

    missing = run_control.missing_api_keys(PROJECT_ROOT)
    if missing:
        st.error(
            f"Es fehlen API-Keys in der Datei `.env`: **{', '.join(missing)}**. "
            "Vorlage: `.env.example`. Ohne diese Keys kann kein Lauf gestartet werden."
        )

    running = run_control.active_run(PROJECT_ROOT)
    if running:
        st.warning(f"Es läuft bereits ein Lauf ({running.run_id}). Es kann immer nur ein Lauf gleichzeitig laufen.")
        if st.button("Zum laufenden Lauf"):
            open_progress(running.run_id)

    all_categories = st.toggle("Alle Themen untersuchen", value=False)
    if all_categories:
        categories = CATEGORIES
        st.caption(f"Alle {len(CATEGORIES)} Themen werden untersucht.")
    else:
        categories = st.multiselect(
            "Themen",
            options=CATEGORIES,
            default=["Wissen / Bildung"],
            placeholder="Mindestens ein Thema auswählen",
        )
    max_results = st.slider(
        "Videos pro Suchbegriff",
        min_value=1,
        max_value=50,
        value=5,
        help="Jedes Thema hat 1–2 Suchbegriffe. Für einen ersten Testlauf reichen 5.",
    )

    if categories:
        usage = run_control.estimate_usage(categories, max_results)
        col1, col2, col3 = st.columns(3)
        col1.metric("Suchanfragen", usage.search_queries)
        col2.metric("Videos (höchstens)", usage.max_videos)
        col3.metric("KI-Aufrufe (höchstens)", usage.max_llm_calls)
        share = usage.youtube_quota_units / run_control.YOUTUBE_DAILY_QUOTA
        st.caption(
            f"YouTube-Kontingent: ca. {usage.youtube_quota_units:,} von {run_control.YOUTUBE_DAILY_QUOTA:,} "
            f"Einheiten pro Tag ({share:.0%}). KI-Aufrufe werden über deinen Anthropic-Account abgerechnet."
            .replace(",", ".")
        )
        if share > 1:
            st.warning("Diese Auswahl überschreitet das tägliche YouTube-Kontingent. Bitte weniger Themen wählen.")

    can_start = bool(categories) and not missing and running is None
    if st.button("▶ Lauf starten", type="primary", disabled=not can_start):
        run_id = run_control.start_run(PROJECT_ROOT, [] if all_categories else categories, max_results)
        open_progress(run_id)


@st.fragment(run_every=2)
def live_progress(run_dir: Path, shown_state: RunState) -> None:
    info = run_control.load_run(run_dir)
    if info.state != shown_state:
        st.rerun(scope="app")  # Zustand hat sich geaendert -> auch Auswahlliste oben aktualisieren
    status = info.status
    if status is None:
        st.info("Für diesen älteren Lauf gibt es keine Fortschrittsdaten.")
        if info.has_report and st.button("📊 Ergebnisse ansehen", type="primary"):
            open_results(info.run_id)
        return

    running = info.state == RunState.RUNNING
    st.subheader(state_label(info.state))
    st.progress(status.fraction_done, text=f"{status.fraction_done:.0%} · {status.stage_name}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Laufzeit", format_duration(status.started_at, info.finished_at))
    col2.metric("Schritt", f"{max(status.stage_index + 1, 0)} von {len(PIPELINE_STAGES)}")
    col3.metric("Videos pro Suchbegriff", status.max_results_per_query or "–")
    st.caption(f"Themen: {', '.join(status.categories) if status.categories else 'alle'}")

    for index, name in enumerate(PIPELINE_STAGES):
        if info.state == RunState.FINISHED or index < status.stage_index:
            icon = "✅"
        elif index == status.stage_index:
            icon = {RunState.RUNNING: "⏳", RunState.CANCELLED: "⏹️", RunState.FAILED: "❌"}[info.state]
        else:
            icon = "⚪"
        line = f"{icon} **{name}**" if index == status.stage_index else f"{icon} {name}"
        if index == status.stage_index and status.detail and info.state != RunState.FINISHED:
            line += f" · {status.detail}"
        st.markdown(line)

    if running:
        if stop_requested(run_dir):
            st.info("Stopp angefordert. Der Agent hält nach dem aktuellen Arbeitsschritt an.")
            if st.button("Sofort beenden", help="Beendet den Prozess hart. Bereits gesammelte Daten gehen verloren."):
                run_control.kill_run(run_dir)
                st.rerun(scope="fragment")
        elif st.button("⏹ Lauf anhalten", help="Der Agent hört nach dem aktuellen Video bzw. der aktuellen Suchanfrage auf."):
            request_stop(run_dir)
            st.rerun(scope="fragment")
    elif info.state == RunState.FINISHED:
        st.success(f"Lauf abgeschlossen in {format_duration(status.started_at, info.finished_at)}.")
        if st.button("📊 Ergebnisse ansehen", type="primary"):
            open_results(info.run_id)
    elif info.state == RunState.CANCELLED:
        st.warning("Der Lauf wurde angehalten. Es wurde kein Report gespeichert.")
    elif info.state == RunState.FAILED:
        st.error(f"Der Lauf ist fehlgeschlagen: {info.error or 'unbekannter Fehler'}")

    log_path = run_dir / LOG_FILE
    if log_path.exists():
        with st.expander("Ausgabe des Agenten (log.txt)", expanded=info.state == RunState.FAILED):
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            st.code(log_text[-5000:] or "(noch keine Ausgabe)", language="text")


def page_progress() -> None:
    st.title("⏱️ Fortschritt")
    runs = run_control.list_runs(PROJECT_ROOT)
    if not runs:
        st.info("Es gibt noch keine Läufe.")
        if st.button("Neuen Lauf starten"):
            st.switch_page(PAGES["new"])
        return

    run_ids = [run.run_id for run in runs]
    active = next((run.run_id for run in runs if run.state == RunState.RUNNING), None)
    preferred = st.session_state.get("selected_run") or active or run_ids[0]
    labels = {run.run_id: f"{format_local(run.started_at)} · {state_label(run.state)} · {run.run_id}" for run in runs}
    run_id = st.selectbox(
        "Lauf",
        options=run_ids,
        index=run_ids.index(preferred) if preferred in run_ids else 0,
        format_func=labels.get,
    )
    st.session_state["selected_run"] = run_id
    live_progress(DATA_DIR / run_id, next(run.state for run in runs if run.run_id == run_id))


def page_all_runs() -> None:
    st.title("🗂️ Alle Läufe")
    runs = run_control.list_runs(PROJECT_ROOT)
    if not runs:
        st.info("Es gibt noch keine Läufe.")
        return

    table = pd.DataFrame(
        [
            {
                "Gestartet": format_local(run.started_at),
                "Status": state_label(run.state),
                "Themen": ", ".join(run.categories) if run.categories else "alle",
                "Gültige Shorts": "–" if run.videos_valid is None else str(run.videos_valid),
                "Dauer": format_duration(run.started_at, run.finished_at) if run.state != RunState.RUNNING else "läuft …",
                "Lauf-ID": run.run_id,
            }
            for run in runs
        ]
    )
    st.caption("Zeile anklicken, um den Lauf zu öffnen. Mehrere Zeilen auswählen, um sie zu löschen.")
    event = st.dataframe(
        table, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="multi-row"
    )
    selected = [runs[i] for i in event.selection.rows]
    if not selected:
        return

    if len(selected) == 1:
        run = selected[0]
        col1, col2 = st.columns(2)
        if col1.button("⏱️ Fortschritt anzeigen", use_container_width=True):
            open_progress(run.run_id)
        if col2.button("📊 Ergebnisse ansehen", use_container_width=True, disabled=not run.has_report, type="primary"):
            open_results(run.run_id)

    deletable = [run for run in selected if run.state != RunState.RUNNING]
    if len(deletable) < len(selected):
        st.info("Laufende Läufe können nicht gelöscht werden. Bitte zuerst auf der Seite „Fortschritt“ anhalten.")
    label = "🗑️ Lauf löschen" if len(deletable) == 1 else f"🗑️ {len(deletable)} Läufe löschen"
    if deletable and st.button(label):
        confirm_delete([run.run_id for run in deletable])


@st.dialog("Läufe löschen")
def confirm_delete(run_ids: list[str]) -> None:
    st.write(
        f"Diese {len(run_ids)} Läufe werden mit allen Dateien (Rohdaten, Report, Log) endgültig gelöscht:"
        if len(run_ids) > 1
        else "Dieser Lauf wird mit allen Dateien (Rohdaten, Report, Log) endgültig gelöscht:"
    )
    for run_id in run_ids:
        st.markdown(f"- `{run_id}`")
    st.warning("Das lässt sich nicht rückgängig machen.")
    col1, col2 = st.columns(2)
    if col1.button("Endgültig löschen", type="primary", use_container_width=True):
        errors = []
        for run_id in run_ids:
            try:
                run_control.delete_run(PROJECT_ROOT, run_id)
            except (ValueError, OSError) as exc:
                errors.append(str(exc))
        if st.session_state.get("selected_run") in run_ids:
            del st.session_state["selected_run"]
        if errors:
            st.error("\n\n".join(errors))
        else:
            st.rerun()
    if col2.button("Abbrechen", use_container_width=True):
        st.rerun()


def page_results() -> None:
    runs = find_runs(DATA_DIR)

    if not runs:
        st.title("📊 Ergebnisse")
        st.info("Noch kein fertiger Report vorhanden. Starte zuerst einen Lauf.")
        if st.button("Neuen Lauf starten"):
            st.switch_page(PAGES["new"])
        return

    preferred = st.session_state.get("selected_run")
    run_names = [p.name for p in runs]
    with st.sidebar:
        selected_dir = st.selectbox(
            "Report-Lauf",
            options=runs,
            index=run_names.index(preferred) if preferred in run_names else 0,
            format_func=lambda p: f"{p.name} " + ("(neuester)" if p == runs[0] else ""),
        )
    st.session_state["selected_run"] = selected_dir.name

    report = load_report(selected_dir)
    meta = report.run_metadata

    st.title("📊 Ergebnisse")
    st.caption(
        f"Lauf-ID `{meta.run_id}` · erstellt {meta.started_at:%d.%m.%Y %H:%M} UTC · Modell `{meta.model_used}`"
    )

    with st.sidebar:
        st.subheader("Lauf-Details")
        st.write("**Kategorien:**", ", ".join(meta.categories_used) or "–")
        st.write("**Suchbegriffe:**")
        for topic in meta.search_topics:
            st.caption(f"· {topic}")
        st.write("**Datenquellen:**", ", ".join(s.value for s in meta.data_sources) or "–")
        if meta.errors:
            st.write("**Fehler im Lauf:**", len(meta.errors))

    # --- KPI-Kacheln ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Geprüfte Shorts", meta.videos_examined)
    col2.metric("Gültige Shorts", meta.videos_valid)
    col3.metric("Verworfen", meta.videos_rejected)
    retention_completeness = report.analysis.data_completeness.get("retention", 0.0)
    col4.metric("Retention verfügbar", f"{retention_completeness:.0%}")
    col5.metric("Erkannte Muster", len(report.patterns))

    st.subheader("Executive Summary")
    st.info(report.executive_summary)

    tabs = st.tabs(
        ["Themen", "Hooks", "Formate", "Videolänge", "Datenvollständigkeit", "Rankings", "Muster", "Einschränkungen & Empfehlungen", "Rohdaten"]
    )

    with tabs[0]:
        render_group_section("Themenanalyse", report.analysis.by_topic)
    with tabs[1]:
        render_group_section("Hook-Analyse", report.analysis.by_hook_type)
    with tabs[2]:
        render_group_section("Format-Analyse", report.analysis.by_format)
    with tabs[3]:
        render_group_section("Analyse der Videolänge", report.analysis.by_duration_bucket)
    with tabs[4]:
        if report.analysis.data_completeness:
            st.plotly_chart(make_completeness_chart(report.analysis.data_completeness), use_container_width=True)
            st.caption(
                "Zeigt, wie viele der untersuchten Shorts für jedes Feld einen echten Wert hatten. "
                "0 % bedeutet: für dieses Feld lagen keine Daten vor — der Wert wurde NICHT geschätzt "
                "(siehe Kapitel 7 der Projektdokumentation)."
            )
        else:
            st.info("Keine Angabe zur Datenvollständigkeit in diesem Lauf.")
    with tabs[5]:
        rank_col1, rank_col2 = st.columns(2)
        with rank_col1:
            render_ranking_table("Top-Themen", report.top_topics)
        with rank_col2:
            render_ranking_table("Top-Formate", report.top_formats)
    with tabs[6]:
        render_patterns(report.patterns)
    with tabs[7]:
        limit_col, rec_col = st.columns(2)
        with limit_col:
            st.markdown("**Einschränkungen der Daten**")
            all_limitations = list(report.limitations) + list(meta.limitations)
            if not all_limitations:
                st.info("Keine besonderen Einschränkungen protokolliert.")
            for limitation in all_limitations:
                st.markdown(f"- {limitation}")
        with rec_col:
            st.markdown("**Konkrete Handlungsempfehlungen**")
            if not report.recommendations:
                st.info("Keine automatisch generierten Empfehlungen verfügbar.")
            for recommendation in report.recommendations:
                st.markdown(f"- {recommendation}")
    with tabs[8]:
        clean_df = load_clean_data(selected_dir)
        if clean_df is None:
            st.info("Keine clean.csv für diesen Lauf gefunden.")
        else:
            st.dataframe(clean_df, use_container_width=True, hide_index=True)
            st.download_button(
                "clean.csv herunterladen",
                data=clean_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{meta.run_id}_clean.csv",
                mime="text/csv",
            )
        report_md_path = selected_dir / "report.md"
        if report_md_path.exists():
            st.download_button(
                "report.md herunterladen",
                data=report_md_path.read_text(encoding="utf-8").encode("utf-8"),
                file_name=f"{meta.run_id}_report.md",
                mime="text/markdown",
            )



def main() -> None:
    st.set_page_config(page_title="Shorts Analytics – Control Panel", page_icon="📊", layout="wide")
    PAGES["new"] = st.Page(page_new_run, title="Neuer Lauf", icon="🚀", default=True)
    PAGES["progress"] = st.Page(page_progress, title="Fortschritt", icon="⏱️", url_path="fortschritt")
    PAGES["results"] = st.Page(page_results, title="Ergebnisse", icon="📊", url_path="ergebnisse")
    PAGES["runs"] = st.Page(page_all_runs, title="Alle Läufe", icon="🗂️", url_path="laeufe")
    st.navigation(list(PAGES.values())).run()


if __name__ == "__main__":
    main()
