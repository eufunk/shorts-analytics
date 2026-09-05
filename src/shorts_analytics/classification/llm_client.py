"""Duenner Wrapper um das Anthropic SDK fuer strukturierte JSON-Antworten.

Alle LLM-Aufrufe im Projekt laufen ueber diese Klasse, damit Modellwahl,
Fehlerbehandlung und JSON-Parsing an einer Stelle gebuendelt sind.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from shorts_analytics.config import DEFAULT_MODEL


class LLMClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> Any:
        """Ruft das Modell auf und erwartet eine reine JSON-Antwort.

        Wirft einen ValueError, wenn die Antwort kein gueltiges JSON ist. Die
        aufrufende Stage entscheidet, wie damit umgegangen wird - im Agenten
        wird eine einzelne fehlgeschlagene Klassifizierung uebersprungen,
        statt den ganzen Lauf abzubrechen.
        """
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return json.loads(_extract_json(text))
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM-Antwort war kein gueltiges JSON: {text!r}") from exc

    def complete_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
        """Ruft das Modell auf und gibt reinen Freitext zurueck (z.B. fuer die Executive Summary)."""
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()


def _extract_json(text: str) -> str:
    """Extrahiert den JSON-Teil aus einer Modellantwort (falls Markdown-Fences vorhanden)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[len("json"):]
    return stripped.strip()
