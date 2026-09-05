"""Collector-Interface fuer eigene YouTube-Studio-/Analytics-Daten (Ebene 2).

Retention-Kennzahlen wie 'stayed to watch', durchschnittliche Wiedergabedauer
oder durchschnittlich gesehener Prozentsatz sind ueber die oeffentliche
YouTube Data API grundsaetzlich NICHT verfuegbar - YouTube stellt sie nur dem
Kanalinhaber selbst ueber die YouTube Analytics API (OAuth) bereit.

Dieses Modul definiert die Schnittstelle, die eine spaetere Implementierung
erfuellen muss, damit sie sich nahtlos in die Pipeline einfuegt. Die
eigentliche OAuth-Anbindung ist bewusst noch nicht umgesetzt, da sie eine
manuelle Google-Cloud-Einrichtung durch den Kanalinhaber voraussetzt.
"""

from __future__ import annotations

from typing import Protocol


class OwnAnalyticsCollector(Protocol):
    """Schnittstelle, die jede Ebene-2-Datenquelle erfuellen muss."""

    def fetch_retention_metrics(self, video_ids: list[str]) -> dict[str, dict[str, float]]:
        """Liefert je Video-ID die verfuegbaren Retention-Kennzahlen.

        Erwartete Schluessel je Video: 'average_view_percentage',
        'average_view_duration_seconds', 'stayed_to_watch_ratio'.
        Fehlt eine Kennzahl fuer ein Video, darf sie im Ergebnis-dict
        schlicht fehlen (nicht raten/interpolieren) - die aufrufende Stage
        markiert sie dann als DataSource.UNAVAILABLE.
        """
        ...


class NotConfiguredOwnAnalyticsCollector:
    """Platzhalter-Implementierung, solange keine OAuth-Anbindung existiert.

    Gibt fuer jede Anfrage bewusst leere Ergebnisse zurueck, statt Werte zu
    schaetzen - damit bleibt die Kernregel 'niemals Daten erfinden' auch bei
    fehlender Ebene-2-Anbindung erfuellt.
    """

    def fetch_retention_metrics(self, video_ids: list[str]) -> dict[str, dict[str, float]]:
        return {}
