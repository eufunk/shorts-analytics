"""Zentrale, versionierte Konfiguration: Kategorien, Suchbegriffe, Schwellwerte.

Diese Werte sind bewusst als einfache Python-Datenstrukturen gehalten (statt
in einer Datenbank), damit Aenderungen ueber Git nachvollziehbar bleiben.
"""

from __future__ import annotations

import os

# Startpunkt fuer die thematische Kategorisierung. Nicht hart verdrahtet im
# Sinne von "ausschliesslich diese Kategorien": der Klassifizierer darf neue
# Unterkategorien vorschlagen (siehe classification/topic_classifier.py),
# diese werden separat protokolliert statt automatisch uebernommen.
DEFAULT_CATEGORIES: list[str] = [
    "Unterhaltung",
    "Kurioses / überraschende Fakten",
    "Wissen / Bildung",
    "Psychologie",
    "Finanzen",
    "Motivation / Selbstoptimierung",
    "Fitness",
    "Sport",
    "Gaming",
    "Technik / KI",
    "Geschichte",
    "Wissenschaft",
    "Tiere",
    "Reisen",
    "Prominente / Popkultur",
    "Storytelling",
    "Humor / Comedy",
    "Beziehungen / soziale Themen",
    "Alltag / Lifehacks",
    "Sonstige",
]

# Suchbegriffe pro Kategorie fuer die Research-Stage (YouTube Data API
# search.list). Dies steuert, welche Shorts ueberhaupt gefunden werden -
# und wird pro Lauf in RunMetadata.search_topics protokolliert.
DEFAULT_SEARCH_QUERIES: dict[str, list[str]] = {
    "Unterhaltung": ["funny shorts", "entertainment shorts"],
    "Kurioses / überraschende Fakten": ["did you know shorts", "crazy facts shorts"],
    "Wissen / Bildung": ["learn shorts", "educational shorts"],
    "Psychologie": ["psychology facts shorts", "human behavior shorts"],
    "Finanzen": ["money tips shorts", "finance shorts"],
    "Motivation / Selbstoptimierung": ["motivation shorts", "self improvement shorts"],
    "Fitness": ["fitness tips shorts", "workout shorts"],
    "Sport": ["sports highlights shorts"],
    "Gaming": ["gaming shorts", "gameplay shorts"],
    "Technik / KI": ["ai shorts", "tech shorts"],
    "Geschichte": ["history facts shorts"],
    "Wissenschaft": ["science shorts", "science facts shorts"],
    "Tiere": ["animal shorts", "cute animals shorts"],
    "Reisen": ["travel shorts"],
    "Prominente / Popkultur": ["celebrity shorts", "pop culture shorts"],
    "Storytelling": ["story time shorts", "storytelling shorts"],
    "Humor / Comedy": ["comedy shorts"],
    "Beziehungen / soziale Themen": ["relationship advice shorts"],
    "Alltag / Lifehacks": ["life hacks shorts"],
}

# Mindest-Stichprobengroesse, ab der eine Gruppenauswertung als belastbar
# gilt. Kleinere Gruppen werden im Report explizit als "nicht belastbar"
# markiert statt stillschweigend mitgerankt zu werden.
MIN_RELIABLE_SAMPLE_SIZE: int = 8

# Anzahl der Ergebnisse pro Suchanfrage (YouTube Data API search.list).
DEFAULT_MAX_RESULTS_PER_QUERY: int = 15

# Dauerbereich fuer "Shorts" laut YouTube (<= 3 Minuten, ueblicherweise <= 60s).
MAX_SHORT_DURATION_SECONDS: int = 180

# Claude-Modell fuer Klassifizierung / Musterinterpretation / Summary.
DEFAULT_MODEL: str = os.environ.get("SHORTS_ANALYTICS_MODEL", "claude-sonnet-5")

# Dauer-Buckets fuer die Videolaengen-Analyse (in Sekunden, jeweils exklusive Obergrenze).
DURATION_BUCKETS: list[tuple[str, int, int]] = [
    ("0-15s", 0, 15),
    ("15-30s", 15, 30),
    ("30-60s", 30, 60),
    ("60-180s", 60, 180),
]
