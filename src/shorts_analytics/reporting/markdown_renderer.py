"""Rendert ein Report-Objekt als lesbares Markdown-Dokument.

Gliederung folgt der fachlichen Spezifikation (docs/YouTube_Shorts_Research_Analyse.docx)
und Prompt 2 (docs/Prompts.docx): Executive Summary, Methode, Datenbasis,
Themenanalyse, Zuschauerbindung, Videolaenge, Hook-Analyse, Format-Analyse,
Muster, Top-Themen/-Formate, Einschraenkungen, Handlungsempfehlungen.
"""

from __future__ import annotations

from shorts_analytics.models import GroupStats, RankingEntry, Report


def render_markdown(report: Report) -> str:
    meta = report.run_metadata
    sections = [
        f"# YouTube Shorts Research-Report\n\nLauf-ID: `{meta.run_id}` | Erstellt: {meta.started_at.isoformat()}",
        "## Executive Summary\n\n" + report.executive_summary,
        _render_methode(report),
        _render_datenbasis(report),
        _render_group_section("Themenanalyse", report.analysis.by_topic),
        _render_retention_section(report),
        _render_group_section("Analyse der Videolänge", report.analysis.by_duration_bucket),
        _render_group_section("Hook-Analyse", report.analysis.by_hook_type),
        _render_group_section("Format-Analyse", report.analysis.by_format),
        _render_patterns(report),
        _render_ranking_section("Top-Themen", report.top_topics),
        _render_ranking_section("Top-Formate", report.top_formats),
        _render_limitations(report),
        _render_recommendations(report),
    ]
    return "\n\n".join(sections) + "\n"


def _render_methode(report: Report) -> str:
    meta = report.run_metadata
    lines = [
        "## Untersuchungsmethode",
        f"- Suchthemen: {', '.join(meta.search_topics) or '–'}",
        f"- Filter: {meta.filters or '–'}",
        f"- Verwendete Kategorien: {', '.join(meta.categories_used) or '–'}",
        f"- Verwendetes Modell: {meta.model_used or '–'}",
        f"- Datenquellen: {', '.join(source.value for source in meta.data_sources) or '–'}",
    ]
    return "\n".join(lines)


def _render_datenbasis(report: Report) -> str:
    meta = report.run_metadata
    lines = [
        "## Datenbasis",
        f"- Geprüfte Shorts: {meta.videos_examined}",
        f"- Gültige Shorts (in Analyse): {meta.videos_valid}",
        f"- Verworfene Shorts: {meta.videos_rejected}",
        "",
        "**Datenvollständigkeit je Feld** (Anteil verfügbarer Werte):",
    ]
    if report.analysis.data_completeness:
        for field_name, ratio in report.analysis.data_completeness.items():
            lines.append(f"- {field_name}: {ratio:.0%}")
    else:
        lines.append("- keine Angabe")
    return "\n".join(lines)


def _render_retention_section(report: Report) -> str:
    lines = ["## Analyse der Zuschauerbindung"]
    completeness = report.analysis.data_completeness.get("retention", 0.0)
    if completeness == 0.0:
        lines.append(
            "Für keines der untersuchten Shorts lagen echte Retention-Daten "
            "(Ebene 2 / eigene YouTube-Analytics) vor. Diese Kennzahl ist für "
            "fremde Kanäle öffentlich nicht zugänglich und wurde daher **nicht** "
            "geschätzt. Die folgenden Analysen (Themen, Hook, Videolänge) "
            "basieren auf Aufrufen, Likes und Kommentaren als Näherung, sofern "
            "verfügbar."
        )
    else:
        lines.append(f"Retention-Daten waren für {completeness:.0%} der untersuchten Shorts verfügbar.")
        lines.append(_group_table(report.analysis.by_topic))
    return "\n\n".join(lines)


def _render_group_section(title: str, groups: list[GroupStats]) -> str:
    lines = [f"## {title}"]
    if not groups:
        lines.append("Keine Daten verfügbar.")
    else:
        lines.append(_group_table(groups))
    return "\n\n".join(lines)


def _group_table(groups: list[GroupStats]) -> str:
    header = "| Gruppe | n | zuverlässig? | Ø Aufrufe | Median Aufrufe | Ø Retention | Median Retention |"
    separator = "|---|---|---|---|---|---|---|"
    rows = [header, separator]
    for group in groups:
        rows.append(
            "| {group} | {n} | {reliable} | {mean_views} | {median_views} | {mean_retention} | {median_retention} |".format(
                group=group.group,
                n=group.sample_size,
                reliable="ja" if group.is_reliable else "nein (zu kleine Stichprobe)",
                mean_views=_fmt(group.mean_views),
                median_views=_fmt(group.median_views),
                mean_retention=_fmt(group.mean_retention, percent=True),
                median_retention=_fmt(group.median_retention, percent=True),
            )
        )
    return "\n".join(rows)


def _render_patterns(report: Report) -> str:
    lines = ["## Häufige Muster erfolgreicher Shorts"]
    if not report.patterns:
        lines.append("Keine Muster identifiziert (zu wenig Daten oder LLM-Analyse fehlgeschlagen).")
    else:
        for pattern in report.patterns:
            lines.append(
                f"### {pattern.title} (Konfidenz: {pattern.confidence})\n"
                f"{pattern.description}\n\n*Beleg:* {pattern.supporting_evidence}"
            )
    return "\n\n".join(lines)


def _render_ranking_section(title: str, entries: list[RankingEntry]) -> str:
    lines = [f"## {title}"]
    if not entries:
        lines.append("Keine belastbaren Daten für ein Ranking.")
    else:
        header = "| Rang | Gruppe | Kennzahl | Wert | n | zuverlässig? |"
        separator = "|---|---|---|---|---|---|"
        rows = [header, separator]
        for entry in entries:
            rows.append(
                f"| {entry.rank} | {entry.group} | {entry.metric_name} | {entry.metric_value:.2f} | "
                f"{entry.sample_size} | {'ja' if entry.is_reliable else 'nein'} |"
            )
        lines.append("\n".join(rows))
    return "\n\n".join(lines)


def _render_limitations(report: Report) -> str:
    lines = ["## Einschränkungen der Daten"]
    all_limitations = list(report.limitations) + list(report.run_metadata.limitations)
    if report.run_metadata.errors:
        all_limitations.append(f"{len(report.run_metadata.errors)} Fehler traten während des Laufs auf (siehe run_metadata.json).")
    if not all_limitations:
        lines.append("Keine besonderen Einschränkungen protokolliert.")
    else:
        lines.extend(f"- {limitation}" for limitation in all_limitations)
    return "\n".join(lines)


def _render_recommendations(report: Report) -> str:
    lines = ["## Konkrete Handlungsempfehlungen"]
    if not report.recommendations:
        lines.append("Keine automatisch generierten Empfehlungen verfügbar.")
    else:
        lines.extend(f"- {rec}" for rec in report.recommendations)
    return "\n".join(lines)


def _fmt(value: float | None, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}" if percent else f"{value:,.0f}"
