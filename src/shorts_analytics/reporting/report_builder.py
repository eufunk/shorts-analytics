"""Report-Stage: baut aus Analyseergebnissen ein strukturiertes Report-Objekt.

Zahlen und Struktur kommen ausschliesslich aus Python (AnalysisResult,
RankingEntry, RunMetadata). Nur die lesbare Zusammenfassung und die
Handlungsempfehlungen werden vom LLM formuliert - und ausschliesslich
basierend auf den bereits berechneten Fakten, nie frei erfunden.
"""

from __future__ import annotations

from shorts_analytics.classification.llm_client import LLMClient
from shorts_analytics.models import AnalysisResult, PatternInsight, RankingEntry, Report, RunMetadata

_SUMMARY_SYSTEM_PROMPT = (
    "Du fasst eine Datenanalyse zu YouTube Shorts in einer knappen, "
    "verstaendlichen Executive Summary zusammen. Nutze ausschliesslich die "
    "gegebenen Fakten, erfinde keine Zahlen. Schreibe 3-5 Saetze auf Deutsch."
)

_RECOMMENDATIONS_SYSTEM_PROMPT = (
    "Du leitest aus einer Datenanalyse zu YouTube Shorts konkrete, "
    "umsetzbare Handlungsempfehlungen fuer die Produktion eigener Shorts ab. "
    "Stuetze jede Empfehlung auf die gegebenen Fakten. Antworte ausschliesslich "
    "mit gueltigem JSON, ohne Erklaerungstext."
)


def build_report(
    client: LLMClient,
    run_metadata: RunMetadata,
    analysis: AnalysisResult,
    top_topics: list[RankingEntry],
    top_formats: list[RankingEntry],
    patterns: list[PatternInsight],
    limitations: list[str],
) -> Report:
    summary = _generate_executive_summary(client, run_metadata, top_topics, patterns)
    recommendations = _generate_recommendations(client, top_topics, top_formats, patterns)

    return Report(
        run_metadata=run_metadata,
        executive_summary=summary,
        analysis=analysis,
        top_topics=top_topics,
        top_formats=top_formats,
        patterns=patterns,
        limitations=limitations,
        recommendations=recommendations,
    )


def _generate_executive_summary(
    client: LLMClient,
    run_metadata: RunMetadata,
    top_topics: list[RankingEntry],
    patterns: list[PatternInsight],
) -> str:
    facts = (
        f"Untersuchte Shorts: {run_metadata.videos_valid} (von {run_metadata.videos_examined} geprueft)\n"
        f"Kategorien: {', '.join(run_metadata.categories_used) or 'keine'}\n"
        f"Top-Themen: {_format_ranking(top_topics)}\n"
        f"Erkannte Muster: {_format_patterns(patterns)}\n"
    )
    try:
        return client.complete_text(system_prompt=_SUMMARY_SYSTEM_PROMPT, user_prompt=facts)
    except Exception as exc:  # ein LLM-Fehler darf den Report nicht komplett verhindern
        return f"[Executive Summary konnte nicht automatisch erstellt werden: {exc}]"


def _generate_recommendations(
    client: LLMClient,
    top_topics: list[RankingEntry],
    top_formats: list[RankingEntry],
    patterns: list[PatternInsight],
) -> list[str]:
    prompt = (
        f"Top-Themen: {_format_ranking(top_topics)}\n"
        f"Top-Formate: {_format_ranking(top_formats)}\n"
        f"Muster: {_format_patterns(patterns)}\n\n"
        'Antworte mit: {"recommendations": ["...", "..."]} (maximal 6 Eintraege)'
    )
    try:
        result = client.complete_json(system_prompt=_RECOMMENDATIONS_SYSTEM_PROMPT, user_prompt=prompt)
        return list(result.get("recommendations", [])) if isinstance(result, dict) else []
    except Exception:
        return []


def _format_ranking(entries: list[RankingEntry]) -> str:
    if not entries:
        return "keine belastbaren Daten"
    return "; ".join(f"{e.group} ({e.metric_name}={e.metric_value:.2f}, n={e.sample_size})" for e in entries[:5])


def _format_patterns(patterns: list[PatternInsight]) -> str:
    if not patterns:
        return "keine"
    return "; ".join(f"{p.title} ({p.confidence})" for p in patterns)
