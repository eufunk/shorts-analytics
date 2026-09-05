"""LLM-Stage: interpretiert bereits berechnete Aggregate zu verstaendlichen Mustern.

Bekommt ausschliesslich Zahlen aus analysis/stats.py als Input, keine
Rohdaten der einzelnen Videos - das begrenzt Kosten und Halluzinationsrisiko,
da das Modell nichts ueber einzelne Videos erfinden kann, das es nie gesehen hat.
"""

from __future__ import annotations

from shorts_analytics.classification.llm_client import LLMClient
from shorts_analytics.models import AnalysisResult, GroupStats, PatternInsight

_SYSTEM_PROMPT = (
    "Du bist ein Datenanalyst fuer YouTube-Shorts-Performance. Du bekommst "
    "ausschliesslich bereits berechnete Aggregat-Statistiken (keine "
    "Einzelvideos) und sollst daraus verstaendliche Muster ableiten. "
    "Erfinde keine Zahlen, die nicht in den Daten stehen. Antworte "
    "ausschliesslich mit gueltigem JSON, ohne Erklaerungstext."
)

_USER_PROMPT_TEMPLATE = """Hier sind die aggregierten Analyseergebnisse eines YouTube-Shorts-Research-Laufs:

Statistik nach Thema:
{by_topic}

Statistik nach Hook-Typ:
{by_hook_type}

Statistik nach Videolaenge:
{by_duration_bucket}

Korrelationen mit Zuschauerbindung/Aufrufen:
{correlations}

Datenvollstaendigkeit je Feld (Anteil verfuegbarer Werte):
{data_completeness}

Leite bis zu 5 konkrete, durch die Zahlen gestuetzte Muster ab. Beziehe dich
in "supporting_evidence" auf konkrete Werte aus den obigen Daten. Wenn die
Stichprobe fuer eine Aussage zu klein ist (reliable=False), markiere
confidence entsprechend niedriger oder lasse das Muster weg.

Antworte ausschliesslich mit folgendem JSON-Format:
{{"patterns": [{{"title": "...", "description": "...", "supporting_evidence": "...", "confidence": "hoch|mittel|niedrig"}}]}}
"""


def interpret_patterns(client: LLMClient, analysis: AnalysisResult) -> list[PatternInsight]:
    prompt = _USER_PROMPT_TEMPLATE.format(
        by_topic=_format_groups(analysis.by_topic),
        by_hook_type=_format_groups(analysis.by_hook_type),
        by_duration_bucket=_format_groups(analysis.by_duration_bucket),
        correlations=analysis.correlations or "keine (zu wenig Daten)",
        data_completeness=analysis.data_completeness or "keine Angabe",
    )
    result = client.complete_json(system_prompt=_SYSTEM_PROMPT, user_prompt=prompt, max_tokens=2048)
    patterns = result.get("patterns", []) if isinstance(result, dict) else []
    return [PatternInsight(**pattern) for pattern in patterns]


def _format_groups(groups: list[GroupStats]) -> str:
    if not groups:
        return "keine Daten"
    lines = []
    for group in groups:
        lines.append(
            f"- {group.group}: n={group.sample_size} (reliable={group.is_reliable}), "
            f"mean_retention={group.mean_retention}, median_retention={group.median_retention}, "
            f"mean_views={group.mean_views}"
        )
    return "\n".join(lines)
