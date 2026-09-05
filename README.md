# shorts-analytics

Datenbasierte Analyse von YouTube Shorts zur Untersuchung von Zuschauerbindung, Durchschauquote, Videolänge, Hooks, Themen und Erfolgsfaktoren.

Dieses Repository enthält einen **Research-Agenten**, der eigenständig YouTube Shorts sammelt, analysiert und daraus einen strukturierten Report erstellt. Die fachliche Spezifikation liegt unter [`docs/YouTube_Shorts_Research_Analyse.docx`](docs/YouTube_Shorts_Research_Analyse.docx), die Architekturentscheidungen sind unten zusammengefasst.

## Architektur in Kürze

Der Agent ist **keine** Multi-Agent-/Tool-Calling-Konstruktion, sondern eine feste, nachvollziehbare Pipeline:

```
Research → Datensammlung → Validierung → Bereinigung → Klassifizierung (LLM)
  → Quantitative Analyse (Python) → Mustererkennung (LLM) → Ranking → Report
```

Ein LLM (Claude) wird nur dort eingesetzt, wo semantisches Verständnis nötig ist (Themen-/Hook-Klassifizierung, Musterinterpretation, Zusammenfassung). Mittelwerte, Mediane, Quantile, Korrelationen und Rankings werden ausschließlich deterministisch in Python/pandas berechnet.

**Wichtigste Regel:** Der Agent erfindet keine fehlenden Daten. Jedes Datenfeld trägt eine `DataSource` (`public`, `own_analytics`, `derived`, `unavailable`). Retention-Kennzahlen (Zuschauerbindung, „stayed to watch“) sind über die öffentliche YouTube-API grundsätzlich nicht für fremde Kanäle verfügbar und werden konsequent als `unavailable` ausgewiesen statt geschätzt.

Projektstruktur, Datenmodelle und Design-Entscheidungen im Detail: siehe `src/shorts_analytics/` (jedes Modul hat einen erklärenden Docstring) sowie den ursprünglichen Architekturplan.

## Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

Kopiere `.env.example` nach `.env` und trage deine API-Keys ein:

```bash
cp .env.example .env
```

- `YOUTUBE_API_KEY` – YouTube Data API v3 Key (Google Cloud Console → APIs & Services → Credentials). Benötigt keine OAuth-Anbindung.
- `ANTHROPIC_API_KEY` – Claude API Key ([console.anthropic.com](https://console.anthropic.com/)).
- `SHORTS_ANALYTICS_MODEL` – optional, Standard ist `claude-sonnet-5`.

## Verwendung

Einen vollständigen Analyse-Lauf starten (alle Standardkategorien, Standard-Suchtiefe):

```bash
shorts-analytics
```

Nur bestimmte Kategorien und eine kleinere Stichprobe untersuchen (empfohlen für den ersten Testlauf, schont die API-Quota):

```bash
shorts-analytics --category "Wissen / Bildung" --category "Motivation / Selbstoptimierung" --max-results 5
```

Alternativ ohne installiertes Skript:

```bash
python -m shorts_analytics.cli --category "Finanzen" --max-results 5
```

Jeder Lauf erzeugt einen Ordner unter `data/runs/<run_id>/` mit:

- `raw.json` – rohe, gesammelte Videodaten
- `clean.csv` – bereinigte Daten (Duplikate entfernt, normalisiert)
- `classifications.json` – LLM-Klassifizierung je Video (Thema, Hook-Typ, Struktur)
- `run_metadata.json` – Suchparameter, Zeitpunkt, verwendetes Modell, Fehler, Einschränkungen (Reproduzierbarkeit)
- `report.json` / `report.md` – der finale, strukturierte Research-Report

## Dashboard

Ein Streamlit-Dashboard (in [`dashboard/app.py`](dashboard/app.py)) visualisiert einen bereits erzeugten Report (KPI-Kacheln, Balkendiagramme je Thema/Hook/Format/Videolänge, Datenvollständigkeit, Rankings, erkannte Muster, Rohdaten-Export). Es startet **keinen neuen Analyse-Lauf** — es zeigt standardmäßig den zuletzt erzeugten Report an; ältere Läufe lassen sich in der Seitenleiste auswählen.

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

Voraussetzung: mindestens ein Lauf muss bereits über `shorts-analytics` erzeugt worden sein (siehe oben). Das Dashboard liest ausschließlich aus `data/runs/` und ist unabhängig vom `shorts_analytics`-Package als eigenständiges Tool im Ordner `dashboard/` organisiert.

## Eigene YouTube-Analytics-Daten (Ebene 2, optional)

Retention-Kennzahlen ("stayed to watch", durchschnittlich gesehener Prozentsatz) sind nur für den eigenen Kanal über die YouTube Analytics API (OAuth) verfügbar. Die Schnittstelle dafür ist in [`src/shorts_analytics/collectors/youtube_studio.py`](src/shorts_analytics/collectors/youtube_studio.py) vorbereitet (`OwnAnalyticsCollector`-Protokoll); die OAuth-Anbindung selbst ist noch nicht implementiert, da sie eine manuelle Google-Cloud-Einrichtung voraussetzt. Ohne diese Anbindung markiert der Agent alle Retention-Felder korrekt als „nicht verfügbar“, statt sie aus Aufrufen/Likes zu schätzen.

## Tests

```bash
pytest
```

- `tests/unit/` – jedes Pipeline-Modul einzeln getestet (keine echten API-Calls)
- `tests/integration/test_agent_pipeline.py` – kompletter Pipeline-Lauf mit Fake-Collector und Fake-LLM-Client, prüft insbesondere, dass fehlende Retention-Daten nicht erfunden werden

## Ausblick

Diese Version deckt einen vollständigen, aber bewusst einfachen Research-Workflow ab (Prompt 1 + 2 aus [`docs/Prompts.docx`](docs/Prompts.docx)). Nicht enthalten, aber als nächste Ausbaustufe vorgesehen (Prompt 3):

- robustere Bias-Behandlung (Vergleich mit Kontrollgruppen, Konfidenzintervalle)
- agentische Fähigkeiten (Agent entscheidet selbst, ob Stichprobe/Daten ausreichen)
- ein dedizierter Evaluation-Agent, der Report-Aussagen gegen die Rohdaten prüft
