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

---

## Task 3: Start-Button auf dem Desktop ✅

**Hinzugefügt:** 30.10.2026
**Ziel:** Ein Doppelklick auf ein Desktop-Symbol startet den Server des Control Panels und öffnet es im Browser, ganz ohne Terminal.

### Checkpoints

- [x] **CP1 – Startskript:** `start_control_panel.bat` im Projektordner. Läuft der Server schon, wird nur der Browser geöffnet. Sonst wird der Server in einem minimierten Fenster gestartet (Fenster schließen = Server beenden), das Skript wartet, bis er erreichbar ist, und öffnet dann den Browser.
- [x] **CP2 – Symbol:** eigenes Icon für die Verknüpfung (`dashboard/icon.ico`).
- [x] **CP3 – Desktop-Verknüpfung:** „Shorts Analytics“ auf dem Desktop, zeigt auf das Startskript.
- [x] **CP4 – Test:** Start aus kaltem Zustand und Start bei bereits laufendem Server geprüft.
- [x] **CP5 – Doku:** README um den Start per Doppelklick ergänzen.

---

## Task 4: Alte Läufe löschen ✅

**Hinzugefügt:** 30.10.2026
**Ziel:** Auf der Seite „Alle Läufe“ einen oder mehrere Läufe auswählen und mit allen Dateien löschen können.

### Checkpoints

- [x] **CP1 – Löschfunktion:** `run_control.delete_run()` löscht den Lauf-Ordner. Laufende Läufe werden nicht gelöscht, und es werden nur Ordner innerhalb von `data/runs/` angefasst.
- [x] **CP2 – Oberfläche:** Mehrfachauswahl in der Tabelle, Button „Löschen“ mit Sicherheitsabfrage (Anzahl und Lauf-IDs). Laufende Läufe sind ausgenommen, mit Hinweis.
- [x] **CP3 – Tests:** Löschen, Schutz laufender Läufe, Schutz vor Pfaden außerhalb von `data/runs/`.
- [x] **CP4 – Prüfung im Browser:** Löschen mit einem Testlauf durchgespielt (keine echten Läufe gelöscht).
- [x] **CP5 – Doku:** README ergänzen.

---

## Task 5: Ergebnisse-Seite übersichtlicher ✅

**Hinzugefügt:** 31.10.2026
**Ziel:** Die Seite „Ergebnisse“ so aufteilen, dass man (auf einem normalen Bildschirm) nicht scrollen muss: Inhalte auf Tabs verteilen, Diagramm und Tabelle nebeneinander, Zahlen lesbar formatieren.

### Checkpoints

- [x] **CP1 – Aufbau:** Kompakter Kopf (Lauf, Datum, Modell) und Tabs ganz oben: Überblick · Themen · Hooks · Formate · Videolänge · Rankings · Muster · Empfehlungen · Daten · Lauf-Details.
- [x] **CP2 – Überblick-Tab:** KPI-Kacheln, Executive Summary und die wichtigsten Muster auf einen Blick.
- [x] **CP3 – Gruppen-Tabs:** Diagramm und Tabelle nebeneinander mit begrenzter Höhe. Zahlen lesbar („2,76 Mrd.“ statt „2762270389.6667“), leere Werte als „–“, Retention-Spalten ausblenden, wenn keine Retention-Daten vorliegen.
- [x] **CP4 – Seitenleiste entlasten:** Lauf-Details (Kategorien, Suchbegriffe, Datenquellen, Fehler) in einen eigenen Tab verschieben. In der Seitenleiste bleibt nur die Lauf-Auswahl.
- [x] **CP5 – Prüfung im Browser:** Alle Tabs mit Screenshots kontrolliert, bei 1280×800 ohne Scrollen.
- [x] **CP6 – Tests & Doku:** Bestehende Tests grün, README aktualisiert.

---

## Task 6: Neues Design mit Tafeln (Karten) ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Auf dem Bildschirm des Anwenders (große Darstellung/Zoom) war der Überblick trotz Tabs zu textlastig und musste gescrollt werden.
**Ziel:** Ein modernes, ruhiges Design mit Tafeln: Kennzahlen als Kacheln, Erkenntnisse als kurze Karten, lange Texte nur auf Wunsch.

### Checkpoints

- [x] **CP1 – Grund-Design:** Einheitliches Farbschema (Akzentfarbe wie die Projekt-Webseite), heller Hintergrund, weiße Karten mit runden Ecken und leichtem Schatten, Tabs als Reiter-Leiste. „Deploy“-Menü ausgeblendet.
- [x] **CP2 – Überblick als Tafeln:** Kennzahl-Kacheln · drei Erkenntnis-Karten (Top-Thema, bester Hook, beste Videolänge) · Karte „Kernaussage“ (kurz, ganzer Text auf Klick) · Karte „Wichtigste Muster“ mit Konfidenz-Abzeichen · Karte „Top-Empfehlung“.
- [x] **CP3 – Übrige Tabs als Karten:** Diagramm und Tabelle jeweils in einer Karte, Muster und Empfehlungen als Karten, Lauf-Details als Karten.
- [x] **CP4 – Prüfung im Browser:** Screenshots bei normaler und bei vergrößerter Darstellung (ca. 1280×650 sichtbare Fläche), Überblick ohne Scrollen.
- [x] **CP5 – Tests & Doku:** Tests grün, README aktualisiert.
- [x] **CP6 – „Neuer Lauf“ verständlicher:** Verbrauch als drei Kacheln (Videos · YouTube kostenlos mit Anteil am Tageslimit · KI-Anfragen kostenpflichtig) plus aufklappbare Erklärung „Was bedeutet das?“ (nachgetragen nach Rückmeldung am 31.10.2026).

---

## Task 7: Fortschritt-Seite übersichtlicher ✅

**Hinzugefügt:** 31.10.2026
**Ziel:** Die Seite „Fortschritt“ im selben Karten-Design wie die Ergebnisse, kompakt und ohne Scrollen.

### Checkpoints

- [x] **CP1 – Kopf & Lauf-Auswahl:** Kopfzeile mit Status-Abzeichen (läuft / fertig / abgebrochen / fehlgeschlagen, je mit Symbol), Datum und Themen als Abzeichen. Die Lauf-Auswahl wandert in die Seitenleiste (wie bei „Ergebnisse“).
- [x] **CP2 – Status-Karte:** Fortschrittsbalken mit Prozent, aktueller Schritt mit Detail (z. B. „Video 3 von 10“), Kacheln für Laufzeit, Schritt und Videos pro Suchbegriff.
- [x] **CP3 – Schritte als Leiste:** Die 9 Pipeline-Schritte nebeneinander als Stepper (erledigt · aktiv · offen · abgebrochen/fehlgeschlagen) statt einer langen Liste.
- [x] **CP4 – Aktionen:** Anhalten / Sofort beenden / Ergebnisse ansehen in einer Zeile, Log aufklappbar.
- [x] **CP5 – Prüfung:** Laufender, fertiger, abgebrochener und fehlgeschlagener Zustand im Browser geprüft (simulierte Läufe, danach entfernt), ohne Scrollen bei 1280×630.
- [x] **CP6 – Abstände der Buttons:** Mehr Luft zwischen Kacheln und Buttons (auch auf „Neuer Lauf“), Log-Button schmaler als „📄 Log anzeigen“ (nachgetragen nach Rückmeldung am 31.10.2026).

---

## Task 8: Überblick mit mehr Luft und farbigen Akzenten ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Die Tafeln stehen zu eng beieinander und sehen alle gleich aus. Wichtiges soll hervorstechen.

### Checkpoints

- [x] **CP1 – Abstände:** Mehr Abstand zwischen und innerhalb der Tafeln.
- [x] **CP2 – Rangfolge durch Farbe:** Kennzahl-Kacheln mit farbigem Symbol; die drei Erkenntnis-Karten (Top-Thema, bester Hook, beste Videolänge) farbig hinterlegt mit Akzentlinie; Kernaussage mit Akzentstreifen; Top-Empfehlung als eigene, dunkle Karte, die sofort ins Auge fällt.
- [x] **CP3 – Prüfung im Browser:** Screenshots bei 1280×800 und 1280×700, Lesbarkeit (Kontrast) geprüft.

---

## Task 9: Überblick vereinfachen ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Trotz Farben und Abständen wirkte der Überblick überladen – zu viele Tafeln auf zu wenig Raum.
**Ansatz:** Weniger Elemente statt kleinerer Abstände.

### Checkpoints

- [x] **CP1 – Kennzahlen in die Kopfzeile:** Die 5 Kennzahl-Kacheln entfallen; geprüft / ausgewertet / verworfen erscheinen als Abzeichen in der Kopfzeile (Retention steht dort bereits als Warnung).
- [x] **CP2 – Zwei Bereiche mit Überschrift:** „Die wichtigsten Erkenntnisse“ (drei farbige Karten) und „Was heißt das für dich?“ (Top-Empfehlung + Kernaussage), großzügige Abstände.
- [x] **CP3 – „Wichtigste Muster“ nur im Reiter „Muster“.**
- [x] **CP4 – Prüfung im Browser:** bei 1280×800 und 1280×700, kein Scrollen.

---

## Task 10: Erkenntnis-Karten verständlich machen ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Auf den Karten war unklar, was „wenige Videos“ und „Ø 2,76 Mrd. Aufrufe · 3 Videos“ bedeuten.

### Checkpoints

- [x] **CP1 – Belastbarkeit erklären:** Abzeichen „○ nur Tendenz“ / „✓ belastbar“ mit Erklärung beim Darüberfahren (genaue Anzahl, Mindestgröße 8) und einem Satz unter den Karten.
- [x] **CP2 – Lesbare Namen:** Hook-Typen und Längen in verständlichem Deutsch („Versprechen eines Ergebnisses“, „0–15 Sekunden“) – auch in Tabellen und Diagrammen.
- [x] **CP3 – Karten erklären sich selbst:** je Karte ein kurzer Satz, was die Gruppe bedeutet, die Kennzahl groß („2,76 Mrd.“) und darunter in Worten „Aufrufe pro Video im Schnitt, aus 3 Videos“.
- [x] **CP4 – Prüfung:** Überblick ohne Scrollen bei 1280×800 und 1280×700, alle Tests grün.

---

## Task 11: Karte „Kernaussage“ aufräumen ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Die „…“ am Textende überlappten den Button, der Text brach mitten im Satz ab.

- [x] **CP1 – Ganze Sätze:** Die Karte zeigt nur ganze Sätze (so viele, wie passen), ohne „…“.
- [x] **CP2 – Abstand:** Text und Button überlappen nicht mehr.
- [x] **CP3 – Dezenter Link:** „Ganze Zusammenfassung lesen“ als schlichter Textlink mit Symbol statt Button-Kasten.
- [x] **CP4 – Prüfung:** ohne Scrollen bei 1280×800 und 1280×700.

---

## Task 12: Gruppen-Reiter verständlich machen (Themen · Hooks · Formate · Videolänge) ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Diagramm und Tabelle zeigten dasselbe doppelt, unterschiedlich sortiert und mit Fachbegriffen (Ø, Median, n, ○); die Diagramm-Werkzeugleiste überdeckte den Titel, die Tabelle war abgeschnitten.

### Checkpoints

- [x] **CP1 – Leitfrage:** Jeder Reiter beginnt mit einer Frage in Alltagssprache und einem Satz, was die Balken zeigen.
- [x] **CP2 – Eine Rangliste:** Platz · Name (bei Hooks mit kurzer Erklärung) · Balken · „2,76 Mrd. Aufrufe pro Video · 3 Videos · ○ nur Tendenz“ – sortiert vom höchsten Wert.
- [x] **CP3 – Genaue Zahlen aufklappbar:** Tabelle mit verständlichen Spaltennamen (Durchschnitt und mittlerer Wert erklärt).
- [x] **CP4 – Diagramm-Werkzeugleiste ausblenden** (auch im Reiter „Daten“).
- [x] **CP5 – Prüfung im Browser:** alle vier Reiter, ohne Scrollen bei 1280×700; Tests grün.
- [x] **CP6 – Überlappung behoben:** „Genaue Zahlen“ sitzt oben rechts neben der Frage statt unter der Liste; Streamlits negativer Abstand nach Textblöcken aufgehoben; lange Listen werden unten sanft ausgeblendet statt hart abgeschnitten (nachgetragen nach Rückmeldung am 31.10.2026).

---

## Task 13: Begriff „Hook“ erklären ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Unklar, was „Hooks“ sind.

- [x] **CP1 – Erklärung im Reiter:** Hinweisbox oben: Hook = Einstieg, die ersten 1–3 Sekunden; entscheidet über Weiterschauen oder Wegwischen; die KI ordnet jedes Video einem von 9 Einstiegs-Typen zu – nur anhand von Titel und Beschreibung.
- [x] **CP2 – Verständliche Namen:** Reiter „Hooks“ → „Einstieg“, Karte im Überblick „Bester Hook“ → „Bester Einstieg“.
- [x] **CP3 – Prüfung:** Reiter-Leiste passt vollständig, kein Scrollen bei 1280×700, Tests grün.

---

## Task 14: Reiter „Empfehlungen“ – Überschriften mit Abstand ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Die Überschriften „Konkrete Handlungsempfehlungen“ und „Einschränkungen der Daten“ klebten am Text.

- [x] **CP1 – Abstand:** Überschrift mit Abstand und feiner Trennlinie zum Text.
- [x] **CP2 – Überschrift bleibt sichtbar:** Beim Scrollen innerhalb der Karte bleibt die Überschrift oben stehen.
- [x] **CP3 – Prüfung im Browser:** vor und nach dem Scrollen kontrolliert, Tests grün.

---

## Task 15: „Rankings“ → „Top 3“ ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Der Reiter „Rankings“ war eine trockene Tabelle und wiederholte nur „Themen“ und „Formate“.

### Checkpoints

- [x] **CP1 – Neuer Inhalt:** Top 3 aus allen vier Bereichen (Themen · Einstieg · Formate · Videolänge) auf einen Blick, als 2×2-Karten.
- [x] **CP2 – Siegertreppchen:** Plätze 1–3 mit Medaille (Nummer + Farbe), kleiner Balken im Vergleich zum Sieger, Wert in Worten, Anzahl Videos und Belastbarkeit.
- [x] **CP3 – Reiter umbenennen:** „Rankings“ → „Top 3“ (kurz, damit die Reiter-Leiste vollständig passt).
- [x] **CP4 – Prüfung im Browser:** ohne Scrollen bei 1280×700, Tests grün.

---

## Task 16: Reiter „Muster“ aufwerten ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Alle Muster sahen gleich aus; echte Erkenntnisse und Hinweise zur Datenlage („Keine Aussage möglich …“) standen gleichrangig nebeneinander; Fachtexte (n=2, versprechen_eines_ergebnisses, Konfidenz).

### Checkpoints

- [x] **CP1 – Einleitung:** kurz erklären, was Muster sind.
- [x] **CP2 – Trennen:** Erkenntnisse (hervorgehobene, nummerierte Karten) und Hinweise zur Datenlage (gelbe Hinweis-Karte) getrennt darstellen.
- [x] **CP3 – Verständliche Sprache:** „Sicherheit ●○○ niedrig“ statt „Konfidenz“, „2 Videos“ statt „n=2“, lesbare Einstiegs-Namen, „Worauf beruht das?“ statt „Beleg“.
- [x] **CP4 – Prüfung im Browser:** ohne Scrollen bei 1280×700, Tests grün.

## Task 17: Medaillen im Reiter „Top 3“ ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Die Platz-Kreise (blasses Gelb, Grau, Rosa) wirkten verwaschen und nicht wie Gold, Silber, Bronze.

### Checkpoints

- [x] **CP1 – Farben:** volle Medaillen in Gold, Silber und Bronze mit leichtem Verlauf und Schatten.
- [x] **CP2 – Lesbarkeit:** dunkle Ziffern, Kontrast mindestens 4.5:1 auf jeder Medaille.
- [x] **CP3 – Prüfung im Browser:** Screenshot geprüft.

## Task 18: Überschriften im Reiter „Empfehlungen“ fixieren ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Beim Scrollen schien der Text durch die Überschrift hindurch; Überschrift und Text standen zu eng.

### Checkpoints

- [x] **CP1 – Feste Überschrift:** Überschrift steht deckend oben in der Karte, nur der Textbereich darunter scrollt.
- [x] **CP2 – Abstand:** mehr Luft zwischen Überschrift-Linie und erstem Absatz.
- [x] **CP3 – Prüfung im Browser:** gescrollt und ungescrollt bei 1280×800 und 1280×700, Seite selbst scrollt nicht.
- [x] **CP4 – Nachbesserung:** Textbereich begann wegen Streamlits negativem Abstand 8 px oberhalb der Linie und rutschte beim Scrollen hinein. Jetzt beginnt er nachgemessen unterhalb der Linie, auch bei 150 % Zoom.

## Task 19: Wichtiges in Empfehlungen und Einschränkungen hervorheben ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Lange Fließtexte ohne Hervorhebung; wichtige Namen, Zahlen und Vorbehalte gingen unter.

### Checkpoints

- [x] **CP1 – Hervorhebungen:** Tu-Wort jeder Empfehlung rot, Namen (Themen, Formate, Einstiege) als blaue Marker, Zahlen fett, Vorbehalte („nicht statistisch belastbar“, „Survivorship Bias“ …) gelb hinterlegt – sparsam.
- [x] **CP2 – Gliederung:** Empfehlungen mit roten Nummern-Kreisen, Einschränkungen mit gelbem „!“, mehr Abstand zwischen den Punkten.
- [x] **CP3 – Lesbarkeit:** Umlaute in Agenten-Texten für die Anzeige korrigiert (ueber → über …), „Konfidenz“ → „Sicherheit“.
- [x] **CP4 – Prüfung im Browser:** 1280×800 und 1280×700, Tests grün.

## Task 20: Reiter „Daten“ verständlich machen ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Diagramm „Datenvollständigkeit“ mit Prozentachse und Fachbegriffen war nicht verständlich; unklar, was die Downloads sind.

### Checkpoints

- [x] **CP1 – Frage statt Fachbegriff:** Überschrift „Welche Angaben gab es zu den N Videos?“ mit einem erklärenden Satz.
- [x] **CP2 – Liste statt Diagramm:** je Angabe Name, was sie bedeutet, woher sie kommt, Status (✓ vollständig / ◐ teilweise / ✗ fehlt) und „X von N Videos“; Fehlendes zuerst.
- [x] **CP3 – Bedeutung:** gelbe Karte „Was heißt das für die Ergebnisse?“ aus den Daten abgeleitet (z. B. keine Zuschauerbindung → alle Reiter vergleichen Aufrufe).
- [x] **CP4 – Downloads erklärt:** „Tabelle aller Videos (CSV, z. B. für Excel)“, „Ganzer Bericht als Text“, Tabellenansicht als Aufklapp-Fenster.
- [x] **CP5 – Prüfung im Browser:** 1280×800 und 1280×700, Tests grün.

## Task 21: Excel-Export statt Roh-CSV ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Die CSV war in Excel unlesbar: Zahlen als `{'value': …, 'source': …}`, lange Beschreibungen, IDs, kaputte Sonderzeichen, keine Spaltenbreiten.

### Checkpoints

- [x] **CP1 – Aufgeräumte Tabelle:** ein Video pro Zeile, sortiert nach Aufrufen, deutsche Spaltennamen, echte Zahlen, Titel ohne Hashtags, klickbarer Link statt IDs, KI-Einordnung (Thema, Unterthema, Einstieg, Format, Begründung); leere Spalten (z. B. Zuschauerbindung) entfallen.
- [x] **CP2 – Excel-Formatierung:** Kopfzeile dunkel und fixiert, Tabelle mit Filter und Streifen, Tausenderpunkte, Datum, Prozent, passende Spaltenbreiten, Umbruch bei langen Texten.
- [x] **CP3 – Zusatzblätter:** „Auswertung“ (Kennzahlen je Thema / Einstieg / Format / Länge) und „Erklärung“ (Bedeutung jeder Spalte).
- [x] **CP4 – Dashboard:** Button „📊 Excel-Tabelle aller Videos“; Tabellenansicht als großes Fenster mit derselben aufgeräumten Tabelle.
- [x] **CP5 – Tests:** 4 neue Tests (`tests/unit/test_excel_export.py`), Download im Browser geprüft.

## Task 22: Reiter „Lauf-Details“ aufwerten ✅

**Hinzugefügt:** 31.10.2026
**Anlass:** Technische Liste (Lauf-ID, max_results_per_query, „public“) ohne Erklärung, wenig ansprechend.

### Checkpoints

- [x] **CP1 – Ablauf in Zahlen:** Kacheln „Gefunden“, „Ausgewertet“, „Aussortiert“, „Dauer“ mit Symbol und kurzer Erklärung.
- [x] **CP2 – Verständliche Karten:** „Wonach gesucht wurde“ (Kategorie, Suchbegriffe als Marker, „bis zu 5 Videos je Suchbegriff“), „Womit ausgewertet wurde“ (Datenquelle in Worten, KI-Modell mit Aufgabe, Lauf-Nummer klein).
- [x] **CP3 – Zustand:** grüne Meldung „Ohne Fehler durchgelaufen“ bzw. Fehlerliste.
- [x] **CP4 – Prüfung im Browser:** 1280×800 und 1280×700 ohne Scrollen, Tests grün.
- [x] **CP5 – Layout korrigiert:** die drei Karten als gemeinsames Raster – gleich hoch, bündig mit den Kacheln, gleiche Abstände, Fußzeile mit Trennlinie; Text klebt nicht mehr am unteren Kartenrand.
