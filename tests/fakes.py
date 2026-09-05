"""Fake-Implementierungen der externen Abhaengigkeiten (kein Netzwerk, kein API-Key noetig).

Werden per Dependency-Injection in den ResearchAgent eingesetzt, um den
kompletten Pipeline-Ablauf zu testen, ohne echte YouTube-/Anthropic-APIs
aufzurufen.
"""

from __future__ import annotations

from tests.factories import make_video


class FakePublicCollector:
    """Ersetzt YouTubePublicCollector: liefert deterministische Test-Videos."""

    def __init__(self, videos_per_query: int = 3):
        self.videos_per_query = videos_per_query

    def search_shorts(self, query: str, max_results: int = 15) -> list[str]:
        return [f"{query}_{i}" for i in range(min(self.videos_per_query, max_results))]

    def fetch_video_details(self, video_ids: list[str], search_topic: str) -> list:
        return [
            make_video(
                video_id=video_id,
                topic=search_topic,
                views=1000 + i * 50,
                likes=100 + i,
                comments=10 + i,
                title=f"Short {video_id}",
            )
            for i, video_id in enumerate(video_ids)
        ]


class FakeLLMClient:
    """Ersetzt LLMClient: gibt anhand des System-Prompts plausible Fake-Antworten zurueck."""

    def __init__(self, model: str = "fake-model"):
        self.model = model
        self.calls: list[str] = []

    def complete_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024):
        self.calls.append(system_prompt)
        if "Klassifizierer fuer YouTube-Shorts-Themen" in system_prompt:
            return {"topic": "Wissen / Bildung", "subtopic": None, "is_new_topic_suggestion": False}
        if "Kurzvideo-Storytelling" in system_prompt:
            return {
                "hook_type": "direkte_frage",
                "format_type": "Erklaerung",
                "has_tension_build": True,
                "has_payoff": True,
                "has_loop_potential": False,
                "has_call_to_action": False,
                "confidence": 0.9,
                "reasoning": "Fake-Begruendung",
            }
        if "Muster ableiten" in system_prompt:
            return {
                "patterns": [
                    {
                        "title": "Kurze Erklaervideos performen gut",
                        "description": "Test-Beschreibung",
                        "supporting_evidence": "n=10",
                        "confidence": "mittel",
                    }
                ]
            }
        if "Handlungsempfehlungen" in system_prompt:
            return {"recommendations": ["Mehr direkte Fragen als Hook verwenden."]}
        raise AssertionError(f"Unerwarteter system_prompt in FakeLLMClient: {system_prompt!r}")

    def complete_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
        self.calls.append(system_prompt)
        return "Dies ist eine Fake-Zusammenfassung basierend auf den gegebenen Fakten."
