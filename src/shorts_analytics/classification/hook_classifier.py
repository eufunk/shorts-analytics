"""LLM-Stage: erkennt Hook-Typ, Format und Story-Struktur eines Shorts.

Basiert (in v1) auf Titel/Beschreibung, da kein Video-/Audiomaterial
verarbeitet wird. Der Prompt weist das Modell an, bei Unsicherheit null
statt einer geratenen Einschaetzung zurueckzugeben.
"""

from __future__ import annotations

from pathlib import Path

from shorts_analytics.classification.llm_client import LLMClient
from shorts_analytics.models import ShortVideo

_PROMPT_PATH = Path(__file__).parent / "prompts" / "hook_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_SYSTEM_PROMPT = (
    "Du bist ein Experte fuer Kurzvideo-Storytelling und analysierst die "
    "Struktur von YouTube Shorts. Antworte ausschliesslich mit gueltigem "
    "JSON, ohne Erklaerungstext."
)


def classify_hook(client: LLMClient, video: ShortVideo) -> dict:
    prompt = _PROMPT_TEMPLATE.format(
        title=video.title,
        description=video.description[:500],
        duration_seconds=video.duration_seconds,
    )
    return client.complete_json(system_prompt=_SYSTEM_PROMPT, user_prompt=prompt)
