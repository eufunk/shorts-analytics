"""Streamlit-Dashboard: visualisiert einen bereits erzeugten Research-Report.

Startet NIE selbst einen neuen Agenten-Lauf - es liest ausschliesslich die
Artefakte, die `agent.py` bereits unter data/runs/<run_id>/ abgelegt hat, und
zeigt standardmaessig den zuletzt erzeugten Lauf an. Ein neuer Report entsteht
weiterhin nur ueber die CLI (`shorts-analytics ...`).

Start: streamlit run dashboard/app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shorts_analytics.models import GroupStats, PatternInsight, RankingEntry, Report

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
# Seite
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Shorts Analytics Dashboard", page_icon="📊", layout="wide")

    data_dir = Path(__file__).resolve().parents[1] / "data" / "runs"
    runs = find_runs(data_dir)

    if not runs:
        st.title("📊 YouTube Shorts Research-Dashboard")
        st.warning(
            "Noch kein Report gefunden. Führe zuerst einen Analyse-Lauf über die Kommandozeile aus:\n\n"
            "`shorts-analytics --category \"...\" --max-results 5`"
        )
        st.stop()

    with st.sidebar:
        st.header("Shorts Analytics")
        selected_dir = st.selectbox(
            "Report-Lauf",
            options=runs,
            index=0,
            format_func=lambda p: f"{p.name} " + ("(neuester)" if p == runs[0] else ""),
        )
        st.caption(
            "Das Dashboard zeigt einen bereits erstellten Report an. "
            "Es wird hier **kein neuer Analyse-Lauf** gestartet — dafür die CLI verwenden."
        )

    report = load_report(selected_dir)
    meta = report.run_metadata

    st.title("📊 YouTube Shorts Research-Dashboard")
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


if __name__ == "__main__":
    main()
