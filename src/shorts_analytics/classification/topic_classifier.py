"""LLM-Stage: ordnet ein Short einem Thema/Unterthema zu.

Kategorien sind nicht hart verdrahtet: das Modell darf ein neues Thema
vorschlagen, wenn keine der Standardkategorien passt. Solche Vorschlaege
werden markiert (is_new_topic_suggestion) statt automatisch uebernommen zu
werden - ein Mensch entscheidet spaeter, ob sie in config.DEFAULT_CATEGORIES
aufgenommen werden.
"""

from __future__ import annotations

from pathlib import Path

from shorts_analytics.classification.llm_client import LLMClient
from shorts_analytics.config import DEFAULT_CATEGORIES
from shorts_analytics.models import ShortVideo

_PROMPT_PATH = Path(__file__).parent / "prompts" / "topic_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

_SYSTEM_PROMPT = (
    "Du bist ein praeziser Klassifizierer fuer YouTube-Shorts-Themen. "
    "Antworte ausschliesslich mit gueltigem JSON, ohne Erklaerungstext."
)


def classify_topic(client: LLMClient, video: ShortVideo) -> dict:
    """Gibt {'topic': str, 'subtopic': str|None, 'is_new_topic_suggestion': bool} zurueck."""
    prompt = _PROMPT_TEMPLATE.format(
        categories="\n".join(f"- {c}" for c in DEFAULT_CATEGORIES),
        title=video.title,
        description=video.description[:500],
    )
    return client.complete_json(system_prompt=_SYSTEM_PROMPT, user_prompt=prompt)
