# Plan: shorts-analytics

**Erstellt:** 30.10.2026

---

## Task 1: Projekt-Webseite ✅

**Ziel:** Eine Webseite, die erklärt, wofür das Projekt erstellt wurde, welchen Nutzen es hat, für wen es gedacht ist, was erledigt ist und was geplant ist.

- [x] **CP1 – Bestandsaufnahme:** README, Spezifikation (`docs/YouTube_Shorts_Research_Analyse.docx`), Projektdokumentation und Code-Struktur gesichtet
- [x] **CP2 – Status verifizieren:** Testsuite ausgeführt, damit „erledigt“ auf der Webseite belegt ist
- [x] **CP3 – Inhalt & Struktur festgelegt:** Abschnitte Zweck · Nutzen · Zielgruppe · Funktionsweise · Erledigt · Geplant
- [x] **CP4 – Webseite gebaut:** `website/index.html` (eigenständig, ohne externe Abhängigkeiten, responsiv, Hell/Dunkel-Modus)
- [x] **CP5 – Prüfung:** Seite auf Inhalt, Links und Darstellung geprüft
- [x] **CP6 – Einbindung:** Link zur Webseite im README ergänzt

---

## Task 2: Bedienoberfläche (Control Panel) für den Agenten ✅

**Hinzugefügt:** 30.10.2026
**Ziel:** Anwender sollen den Agenten ohne Terminal bequem im Browser bedienen können: starten, stoppen, den Fortschritt beobachten und Ergebnisse ansehen.
**Nicht enthalten (vorerst):** Ergebnisse beurteilen/bewerten. Das wurde am 30.10.2026 bewusst zurückgestellt.

**Ausgangslage:**
- Der Agent wird heute nur per Befehl im Terminal gestartet (`shorts-analytics`).
- `ResearchAgent.run()` ([src/shorts_analytics/agent.py](../src/shorts_analytics/agent.py)) läuft ohne Rückmeldung zum Fortschritt durch und lässt sich nicht kontrolliert anhalten.
- Das Streamlit-Dashboard ([dashboard/app.py](../dashboard/app.py)) zeigt nur fertige Reports an.

**Ansatz:** Das bestehende Streamlit-Dashboard wird zum Control Panel ausgebaut, statt eine zweite Oberfläche zu bauen. Der Agent läuft als eigener Hintergrundprozess und tauscht sich mit der Oberfläche über Dateien im Lauf-Ordner aus (`status.json` für den Fortschritt, `stop.requested` für den Stopp-Wunsch, `log.txt` für die Ausgabe). Dadurch läuft ein Lauf weiter, auch wenn der Browser-Tab geschlossen wird.

**Benötigt:** `YOUTUBE_API_KEY` (YouTube Data API, kostenlos mit Tageskontingent) und `ANTHROPIC_API_KEY` (Claude, kostenpflichtig je Nutzung) in `.env`.

### Checkpoints

- [x] **CP1 – Anforderungen festlegen:** Start mit Themenauswahl und Anzahl Videos, Stopp, Live-Fortschritt, Ergebnisse, Übersicht aller Läufe. Kein „Beurteilen“. Es läuft immer nur ein Lauf gleichzeitig.
- [x] **CP2 – Fortschrittsmeldungen im Agenten:** `ResearchAgent.run()` meldet jeden der 9 Pipeline-Schritte (inkl. „Video x von y“) über einen Callback. Ein neues Modul `run_status.py` schreibt den Stand in `data/runs/<run_id>/status.json`.
- [x] **CP3 – Start & Stopp im Hintergrund:** Der Lauf startet als eigener Prozess (über die CLI mit `--run-id`). Stopp-Wunsch über eine Datei: Der Agent hört nach dem aktuellen Video bzw. der aktuellen Suchanfrage sauber auf und speichert den Lauf als „abgebrochen“. Zusätzlich gibt es „Sofort beenden“ als Notfalloption.
- [x] **CP4 – Seite „Neuer Lauf“:** Themenauswahl, Anzahl Videos, Schätzung von YouTube-Kontingent und KI-Aufrufen, Start-Button. Ein Hinweis erscheint, wenn API-Keys fehlen oder schon ein Lauf aktiv ist.
- [x] **CP5 – Seite „Fortschritt“:** Live-Anzeige (alle 2 Sekunden) mit Fortschrittsbalken, Liste der 9 Schritte mit Status, aktuellem Detail, Laufzeit, Stopp-Button und Log-Ausgabe bei Fehlern.
- [x] **CP6 – Seite „Ergebnisse“:** Die bestehende Report-Ansicht wird übernommen. Nach Abschluss eines Laufs führt ein Button direkt dorthin.
- [x] **CP7 – Seite „Alle Läufe“:** Tabelle aller Läufe mit Status (läuft / fertig / abgebrochen / fehlgeschlagen), Datum, Themen, Videos und Dauer. Ältere Läufe ohne Statusdatei werden ebenfalls angezeigt.
- [x] **CP8 – Tests:** Tests für Fortschrittsmeldungen, Stopp, Statusdateien und Lauf-Übersicht. Die bestehenden 33 Tests bestehen weiterhin.
- [x] **CP9 – Prüfung im Browser:** Das Control Panel starten, alle Seiten durchklicken, Screenshot-Kontrolle.
- [x] **CP10 – Doku & Webseite aktualisieren:** README (Start über die Oberfläche) und Projekt-Webseite (Einleitung, „Erledigt“) anpassen.
