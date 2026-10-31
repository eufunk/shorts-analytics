# shorts-analytics

Datenbasierte Analyse von YouTube Shorts zur Untersuchung von Zuschauerbindung, Durchschauquote, Videolänge, Hooks, Themen und Erfolgsfaktoren.

📄 **Projekt-Webseite:** [`website/index.html`](website/index.html) – Zweck, Nutzen, Zielgruppe, erledigte und geplante Arbeiten auf einen Blick (im Browser öffnen).

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
- `status.json` – Zustand und Fortschritt des Laufs (für das Control Panel)

## Control Panel (Bedienoberfläche)

Statt über das Terminal lässt sich der Agent bequem im Browser bedienen. Das Control Panel ([`dashboard/app.py`](dashboard/app.py)) hat vier Seiten:

- **Neuer Lauf** – Themen und Anzahl Videos wählen, geschätzten Verbrauch (YouTube-Kontingent, KI-Aufrufe) ansehen, Lauf starten
- **Fortschritt** – Live-Anzeige (alle 2 Sekunden): Status-Abzeichen, Fortschrittsbalken mit aktuellem Schritt („Video 3 von 10“), die 9 Pipeline-Schritte als Leiste, Laufzeit; Lauf anhalten oder im Notfall sofort beenden, Ausgabe des Agenten (`log.txt`). Direktlink auf einen Lauf: `/fortschritt?lauf=<Lauf-ID>`
- **Ergebnisse** – ein fertiger Report als Tafeln (Karten), aufgeteilt auf Reiter, die ohne Scrollen auf den Bildschirm passen: Überblick („Die wichtigsten Erkenntnisse“: Top-Thema / bester Einstieg / beste Länge; „Was heißt das für dich?“: Top-Empfehlung und Kernaussage; Kennzahlen als Abzeichen in der Kopfzeile) · Themen · Einstieg (Hook) · Formate · Videolänge (je eine Leitfrage und eine Rangliste mit Balken und Werten in Worten, genaue Zahlen aufklappbar) · Top 3 (Siegertreppchen der drei Besten aus Themen, Einstieg, Formaten und Videolänge) · Muster · Empfehlungen · Daten (welche Angaben es zu den Videos gab, Excel-Download mit den Blättern „Videos“, „Auswertung“ und „Erklärung“, Tabellenansicht aller Videos) · Lauf-Details
- **Alle Läufe** – Übersicht aller Läufe mit Status (läuft / fertig / abgebrochen / fehlgeschlagen); einen oder mehrere Läufe auswählen und nach Sicherheitsabfrage mit allen Dateien löschen (laufende Läufe sind ausgenommen)

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

Das Erscheinungsbild (Farben, Akzentfarbe wie die Projekt-Webseite) ist in [`.streamlit/config.toml`](.streamlit/config.toml) festgelegt, die Karten-Gestaltung als CSS in `dashboard/app.py`.

**Start per Doppelklick (Windows):** [`start_control_panel.bat`](start_control_panel.bat) startet den Server auf Port 8502 in einem minimierten Fenster und öffnet das Control Panel im Browser. Läuft der Server schon, wird nur der Browser geöffnet. Fenster „Shorts Analytics Server“ schließen = Server beenden. Eine Desktop-Verknüpfung mit eigenem Symbol ([`dashboard/icon.ico`](dashboard/icon.ico)) lässt sich auf das Skript anlegen.

So funktioniert es: Ein gestarteter Lauf arbeitet als eigener Hintergrundprozess (über die CLI mit `--run-id`), er läuft also weiter, auch wenn der Browser-Tab geschlossen wird. Fortschritt und Zustand stehen in `data/runs/<run_id>/status.json`. „Lauf anhalten“ legt die Datei `stop.requested` an; der Agent hört dann nach dem aktuellen Video bzw. der aktuellen Suchanfrage sauber auf und speichert keinen Report. Es läuft immer nur ein Lauf gleichzeitig. Die Logik dafür liegt in [`run_status.py`](src/shorts_analytics/run_status.py) und [`run_control.py`](src/shorts_analytics/run_control.py).

Die API-Keys in `.env` werden auch für Läufe aus dem Control Panel benötigt; fehlen sie, zeigt die Seite „Neuer Lauf“ einen Hinweis.

## Eigene YouTube-Analytics-Daten (Ebene 2, optional)

Retention-Kennzahlen ("stayed to watch", durchschnittlich gesehener Prozentsatz) sind nur für den eigenen Kanal über die YouTube Analytics API (OAuth) verfügbar. Die Schnittstelle dafür ist in [`src/shorts_analytics/collectors/youtube_studio.py`](src/shorts_analytics/collectors/youtube_studio.py) vorbereitet (`OwnAnalyticsCollector`-Protokoll); die OAuth-Anbindung selbst ist noch nicht implementiert, da sie eine manuelle Google-Cloud-Einrichtung voraussetzt. Ohne diese Anbindung markiert der Agent alle Retention-Felder korrekt als „nicht verfügbar“, statt sie aus Aufrufen/Likes zu schätzen.

## Tests

```bash
pytest
```

- `tests/unit/` – jedes Pipeline-Modul einzeln getestet (keine echten API-Calls)
- `tests/integration/test_agent_pipeline.py` – kompletter Pipeline-Lauf mit Fake-Collector und Fake-LLM-Client, prüft insbesondere, dass fehlende Retention-Daten nicht erfunden werden
- `tests/integration/test_agent_progress.py` – Fortschrittsmeldungen und Anhalten eines Laufs

## Ausblick

Diese Version deckt einen vollständigen, aber bewusst einfachen Research-Workflow ab (Prompt 1 + 2 aus [`docs/Prompts.docx`](docs/Prompts.docx)). Nicht enthalten, aber als nächste Ausbaustufe vorgesehen (Prompt 3):

- robustere Bias-Behandlung (Vergleich mit Kontrollgruppen, Konfidenzintervalle)
- agentische Fähigkeiten (Agent entscheidet selbst, ob Stichprobe/Daten ausreichen)
- ein dedizierter Evaluation-Agent, der Report-Aussagen gegen die Rohdaten prüft
