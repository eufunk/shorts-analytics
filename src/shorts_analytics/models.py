"""Typisierte Datenstrukturen, die zwischen den Pipeline-Stages fliessen.

Alle Stages im Agenten (siehe agent.py) kommunizieren ausschliesslich ueber
diese Pydantic-Modelle statt ueber lose dicts. Das macht Fehler frueh
sichtbar (Validierung) und die einzelnen Stages unabhaengig testbar.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class DataSource(str, Enum):
    """Herkunft eines einzelnen Datenfelds.

    Diese Unterscheidung ist die wichtigste Regel im gesamten Projekt: der
    Agent darf niemals fehlende Daten erfinden. Jeder Wert, der nicht aus
    einer echten Quelle stammt, MUSS als UNAVAILABLE markiert werden.
    """

    PUBLIC = "public"                # oeffentliche YouTube Data API
    OWN_ANALYTICS = "own_analytics"  # eigene YouTube-Studio-/Analytics-Daten
    DERIVED = "derived"              # aus anderen Feldern berechnet
    UNAVAILABLE = "unavailable"      # nicht verfuegbar - nie geschaetzt


class Sourced(BaseModel, Generic[T]):
    """Ein Wert zusammen mit der Angabe, woher er stammt."""

    value: Optional[T] = None
    source: DataSource = DataSource.UNAVAILABLE

    @classmethod
    def unavailable(cls) -> "Sourced[T]":
        return cls(value=None, source=DataSource.UNAVAILABLE)

    @classmethod
    def public(cls, value: T) -> "Sourced[T]":
        return cls(value=value, source=DataSource.PUBLIC)

    @classmethod
    def own_analytics(cls, value: T) -> "Sourced[T]":
        return cls(value=value, source=DataSource.OWN_ANALYTICS)

    @classmethod
    def derived(cls, value: T) -> "Sourced[T]":
        return cls(value=value, source=DataSource.DERIVED)

    @property
    def is_available(self) -> bool:
        return self.value is not None and self.source != DataSource.UNAVAILABLE


class HookType(str, Enum):
    UEBERRASCHENDE_AUSSAGE = "ueberraschende_aussage"
    DIREKTE_FRAGE = "direkte_frage"
    UNGEWOEHNLICHE_BEHAUPTUNG = "ungewoehnliche_behauptung"
    KONFLIKT_ODER_PROBLEM = "konflikt_oder_problem"
    SOFORTIGE_HANDLUNG = "sofortige_handlung"
    VISUELL_UNGEWOEHNLICH = "visuell_ungewoehnliche_szene"
    ERGEBNIS_VERSPRECHEN = "versprechen_eines_ergebnisses"
    INFORMATIONSLUECKE = "offene_frage_informationsluecke"
    SONSTIGE = "sonstige"


class ShortVideo(BaseModel):
    """Ein einzelnes YouTube Short mit allen bislang bekannten Merkmalen."""

    video_id: str
    channel_id: str
    channel_title: str
    title: str
    description: str = ""
    published_at: dt.datetime
    duration_seconds: int
    thumbnail_url: Optional[str] = None
    search_topic: str  # Suchthema, das dieses Video gefunden hat

    # Ebene 1 - oeffentlich (YouTube Data API v3)
    views: Sourced[int] = Field(default_factory=Sourced.unavailable)
    likes: Sourced[int] = Field(default_factory=Sourced.unavailable)
    comments: Sourced[int] = Field(default_factory=Sourced.unavailable)

    # Ebene 2 - nur fuer den eigenen Kanal verfuegbar (YouTube Analytics API)
    average_view_percentage: Sourced[float] = Field(default_factory=Sourced.unavailable)
    average_view_duration_seconds: Sourced[float] = Field(default_factory=Sourced.unavailable)
    stayed_to_watch_ratio: Sourced[float] = Field(default_factory=Sourced.unavailable)

    # Ebene 3 - abgeleitet aus anderen Feldern
    engagement_rate: Sourced[float] = Field(default_factory=Sourced.unavailable)

    def retention_proxy(self) -> Optional[float]:
        """Bester verfuegbarer Zuschauerbindungs-Indikator, sonst None.

        Views/Likes sind bewusst KEIN Ersatz fuer Retention-Daten - fehlt
        die echte Kennzahl, gibt diese Methode None zurueck statt zu raten.
        """
        if self.average_view_percentage.is_available:
            return self.average_view_percentage.value
        return None


class ClassificationResult(BaseModel):
    """LLM-Ergebnis der semantischen Klassifizierung eines einzelnen Shorts."""

    video_id: str
    topic: str
    subtopic: Optional[str] = None
    is_new_topic_suggestion: bool = False
    hook_type: HookType
    format_type: str  # z.B. Story, Liste, Frage, Experiment, Erklaerung
    has_tension_build: Optional[bool] = None
    has_payoff: Optional[bool] = None
    has_loop_potential: Optional[bool] = None
    has_call_to_action: Optional[bool] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning: str = ""


class RunMetadata(BaseModel):
    """Protokoll eines einzelnen Agenten-Laufs, fuer Nachvollziehbarkeit."""

    run_id: str
    started_at: dt.datetime
    finished_at: Optional[dt.datetime] = None
    search_topics: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    categories_used: list[str] = Field(default_factory=list)
    videos_examined: int = 0
    videos_valid: int = 0
    videos_rejected: int = 0
    model_used: str = ""
    data_sources: list[DataSource] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class GroupStats(BaseModel):
    """Aggregierte Kennzahlen fuer eine Gruppe (z.B. ein Thema oder Hook-Typ)."""

    group: str
    sample_size: int
    mean_views: Optional[float] = None
    median_views: Optional[float] = None
    mean_retention: Optional[float] = None
    median_retention: Optional[float] = None
    p25_retention: Optional[float] = None
    p75_retention: Optional[float] = None
    is_reliable: bool = False


class AnalysisResult(BaseModel):
    """Ergebnis der rein deterministischen quantitativen Analyse (Python/pandas)."""

    by_topic: list[GroupStats] = Field(default_factory=list)
    by_hook_type: list[GroupStats] = Field(default_factory=list)
    by_format: list[GroupStats] = Field(default_factory=list)
    by_duration_bucket: list[GroupStats] = Field(default_factory=list)
    correlations: dict[str, float] = Field(default_factory=dict)
    outlier_video_ids: list[str] = Field(default_factory=list)
    data_completeness: dict[str, float] = Field(default_factory=dict)


class PatternInsight(BaseModel):
    """Vom LLM interpretiertes Muster - basiert ausschliesslich auf bereits
    berechneten Aggregaten (analysis.AnalysisResult), nicht auf Rohdaten."""

    title: str
    description: str
    supporting_evidence: str
    confidence: str = "mittel"  # "hoch" | "mittel" | "niedrig"


class RankingEntry(BaseModel):
    rank: int
    group: str
    metric_name: str
    metric_value: float
    sample_size: int
    is_reliable: bool


class Report(BaseModel):
    """Finales, strukturiertes Analyseergebnis eines Laufs."""

    run_metadata: RunMetadata
    executive_summary: str
    analysis: AnalysisResult
    top_topics: list[RankingEntry] = Field(default_factory=list)
    top_formats: list[RankingEntry] = Field(default_factory=list)
    patterns: list[PatternInsight] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
