"""Streamlit-Control-Panel: Agenten-Laeufe starten, beobachten und auswerten.

Seiten:
- Neuer Lauf   - Themen und Stichprobengroesse waehlen, Lauf starten
- Fortschritt  - Live-Anzeige der 9 Pipeline-Schritte, Lauf anhalten
- Ergebnisse   - Visualisierung eines fertigen Reports
- Alle Laeufe  - Uebersicht aller Laeufe mit Status

Ein Lauf wird als eigener Hintergrundprozess ueber die CLI gestartet
(siehe shorts_analytics/run_control.py). Das Panel liest den Fortschritt aus
data/runs/<run_id>/status.json und die Ergebnisse aus den dort abgelegten
Artefakten; es ruft selbst keine YouTube- oder KI-Schnittstelle auf.

Start: streamlit run dashboard/app.py
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from shorts_analytics import config, run_control
from shorts_analytics.models import ClassificationResult, GroupStats, PatternInsight, Report
from shorts_analytics.reporting import excel_export
from shorts_analytics.run_status import (
    LOG_FILE,
    PIPELINE_STAGES,
    STATE_LABELS,
    RunState,
    request_stop,
    stop_requested,
)

MIN_RELIABLE_SAMPLE_SIZE = 8  # nur fuer die Legenden-Beschriftung, siehe config.py

CONFIDENCE_ICON = {"hoch": "🟢", "mittel": "🟡", "niedrig": "⚪"}
# Konfidenz-Abzeichen: Symbol + Text + Farbe (nie Farbe allein)
CONFIDENCE_BADGE = {"hoch": ("good", "✓ hoch"), "mittel": ("warn", "◐ mittel"), "niedrig": ("neutral", "○ niedrig")}

ACCENT = "#c4302b"

# Karten-Design: weisse Tafeln mit runden Ecken auf hellem Hintergrund. Container mit
# key="card_..." werden ueber ihre CSS-Klasse "st-key-card_..." als Karte gestaltet.
APP_CSS = """
<style>
[data-testid='stMainBlockContainer'], .block-container {padding-top: 2rem; padding-bottom: 1rem;}
[class*='st-key-card'] {
  background: #ffffff; border: 1px solid rgba(11,11,11,0.08); border-radius: 16px;
  padding: 16px 20px; gap: 0.5rem; box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 2px 6px rgba(16,24,40,0.05);
}
.stTabs [role='tablist'] {
  gap: 2px; background: #ffffff; padding: 4px; border-radius: 12px; border: 1px solid rgba(11,11,11,0.08);
  width: fit-content; max-width: 100%; box-shadow: none;
}
.stTabs [data-testid='stTab'] {height: auto; padding: 5px 12px; border-radius: 9px; border: none;}
.stTabs [data-testid='stTab'][aria-selected='true'] {background: #fbe9e8;}
.stTabs [data-testid='stTab'][aria-selected='true'] p {color: #c4302b; font-weight: 600;}
.stTabs [data-testid='stTab']:hover {background: #f5f5f2;}

.page-head {display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-bottom: 2px;}
.page-head .title {font-size: 1.5rem; font-weight: 700; color: #0b0b0b; margin-right: 6px;}
.chip {display: inline-block; font-size: 0.78rem; color: #52514e; background: #ffffff;
  border: 1px solid rgba(11,11,11,0.10); border-radius: 999px; padding: 2px 10px;}
.badge {display: inline-block; font-size: 0.74rem; font-weight: 600; padding: 2px 9px; border-radius: 999px; white-space: nowrap;}
.badge.good {background: #e3f3ea; color: #006300;}
.badge.warn {background: #fdf1d8; color: #7a4b00;}
.badge.neutral {background: #efefec; color: #52514e;}

.tile-grid {display: grid; gap: 16px; margin-bottom: 6px;}
.tile-grid.kpi {grid-template-columns: repeat(5, minmax(0, 1fr));}
.tile-grid.insight {grid-template-columns: repeat(3, minmax(0, 1fr));}
/* Kacheln, auf die Buttons oder Aufklapp-Bereiche folgen: mehr Luft darunter */
.tile-grid.spaced {margin-bottom: 26px;}
.tile {background: #ffffff; border: 1px solid rgba(11,11,11,0.08); border-radius: 16px; padding: 14px 18px;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 2px 6px rgba(16,24,40,0.05); min-width: 0;}
.tile .label {font-size: 0.8rem; color: #52514e;}
.tile .value {font-size: 1.5rem; font-weight: 600; color: #0b0b0b; line-height: 1.2;}
.tile .sub {font-size: 0.75rem; color: #898781; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.tile.insight .head {display: flex; justify-content: space-between; align-items: center; gap: 8px;}
.tile.insight .eyebrow {font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: #c4302b;}
.tile.insight .value {font-size: 1.1rem; margin: 2px 0 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.tile.insight .sub {font-size: 0.8rem; color: #52514e;}

.card-title {font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: #52514e; margin-bottom: 6px;}
.card-text {font-size: 0.95rem; color: #0b0b0b; line-height: 1.5;}
.pattern-row {display: flex; justify-content: space-between; gap: 10px; align-items: baseline; padding: 4px 0;
  border-bottom: 1px solid #efefec; font-size: 0.92rem;}
.pattern-row:last-child {border-bottom: none;}
.muted {color: #898781; font-size: 0.8rem;}

/* Kennzahl-Kacheln: farbiges Symbol links (Dekoration, die Bedeutung steht im Text) */
.tile.kpi-tile {position: relative; padding-right: 52px;}
.kpi-icon {position: absolute; top: 12px; right: 12px; width: 34px; height: 34px; border-radius: 10px;
  display: grid; place-items: center; font-size: 1rem;}
.kpi-icon.blue {background: #e8f1fc;} .kpi-icon.green {background: #e3f3ea;} .kpi-icon.gray {background: #efefec;}
.kpi-icon.amber {background: #fdf1d8;} .kpi-icon.purple {background: #f0eafb;}
.kpi-body {min-width: 0;}

/* Erkenntnis-Karten: farbig hinterlegt mit Akzentlinie oben */
.tile.insight {border-top: 4px solid var(--c); background: var(--bg);}
.tile.insight .eyebrow {color: var(--c);}
.tile.insight.red {--c: #c4302b; --bg: #fdf3f2;}
.tile.insight.blue {--c: #1f63b5; --bg: #eef5fd;}
.tile.insight.teal {--c: #0f7a62; --bg: #eaf6f1;}
.tile.insight .explain {font-size: 0.82rem; color: #52514e; margin: 2px 0 8px;}
.tile.insight .figure {border-top: 1px solid rgba(11,11,11,0.08); padding-top: 8px;}
.tile.insight .figure .num {font-size: 1.3rem; font-weight: 700; color: #0b0b0b; white-space: nowrap;}
.tile.insight .figure .what {font-size: 0.8rem; color: #52514e; line-height: 1.35;}
/* Rangliste in den Gruppen-Reitern */
.barlist {display: flex; flex-direction: column; gap: 14px; padding: 2px 6px 18px 0; margin-bottom: 0 !important;
  max-height: max(240px, calc(100vh - 290px)); overflow-y: auto;
  /* unten sanft ausblenden: zeigt, dass man in langen Listen scrollen kann, ohne Zeilen hart abzuschneiden */
  mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
  -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);}
/* Streamlit zieht das naechste Element nach einem Textblock um 1rem hoch - fuer eigene Bloecke aufheben */
.card-text {margin-bottom: 0 !important;}
.barrow {display: grid; grid-template-columns: 28px minmax(150px, 30%) 1fr; gap: 14px; align-items: center;}
.barrow .rank {font-weight: 700; color: #898781; text-align: right;}
.barrow .gname {font-weight: 600; color: #0b0b0b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.barrow .gdesc {font-size: 0.76rem; color: #6b6a66; line-height: 1.3;}
.barrow .track {height: 12px; background: #efefec; border-radius: 999px; overflow: hidden;}
.barrow .fillb {height: 100%; border-radius: 999px; background: #2a78d6;}
.barrow .fillb.tendency {background: #8fb8e8;}
.barrow .bmeta {display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; font-size: 0.8rem;
  color: #52514e; margin-top: 4px;}
.barrow .bmeta b {color: #0b0b0b;}
.intro-box {background: #eef5fd; border-left: 4px solid #1f63b5; border-radius: 10px; padding: 8px 12px;
  font-size: 0.85rem; color: #0b0b0b; line-height: 1.45; margin: -2px 0 10px;}
/* Bestenliste: 2x2 Siegertreppchen */
.podium-grid {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;}
.podium {background: #ffffff; border: 1px solid rgba(11,11,11,0.08); border-radius: 16px; padding: 14px 20px 8px;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 2px 6px rgba(16,24,40,0.05); min-width: 0;}
.podium-head {display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;}
.podium-row {display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: 12px; align-items: center;
  padding: 7px 0; border-top: 1px solid #efefec;}
.medal {width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; font-weight: 800; font-size: 0.95rem;
  box-shadow: inset 0 -2px 0 rgba(0,0,0,0.15), 0 1px 3px rgba(16,24,40,0.18);}
/* Gold, Silber, Bronze als volle Medaillen; dunkle Ziffern fuer genug Kontrast */
.medal.m1 {background: linear-gradient(145deg, #ffe58a, #e8b012); color: #3d2600;}
.medal.m2 {background: linear-gradient(145deg, #f2f3f5, #a9adb4); color: #24272c;}
.medal.m3 {background: linear-gradient(145deg, #f3b98a, #c26a2c); color: #2e1404;}
.pname {font-weight: 600; color: #0b0b0b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.pbar {height: 6px; background: #efefec; border-radius: 999px; margin-top: 5px; overflow: hidden;}
.pbar div {height: 100%; background: #2a78d6; border-radius: 999px;}
.pval {display: flex; flex-direction: column; align-items: flex-end; font-size: 0.75rem; color: #52514e; line-height: 1.25;}
.pval b {font-size: 0.95rem; color: #0b0b0b;}
@media (max-width: 1000px) {.podium-grid {grid-template-columns: 1fr;}}
/* Muster: Erkenntnis-Karten mit Akzentfarbe, Hinweise zur Datenlage gelb */
[class*='st-key-card_pattern_'] {border-top: 4px solid transparent;}
.st-key-card_pattern_0, .st-key-card_pattern_3 {border-top-color: #c4302b !important;}
.st-key-card_pattern_1, .st-key-card_pattern_4 {border-top-color: #1f63b5 !important;}
.st-key-card_pattern_2, .st-key-card_pattern_5 {border-top-color: #0f7a62 !important;}
.pattern-card .phead {display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;}
.pattern-card .pnum {width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
  background: var(--c); color: #ffffff; font-weight: 700; font-size: 0.85rem;}
.pattern-card .dots {letter-spacing: 1px;}
.pattern-card .ptitle {font-weight: 700; color: #0b0b0b; line-height: 1.35; margin-bottom: 6px;}
.pattern-card .pdesc {font-size: 0.88rem; color: #52514e; line-height: 1.45; padding-bottom: 6px;}
/* Muster-Bereich: Platz fuer die Einleitung oberhalb abziehen */
div.st-key-scroll_patterns.st-key-scroll_patterns {height: max(280px, calc(100vh - 245px)) !important;}
.st-key-card_caveats {background: #fdf8ec !important; border-left: 5px solid #f2c14e !important; margin-top: 8px;}
.caveats {margin: 0; padding-left: 1.1rem; font-size: 0.86rem; color: #3a3935; line-height: 1.5;}
.caveats li {margin-bottom: 4px;}
.section-title {font-size: 1.05rem; font-weight: 700; color: #0b0b0b; margin: 8px 0 10px;}
.section-title .hint {font-size: 0.8rem; font-weight: 400; color: #898781; margin-left: 8px;}
.tile-grid.hero {grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; margin-bottom: 8px;}
.tile-grid.hero .tile {padding: 16px 20px;}
.tile.insight .value {font-size: 1.2rem; white-space: normal; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; line-height: 1.25;}

/* Kernaussage mit Akzentstreifen, Top-Empfehlung als dunkle Blickfang-Karte */
.st-key-card_summary {border-left: 5px solid #c4302b !important;}
/* Empfehlungen / Einschraenkungen: Ueberschrift fest oben (deckend), nur der Textbereich darunter scrollt */
.st-key-card_recommendations .card-title, .st-key-card_limitations .card-title {
  margin: 0 !important; padding-bottom: 12px; border-bottom: 1px solid #efefec; background: #ffffff;
}
.st-key-card_recommendations > [data-testid='stElementContainer']:first-child,
.st-key-card_limitations > [data-testid='stElementContainer']:first-child {margin-bottom: 0 !important;}
.st-key-card_recommendations > [data-testid='stLayoutWrapper'],
.st-key-card_limitations > [data-testid='stLayoutWrapper'] {flex: 1 1 0 !important; min-height: 0 !important;}
/* Lauf-Details */
.tile-grid.kpi4 {grid-template-columns: repeat(4, minmax(0, 1fr));}
.tile-grid.kpi4 .sub {white-space: normal; font-size: 0.8rem; color: #52514e;}
.dl {display: flex; flex-direction: column;}
.dl .dt {font-size: 0.78rem; color: #6b6a64; margin-top: 10px;}
.dl .dt:first-child {margin-top: 0;}
.dl .dd {color: #0b0b0b; font-weight: 600; margin-top: 2px;}
.dl .dd .muted {font-weight: 400;}
.dl .dd.mono {font-family: ui-monospace, Consolas, monospace; font-size: 0.82rem; font-weight: 400; color: #52514e;}
.terms {display: flex; flex-wrap: wrap; gap: 6px;}
.term {background: #eef5fd; color: #174a8b; border-radius: 8px; padding: 2px 10px; font-weight: 600;}
.detail-grid {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; align-items: stretch;}
.detail-card {display: flex; flex-direction: column; padding: 18px 20px 20px;}
.detail-card .card-title {margin-bottom: 12px;}
.detail-card .foot {margin-top: auto; padding-top: 14px; font-size: 0.82rem; color: #6b6a64;}
.detail-card .dl + .foot {border-top: 1px solid #efefec; margin-top: auto;}
.detail-card .mono {font-family: ui-monospace, Consolas, monospace; color: #52514e; overflow-wrap: anywhere;}
.error-list {margin: 0; padding-left: 18px; max-height: 260px; overflow-y: auto; font-size: 0.85rem; color: #b42318;}
.all-good {display: flex; gap: 14px; align-items: center; background: #eaf6ee; border-radius: 12px; padding: 16px; flex: 1;}
.all-good .big {width: 38px; height: 38px; border-radius: 50%; background: #0ca30c; color: #ffffff; display: grid;
  place-items: center; font-weight: 800; font-size: 1.1rem; flex: none;}
@media (max-width: 1000px) {.tile-grid.kpi4 {grid-template-columns: repeat(2, minmax(0, 1fr));}
  .detail-grid {grid-template-columns: 1fr;}}
/* Reiter Daten: Liste der Angaben mit Status */
.field-list {display: flex; flex-direction: column;}
.field-row {display: grid; grid-template-columns: minmax(0, 1fr) 190px; gap: 16px; align-items: center;
  padding: 10px 0; border-top: 1px solid #efefec;}
.field-row:first-child {border-top: none; padding-top: 0;}
.fname {font-weight: 700; color: #0b0b0b;}
.fmeaning {color: #2b2b2b; font-size: 0.92rem;}
.fsource {color: #6b6a64; font-size: 0.8rem;}
.fstat {text-align: right;}
.fcount {font-size: 0.85rem; color: #52514e; margin-top: 4px;}
.fbar {height: 6px; background: #efefec; border-radius: 999px; overflow: hidden; margin-top: 4px;}
.fbar div {height: 100%; border-radius: 999px;}
.fbar.good div {background: #0ca30c;} .fbar.warn div {background: #e0a91b;} .fbar.bad div {background: #b42318;}
.st-key-card_data_meaning {border-left: 5px solid #f2c14e !important;}
.st-key-card_data_meaning .card-text + .card-text {margin-top: 12px;}
div.st-key-card_scroll_fields.st-key-card_scroll_fields {height: max(280px, calc(100vh - 245px)) !important;}
/* Hervorhebungen in KI-Texten: Namen als Marker, Zahlen fett, Vorsicht gelb */
.hl-item {display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 12px; line-height: 1.65; color: #2b2b2b;
  padding-bottom: 16px;}
.hl-no {width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-weight: 700;
  font-size: 0.8rem; background: #c4302b; color: #ffffff; margin-top: 2px;}
.hl-no.warn {background: #f2c14e; color: #3d2600;}
.hl-name {background: #e8f0fb; color: #174a8b; font-weight: 600; padding: 0 3px; border-radius: 4px; white-space: nowrap;}
.hl-num {color: #0b0b0b; font-weight: 700;}
.hl-verb {color: #c4302b; font-weight: 700;}
.hl-warn {background: #fdf3dc; color: #6b4500; font-weight: 600; padding: 0 2px; border-radius: 3px;}
.st-key-textbody_recommendations, .st-key-textbody_limitations {
  flex: 1 1 0 !important; min-height: 0 !important; overflow-y: auto !important; padding: 18px 6px 0 0;
  margin-top: 16px !important; /* gleicht Streamlits negativen Abstand unter der Ueberschrift aus */
}
.st-key-card_recommendations > [data-testid='stElementContainer']:first-child,
.st-key-card_limitations > [data-testid='stElementContainer']:first-child {position: relative; z-index: 3; background: #ffffff;}
/* Streamlit setzt unter dem letzten Absatz einen negativen Abstand - hier Platz zum Button lassen */
.card-text.teaser {padding-bottom: 14px;}
.st-key-card_reco {background: #1f2430 !important; border: none !important;}
.st-key-card_reco .card-title {color: #f6c9c6;}
.st-key-card_reco .card-text {color: #ffffff;}
.st-key-card_reco .hint {color: #b9bcc6; font-size: 0.78rem; margin-top: 6px;}
.badge.bad {background: #fde4e4; color: #b42318;}

.prog-head {display: flex; justify-content: space-between; align-items: baseline;}
.prog-head .pct {font-size: 1.5rem; font-weight: 600; color: #0b0b0b;}
.bar {height: 10px; background: #efefec; border-radius: 999px; overflow: hidden; margin: 6px 0 8px;}
.bar .fill {height: 100%; border-radius: 999px; transition: width 0.6s ease;}
.prog-detail {font-size: 0.9rem; color: #52514e; min-height: 1.4em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.prog-detail.error {color: #b42318; white-space: normal;}
.stepper {display: grid; grid-template-columns: repeat(9, minmax(0, 1fr)); gap: 2px; margin-top: 14px;}
.step {position: relative; text-align: center; font-size: 0.74rem; color: #898781;}
.step::before {content: ""; position: absolute; top: 13px; left: -50%; width: 100%; height: 2px; background: #e1e0d9; z-index: 0;}
.step:first-child::before {display: none;}
.step.done::before, .step.active::before, .step.stopped::before, .step.failed::before {background: #0ca30c;}
.step .dot {position: relative; width: 28px; height: 28px; margin: 0 auto 4px; border-radius: 50%; display: grid;
  place-items: center; font-weight: 700; font-size: 0.78rem; background: #efefec; color: #52514e; border: 2px solid #ffffff; z-index: 1;}
.step.done .dot {background: #e3f3ea; color: #006300;}
.step.active .dot {background: #c4302b; color: #ffffff; box-shadow: 0 0 0 4px #fbe9e8;}
.step.failed .dot {background: #fde4e4; color: #b42318;}
.step .name {line-height: 1.2; hyphens: manual;}
.step.done .name {color: #52514e;}
.step.active .name, .step.failed .name, .step.stopped .name {color: #0b0b0b; font-weight: 600;}
@media (max-width: 1000px) {.stepper {grid-template-columns: repeat(5, minmax(0, 1fr)); row-gap: 10px;}}
.pattern-row .t {white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;}
/* Bereiche mit viel Text: so hoch wie das Fenster erlaubt, darin scrollen statt die ganze Seite */
[class*='st-key-scroll'] {
  height: max(280px, calc(100vh - 175px)) !important; overflow-y: auto !important; flex: none !important;
}
.st-key-card_recommendations, .st-key-card_limitations {
  height: max(280px, calc(100vh - 175px)) !important; overflow: hidden !important; flex: none !important;
  display: flex !important; flex-direction: column !important;
}

@media (max-width: 1000px) {
  .tile-grid.hero {grid-template-columns: 1fr;}
  .tile-grid.kpi {grid-template-columns: repeat(3, minmax(0, 1fr));}
  .tile-grid.insight {grid-template-columns: 1fr;}
}
</style>
"""


# ---------------------------------------------------------------------------
# Daten laden - keine Netzwerkzugriffe, nur lokale Dateien unter data/runs/
# ---------------------------------------------------------------------------
def find_runs(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    return sorted(
        (p for p in data_dir.iterdir() if p.is_dir() and (p / "report.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    )


def load_report(run_dir: Path) -> Report:
    return Report.model_validate_json((run_dir / "report.json").read_text(encoding="utf-8"))


def load_clean_data(run_dir: Path) -> pd.DataFrame | None:
    path = run_dir / "clean.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def load_classifications(run_dir: Path) -> list[ClassificationResult]:
    path = run_dir / "classifications.json"
    if not path.exists():
        return []
    return [ClassificationResult(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def export_labels(report: Report) -> tuple[dict[str, str], dict[str, str]]:
    """Lesbare Namen fuer den Excel-Export: Einstiegs-Typen und alle Gruppen."""
    hooks = {key: label for key, (label, _) in HOOK_LABELS.items()}
    groups = {
        g.group: pretty_group(g.group)
        for section in (report.analysis.by_topic, report.analysis.by_hook_type,
                        report.analysis.by_format, report.analysis.by_duration_bucket)
        for g in section
    }
    return hooks, groups


# ---------------------------------------------------------------------------
# Formatierung
# ---------------------------------------------------------------------------
def format_views(value: float | None) -> str:
    """Aufrufe gut lesbar im deutschen Format, z.B. 2,76 Mrd. / 780,5 Mio."""
    if value is None or pd.isna(value):
        return "–"
    for limit, unit, digits in ((1e9, "Mrd.", 2), (1e6, "Mio.", 1), (1e3, "Tsd.", 1)):
        if abs(value) >= limit:
            return f"{value / limit:.{digits}f}".replace(".", ",") + f" {unit}"
    return f"{value:.0f}"


def format_percent(value: float | None) -> str:
    """Retention liegt als 'durchschnittlich gesehener Prozentsatz' (0-100) vor."""
    if value is None or pd.isna(value):
        return "–"
    return f"{value:.1f} %".replace(".", ",")


def slug(text: str) -> str:
    """Fuer Widget-Keys (werden zu CSS-Klassen): nur Buchstaben, Ziffern, Unterstrich."""
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def thousands(number: int) -> str:
    """Ganze Zahl mit deutschem Tausenderpunkt, z.B. 10.000."""
    return f"{number:,}".replace(",", ".")


def esc(text: object) -> str:
    return html.escape(str(text))


def humanize(text: str) -> str:
    """Technische Kennzahlen in KI-Texten lesbar machen, z.B. 'mean_views=2762270389.67' -> 'Ø 2,76 Mrd. Aufrufe'."""
    def views(match: re.Match) -> str:
        number = match.group(1)
        if "," in number:  # deutsches Format: 2.762.270.389,67
            number = number.replace(".", "").replace(",", ".")
        elif number.count(".") > 1:  # Tausenderpunkte ohne Nachkommastellen: 2.762.270.389
            number = number.replace(".", "")
        try:
            return f"Ø {format_views(float(number))} Aufrufe"
        except ValueError:
            return match.group(0)

    text = re.sub(r"mean_views\s*=\s*(\d[\d.,]*\d)", views, text)
    # Einstiegs-Typen und Feldnamen lesbar, "n=2" -> "2 Videos"
    for key, (label, _) in HOOK_LABELS.items():
        # ohne Anfuehrungszeichen nur technische Bezeichner (mit "_"), damit z.B. "sonstigen Themen" unberuehrt bleibt
        text = re.sub(rf"'{key}'" + (rf"|\b{key}\b" if "_" in key else ""), label, text)
    text = re.sub(r"'retention'", "„Zuschauerbindung“", text)
    text = re.sub(r"\bn\s*=\s*(\d+)", lambda m: f"{m.group(1)} Video{'' if m.group(1) == '1' else 's'}", text)
    text = re.sub(r"(\d+ Videos?) Datenpunkte[n]?", r"\1", text)
    # einzeln stehende Aufrufzahlen ab einer Million, z.B. "2049118937.00"
    return re.sub(r"(?<![\d.,])(\d{7,})(?:\.\d+)?(?![\d.,]*\d)", lambda m: format_views(float(m.group(1))), text)


# Schreibweisen ohne Umlaute aus den Agenten-Texten fuer die Anzeige korrigieren
UMLAUT_FIXES = {
    "ueber": "über", "Ueber": "Über", "fuer": "für", "Fuer": "Für", "verfuegbar": "verfügbar",
    "Kanaele": "Kanäle", "Ausreisser": "Ausreißer", "moeglich": "möglich", "koennen": "können",
    "waere": "wäre", "groesser": "größer", "geschaetzt": "geschätzt", "zusaetzlich": "zusätzlich",
    "Konfidenz": "Sicherheit",
}
# Formulierungen, die zur Vorsicht mahnen - werden gelb hinterlegt
CAUTION_PHRASES = [
    r"nicht statistisch belastbar", r"nicht belastbar", r"keine belastbaren [A-Za-zäöü]+", r"Survivorship Bias",
    r"Keine eigenen [A-Za-z-]+-Daten", r"Einzelfall-Charakter", r"Datenbasis gering",
    r"niedrige[rn]? (?:Sicherheit|Aussagekraft)", r"vorläufige Hypothesen",
]
HIGHLIGHT_PATTERN = re.compile(
    r"(?P<name>'[^'\n]{2,40}'|„[^“\n]{2,40}“)"
    r"|(?P<num>Ø\s?\d[\d.,]*\s?(?:Mrd\.|Mio\.|Tsd\.)?(?:\s?Aufrufe)?|\d[\d,]*\s?(?:Mrd\.|Mio\.)|\(?\d+\s?Videos?\)?|\d+\s?Shorts)"
    r"|(?P<warn>" + "|".join(CAUTION_PHRASES) + ")",
)


def highlight(text: str, lead_verb: bool = False) -> str:
    """KI-Text als HTML mit Hervorhebungen: Namen als Marker, Zahlen fett, Vorsicht-Hinweise gelb."""
    text = humanize(text)
    for wrong, right in UMLAUT_FIXES.items():
        text = re.sub(rf"\b{wrong}", right, text)
    parts, last = [], 0
    for match in HIGHLIGHT_PATTERN.finditer(text):
        parts.append(esc(text[last:match.start()]))
        if match.group("name"):
            parts.append(f'<span class="hl-name">{esc(match.group("name")[1:-1])}</span>')
        elif match.group("num"):
            parts.append(f'<b class="hl-num">{esc(match.group("num"))}</b>')
        else:
            parts.append(f'<span class="hl-warn">{esc(match.group("warn"))}</span>')
        last = match.end()
    parts.append(esc(text[last:]))
    result = "".join(parts)
    if lead_verb:  # erstes Wort einer Empfehlung ist das Tu-Wort ("Setze", "Produziere" ...)
        result = re.sub(r"^([A-ZÄÖÜ][a-zäöüß]+)", r'<b class="hl-verb">\1</b>', result)
    return result


def teaser(text: str, limit: int) -> str:
    """So viele ganze Saetze, wie in `limit` Zeichen passen - kein Abbruch mitten im Satz.
    Nur wenn schon der erste Satz zu lang ist, wird er an einer Wortgrenze gekuerzt."""
    result = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        candidate = f"{result} {sentence}".strip()
        if len(candidate) > limit:
            break
        result = candidate
    return result or shorten(text, limit)


def first_sentences(text: str, count: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:count])


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + " …"


def best_group(groups: list[GroupStats]) -> GroupStats | None:
    """Gruppe mit der hoechsten Zuschauerbindung, ersatzweise mit den meisten Aufrufen (wie ranking.py)."""
    use_retention = any(g.mean_retention is not None for g in groups)
    candidates = [g for g in groups if (g.mean_retention if use_retention else g.mean_views) is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda g: g.mean_retention if use_retention else g.mean_views)


def reliability_badge(reliable: bool, sample_size: int) -> str:
    """Abzeichen, ob eine Gruppe genug Videos fuer eine belastbare Aussage hat (Erklaerung beim Darueberfahren)."""
    if reliable:
        tip = f"{sample_size} Videos – genug für eine belastbare Aussage (ab {MIN_RELIABLE_SAMPLE_SIZE})."
        return f'<span class="badge good" title="{esc(tip)}">✓ belastbar</span>'
    tip = (f"Nur {sample_size} Video{'s' if sample_size != 1 else ''} – für eine belastbare Aussage braucht es "
           f"mindestens {MIN_RELIABLE_SAMPLE_SIZE}. Das Ergebnis kann Zufall sein.")
    return f'<span class="badge neutral" title="{esc(tip)}">○ nur Tendenz</span>'


# Hook-Typen (siehe classification/prompts/hook_prompt.txt): lesbarer Name + kurze Erklaerung
HOOK_LABELS: dict[str, tuple[str, str]] = {
    "ueberraschende_aussage": ("Überraschende Aussage", "Startet mit einer verblüffenden Aussage."),
    "direkte_frage": ("Direkte Frage", "Stellt den Zuschauern gleich eine Frage."),
    "ungewoehnliche_behauptung": ("Ungewöhnliche Behauptung", "Beginnt mit einer gewagten Behauptung."),
    "konflikt_oder_problem": ("Konflikt oder Problem", "Zeigt sofort ein Problem oder einen Konflikt."),
    "sofortige_handlung": ("Sofortige Handlung", "Steigt ohne Einleitung direkt ins Geschehen ein."),
    "visuell_ungewoehnliche_szene": ("Ungewöhnliches Bild", "Beginnt mit einer auffälligen, ungewohnten Szene."),
    "versprechen_eines_ergebnisses": ("Versprechen eines Ergebnisses", "Verspricht gleich am Anfang ein Ergebnis."),
    "offene_frage_informationsluecke": ("Offene Frage / Neugier", "Weckt Neugier, die erst später aufgelöst wird."),
    "sonstige": ("Sonstiger Einstieg", "Passt zu keinem typischen Einstiegs-Muster."),
}


def pretty_group(name: str) -> str:
    """Technische Bezeichner lesbar machen: Hook-Typen und Laengen-Gruppen wie '0-15s'."""
    if name in HOOK_LABELS:
        return HOOK_LABELS[name][0]
    duration = re.fullmatch(r"(\d+)-(\d+)s", name)
    if duration:
        start, end = int(duration.group(1)), int(duration.group(2))
        if start >= 60 and end % 60 == 0:
            return f"{start // 60}–{end // 60} Minuten"
        return f"{start}–{end} Sekunden"
    return name.replace("_", " ").strip().capitalize() if "_" in name else name


def group_explanation(kind: str, name: str) -> str:
    """Ein kurzer Satz, was die Gewinner-Gruppe einer Erkenntnis-Karte bedeutet."""
    if kind == "hook":
        return HOOK_LABELS.get(name, ("", "Art des Einstiegs in den ersten Sekunden."))[1]
    if kind == "duration":
        return "Länge der Videos in dieser Gruppe."
    return "Themenbereich der Videos."


# ---------------------------------------------------------------------------
# Chart-Bausteine
# ---------------------------------------------------------------------------
CHART_HEIGHT = 340


# Angaben je Video: Anzeigename, was sie bedeutet, woher sie kommt
FIELD_INFO = {
    "views": ("Aufrufe", "Wie oft das Video angesehen wurde.", "öffentlich bei YouTube"),
    "likes": ("Likes", "Wie viele Daumen-hoch das Video bekommen hat.", "öffentlich bei YouTube, kann vom Kanal versteckt werden"),
    "comments": ("Kommentare", "Wie viele Kommentare unter dem Video stehen.", "öffentlich bei YouTube, fehlt, wenn Kommentare abgeschaltet sind"),
    "retention": ("Zuschauerbindung", "Wie viel vom Video die Zuschauer im Schnitt ansehen.", "gibt YouTube nur dem Besitzer des Kanals heraus"),
    "topic": ("Thema", "Worum es im Video geht.", "von der KI aus Titel und Beschreibung eingeordnet"),
    "hook_type": ("Einstieg (Hook)", "Wie die ersten Sekunden die Aufmerksamkeit holen.", "von der KI eingeordnet"),
}


def field_rows_html(completeness: dict[str, float], video_count: int) -> str:
    """Je Angabe eine Zeile: Status (Symbol + Wort), Name, Erklärung, Quelle, 'X von Y Videos'.
    Fehlende und lückenhafte Angaben zuerst - sie sind das Wichtigste."""
    rows = []
    for key in sorted(completeness, key=lambda k: completeness[k]):
        ratio = completeness[key]
        label, meaning, source = FIELD_INFO.get(key, (key, "", ""))
        if ratio >= 1:
            kind, status = "good", "✓ vollständig"
        elif ratio <= 0:
            kind, status = "bad", "✗ fehlt"
        else:
            kind, status = "warn", "◐ teilweise"
        have = round(ratio * video_count)
        rows.append(
            f'<div class="field-row"><div><div class="fname">{esc(label)}</div>'
            f'<div class="fmeaning">{esc(meaning)}</div><div class="fsource">Quelle: {esc(source)}</div></div>'
            f'<div class="fstat"><span class="badge {kind}">{status}</span>'
            f'<div class="fcount"><b>{have}</b> von {video_count} Videos</div>'
            f'<div class="fbar {kind}"><div style="width:{ratio * 100:.0f}%"></div></div></div></div>'
        )
    return '<div class="field-list">' + "".join(rows) + "</div>"



# Kurze Erklaerung oben im Reiter, wenn der Begriff nicht selbsterklaerend ist
GROUP_INTROS = {
    "hook": ("<b>Was ist ein Hook?</b> Der Einstieg eines Shorts – die ersten 1–3 Sekunden. Er entscheidet, ob "
             "jemand weiterschaut oder weiterwischt. Die KI ordnet jedes Video einem von 9 Einstiegs-Typen zu, "
             "allein anhand von Titel und Beschreibung (das Video selbst sieht sie nicht)."),
}

GROUP_QUESTIONS = {
    "topic": ("Welche Themen bringen die meisten Aufrufe?", "Thema"),
    "hook": ("Welcher Einstieg in den ersten Sekunden bringt die meisten Aufrufe?", "Einstieg (Hook)"),
    "format": ("Welche Video-Formate bringen die meisten Aufrufe?", "Format"),
    "duration": ("Wie lang sind die Videos mit den meisten Aufrufen?", "Videolänge"),
}


def render_group_section(kind: str, groups: list[GroupStats]) -> None:
    """Eine Rangliste je Kategorie: Platz · Name · Balken · Wert in Worten · Anzahl Videos · Belastbarkeit."""
    question, group_word = GROUP_QUESTIONS[kind]
    if not groups:
        st.info("Für diesen Lauf liegen hier keine Daten vor.")
        return

    use_retention = any(g.mean_retention is not None for g in groups)
    value = (lambda g: g.mean_retention) if use_retention else (lambda g: g.mean_views)
    ranked = sorted((g for g in groups if value(g) is not None), key=value, reverse=True)
    top = value(ranked[0]) if ranked else 0
    measure = "des Videos im Schnitt angesehen" if use_retention else "Aufrufe pro Video im Schnitt"
    fmt = format_percent if use_retention else format_views

    text_col, table_col = st.columns([4, 1], vertical_alignment="bottom")
    intro = GROUP_INTROS.get(kind)
    text_col.markdown(
        f'<div class="section-title">{esc(question)}</div>'
        + (f'<div class="intro-box">💡 {intro}</div>' if intro else "")
        + f'<div class="muted" style="margin:-4px 0 4px">Jeder Balken zeigt, wie viele {"Prozent" if use_retention else "Aufrufe"} '
        f'ein Video dieser Gruppe im Schnitt hatte – sortiert vom höchsten Wert.</div>',
        unsafe_allow_html=True,
    )

    rows = []
    for rank, group in enumerate(ranked, start=1):
        name = pretty_group(group.group)
        explanation = HOOK_LABELS[group.group][1] if kind == "hook" and group.group in HOOK_LABELS else ""
        width = 100 * value(group) / top if top else 0
        videos = f"{group.sample_size} Video{'s' if group.sample_size != 1 else ''}"
        rows.append(
            f'<div class="barrow"><div class="rank">{rank}.</div>'
            f'<div class="gcell"><div class="gname" title="{esc(name)}">{esc(name)}</div>'
            + (f'<div class="gdesc">{esc(explanation)}</div>' if explanation else "")
            + f'</div><div><div class="track"><div class="fillb {"" if group.is_reliable else "tendency"}" '
            f'style="width:{width:.1f}%"></div></div>'
            f'<div class="bmeta"><span><b>{esc(fmt(value(group)))}</b> {esc(measure)}</span>'
            f'<span>{esc(videos)} {reliability_badge(group.is_reliable, group.sample_size)}</span></div></div></div>'
        )

    with table_col.popover("Genaue Zahlen", type="tertiary", icon=":material/table_chart:"):
        table = pd.DataFrame(
            {
                group_word: [pretty_group(g.group) for g in ranked],
                "Videos": [g.sample_size for g in ranked],
                "Durchschnitt": [fmt(value(g)) for g in ranked],
                "Mittlerer Wert": [fmt(g.median_retention if use_retention else g.median_views) for g in ranked],
                "Belastbar": ["ja" if g.is_reliable else "nur Tendenz" for g in ranked],
            }
        )
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.caption(
            f"**Durchschnitt:** {measure}. **Mittlerer Wert (Median):** Die Hälfte der Videos liegt darüber, "
            "die Hälfte darunter. Er ist weniger anfällig für einzelne extrem erfolgreiche Videos. "
            f"**Belastbar** ab {MIN_RELIABLE_SAMPLE_SIZE} Videos pro Gruppe."
        )

    with st.container(key=f"card_group_{kind}"):
        st.markdown('<div class="barlist">' + "".join(rows) + "</div>", unsafe_allow_html=True)


LEADERBOARD = [
    ("topic", "🏷️ Themen", "by_topic"),
    ("hook", "🎣 Einstieg", "by_hook_type"),
    ("format", "🎬 Formate", "by_format"),
    ("duration", "⏱️ Videolänge", "by_duration_bucket"),
]


def podium_html(kind: str, title: str, groups: list[GroupStats]) -> str:
    """Top 3 einer Kategorie als Siegertreppchen (Medaille = Nummer + Farbe, nie Farbe allein)."""
    use_retention = any(g.mean_retention is not None for g in groups)
    value = (lambda g: g.mean_retention) if use_retention else (lambda g: g.mean_views)
    ranked = sorted((g for g in groups if value(g) is not None), key=value, reverse=True)
    fmt = format_percent if use_retention else format_views
    unit = "gesehen" if use_retention else "Aufrufe/Video"
    head = (f'<div class="podium-head"><span class="card-title" style="margin:0">{esc(title)}</span>'
            f'<span class="muted">Top 3 von {len(ranked)}</span></div>')
    if not ranked:
        return f'<div class="podium">{head}<div class="muted">Keine Daten.</div></div>'

    top = value(ranked[0])
    rows = []
    for place, group in enumerate(ranked[:3], start=1):
        name = pretty_group(group.group)
        width = 100 * value(group) / top if top else 0
        videos = f"{group.sample_size} Video{'s' if group.sample_size != 1 else ''}"
        rows.append(
            f'<div class="podium-row"><div class="medal m{place}" aria-label="Platz {place}">{place}</div>'
            f'<div class="pcell"><div class="pname" title="{esc(name)}">{esc(name)}</div>'
            f'<div class="pbar"><div style="width:{width:.1f}%"></div></div></div>'
            f'<div class="pval"><span><b>{esc(fmt(value(group)))}</b> {esc(unit)}</span>'
            f'<span title="{"belastbar" if group.is_reliable else "nur Tendenz: zu wenige Videos"}">'
            f'{esc(videos)} {"✓" if group.is_reliable else "○"}</span></div></div>'
        )
    return f'<div class="podium">{head}{"".join(rows)}</div>'


def render_leaderboard(report: Report) -> None:
    st.markdown(
        '<div class="section-title">Das Erfolgsrezept auf einen Blick'
        '<span class="hint">die drei Besten aus jedem Bereich</span></div>',
        unsafe_allow_html=True,
    )
    cards = [podium_html(kind, title, getattr(report.analysis, field)) for kind, title, field in LEADERBOARD]
    st.markdown('<div class="podium-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="muted" style="margin-top:10px">✓ belastbar (ab {MIN_RELIABLE_SAMPLE_SIZE} Videos) · '
        "○ nur Tendenz. Alle Plätze im jeweiligen Reiter.</div>",
        unsafe_allow_html=True,
    )


CONFIDENCE_METER = {"hoch": ("●●●", "hoch"), "mittel": ("●●○", "mittel"), "niedrig": ("●○○", "niedrig")}
# Akzentfarben der Erkenntnis-Karten (wie im Ueberblick: rot, blau, gruen)
PATTERN_COLORS = ["#c4302b", "#1f63b5", "#0f7a62"]


def is_data_caveat(pattern: PatternInsight) -> bool:
    """Aussagen wie 'Keine Aussage zu ... moeglich' sind Hinweise zur Datenlage, keine Erkenntnisse."""
    return bool(re.match(r"^(keine?|kein|nicht)\b", pattern.title.strip(), re.IGNORECASE))


def render_patterns(patterns: list[PatternInsight]) -> None:
    if not patterns:
        st.info("Keine Muster erkannt (zu wenig Daten oder die KI-Auswertung ist fehlgeschlagen).")
        return
    findings = [p for p in patterns if not is_data_caveat(p)]
    caveats = [p for p in patterns if is_data_caveat(p)]

    st.markdown(
        '<div class="section-title">Was die KI in den Zahlen erkannt hat</div>'
        '<div class="muted" style="margin:-4px 0 12px">Muster sind Zusammenhänge, die die KI aus den berechneten '
        "Kennzahlen ableitet. Die Sicherheit zeigt, wie stark die Daten das stützen.</div>",
        unsafe_allow_html=True,
    )

    with st.container(key="scroll_patterns"):
        if findings:
            columns = st.columns(min(3, len(findings)), gap="medium")
            for index, pattern in enumerate(findings):
                dots, level = CONFIDENCE_METER.get(pattern.confidence, ("○○○", pattern.confidence))
                kind, _ = CONFIDENCE_BADGE.get(pattern.confidence, ("neutral", ""))
                color = PATTERN_COLORS[index % len(PATTERN_COLORS)]
                with columns[index % len(columns)].container(key=f"card_pattern_{index}"):
                    st.markdown(
                        f'<div class="pattern-card" style="--c:{color}">'
                        f'<div class="phead"><span class="pnum">{index + 1}</span>'
                        f'<span class="badge {kind}" title="Wie stark die Daten dieses Muster stützen">'
                        f'Sicherheit <span class="dots">{dots}</span> {esc(level)}</span></div>'
                        f'<div class="ptitle">{esc(humanize(pattern.title))}</div>'
                        f'<div class="pdesc">{esc(humanize(pattern.description))}</div></div>',
                        unsafe_allow_html=True,
                    )
                    with st.expander("Worauf beruht das?"):
                        st.caption(humanize(pattern.supporting_evidence))

        if caveats:
            items = "".join(
                f'<li><b>{esc(humanize(p.title))}</b> – {esc(humanize(p.description))}</li>' for p in caveats
            )
            with st.container(key="card_caveats"):
                st.markdown(
                    '<div class="card-title">⚠️ Hinweise zur Datenlage</div>'
                    f'<ul class="caveats">{items}</ul>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Seiten des Control Panels
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "runs"
CATEGORIES = list(config.DEFAULT_SEARCH_QUERIES.keys())

STATE_ICON = {
    RunState.RUNNING: "⏳",
    RunState.FINISHED: "✅",
    RunState.CANCELLED: "⏹️",
    RunState.FAILED: "❌",
}

PAGES: dict[str, st.Page] = {}


def state_label(state: RunState) -> str:
    return f"{STATE_ICON[state]} {STATE_LABELS[state]}"


def format_duration(start: dt.datetime | None, end: dt.datetime | None) -> str:
    if start is None:
        return "–"
    seconds = int(((end or dt.datetime.now(dt.timezone.utc)) - start).total_seconds())
    minutes, seconds = divmod(max(seconds, 0), 60)
    return f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"


def format_local(timestamp: dt.datetime | None) -> str:
    return timestamp.astimezone().strftime("%d.%m.%Y %H:%M") if timestamp else "–"


def open_results(run_id: str) -> None:
    st.session_state["selected_run"] = run_id
    st.switch_page(PAGES["results"])


def open_progress(run_id: str) -> None:
    st.session_state["selected_run"] = run_id
    st.switch_page(PAGES["progress"])


def page_new_run() -> None:
    st.title("🚀 Neuer Analyse-Lauf")
    st.caption(
        "Der Agent sucht passende Shorts über die YouTube-Schnittstelle, lässt sie von der KI einordnen, "
        "wertet sie statistisch aus und schreibt einen Report. Der Lauf arbeitet im Hintergrund weiter, "
        "auch wenn du diese Seite verlässt."
    )

    missing = run_control.missing_api_keys(PROJECT_ROOT)
    if missing:
        st.error(
            f"Es fehlen API-Keys in der Datei `.env`: **{', '.join(missing)}**. "
            "Vorlage: `.env.example`. Ohne diese Keys kann kein Lauf gestartet werden."
        )

    running = run_control.active_run(PROJECT_ROOT)
    if running:
        st.warning(f"Es läuft bereits ein Lauf ({running.run_id}). Es kann immer nur ein Lauf gleichzeitig laufen.")
        if st.button("Zum laufenden Lauf"):
            open_progress(running.run_id)

    all_categories = st.toggle("Alle Themen untersuchen", value=False)
    if all_categories:
        categories = CATEGORIES
        st.caption(f"Alle {len(CATEGORIES)} Themen werden untersucht.")
    else:
        categories = st.multiselect(
            "Themen",
            options=CATEGORIES,
            default=["Wissen / Bildung"],
            placeholder="Mindestens ein Thema auswählen",
        )
    max_results = st.slider(
        "Videos pro Suchbegriff",
        min_value=1,
        max_value=50,
        value=5,
        help="Jedes Thema hat 1–2 Suchbegriffe. Für einen ersten Testlauf reichen 5.",
    )

    if categories:
        usage = run_control.estimate_usage(categories, max_results)
        share = usage.youtube_quota_units / run_control.YOUTUBE_DAILY_QUOTA
        runs_per_day = run_control.YOUTUBE_DAILY_QUOTA // usage.youtube_quota_units if usage.youtube_quota_units else 0
        tiles = [
            ("Videos", f"bis {usage.max_videos}",
             f"{usage.search_queries} Suchbegriff{'e' if usage.search_queries != 1 else ''} × {max_results} Videos"),
            ("YouTube (kostenlos)", f"{share:.0%} vom Tageslimit",
             f"etwa {runs_per_day} solche Läufe pro Tag möglich" if runs_per_day else "Tageslimit überschritten"),
            ("KI-Anfragen (kostenpflichtig)", f"bis {usage.max_llm_calls}", "über dein Anthropic-Konto"),
        ]
        st.markdown(
            '<div class="tile-grid insight spaced">'
            + "".join(
                f'<div class="tile"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>'
                f'<div class="sub">{esc(sub)}</div></div>'
                for label, value, sub in tiles
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Was bedeutet das?"):
            st.markdown(
                f"""
- **Videos:** Für jedes gewählte Thema gibt es 1–2 Suchbegriffe. Pro Suchbegriff holt der Agent bis zu
  {max_results} Videos. Doppelte Videos und Videos, die keine Shorts sind, fallen später weg.
- **YouTube (kostenlos):** Google erlaubt jedem API-Schlüssel ein Tageslimit von
  {thousands(run_control.YOUTUBE_DAILY_QUOTA)} „Einheiten“. Eine Suche verbraucht {run_control.QUOTA_SEARCH_LIST}
  Einheiten, das Abrufen der Video-Details {run_control.QUOTA_VIDEOS_LIST}. Dieser Lauf braucht also etwa
  {thousands(usage.youtube_quota_units)} Einheiten. Ist das Limit erreicht, sucht YouTube erst am nächsten Tag
  wieder (das Limit wird gegen 9 Uhr deutscher Zeit zurückgesetzt). Es entstehen dabei keine Kosten.
- **KI-Anfragen (kostenpflichtig):** Claude ordnet jedes Video zweimal ein (Thema und Einstieg) und
  schreibt danach Muster, Empfehlungen und die Zusammenfassung. Die Kosten rechnet Anthropic über dein
  Konto ab; deinen Verbrauch siehst du unter [console.anthropic.com](https://console.anthropic.com/settings/usage).
"""
            )
        if share > 1:
            st.warning("Diese Auswahl braucht mehr als das YouTube-Tageslimit. Bitte weniger Themen oder Videos wählen.")

    can_start = bool(categories) and not missing and running is None
    if st.button("▶ Lauf starten", type="primary", disabled=not can_start):
        run_id = run_control.start_run(PROJECT_ROOT, [] if all_categories else categories, max_results)
        open_progress(run_id)


STATE_BADGE = {
    RunState.RUNNING: ("warn", "⏳ läuft"),
    RunState.FINISHED: ("good", "✓ fertig"),
    RunState.CANCELLED: ("neutral", "⏹ abgebrochen"),
    RunState.FAILED: ("bad", "✕ fehlgeschlagen"),
}
# Farbe des Fortschrittsbalkens je Zustand (immer zusammen mit dem Text-Abzeichen, nie allein)
BAR_COLOR = {
    RunState.RUNNING: ACCENT,
    RunState.FINISHED: "#0ca30c",
    RunState.CANCELLED: "#898781",
    RunState.FAILED: "#b42318",
}


def state_badge(state: RunState) -> str:
    kind, label = STATE_BADGE[state]
    return f'<span class="badge {kind}">{esc(label)}</span>'


# Trennstellen (weiches Trennzeichen), damit lange Schrittnamen sauber umbrechen
STEP_LABELS = {"Datensammlung": "Daten­sammlung", "Klassifizierung": "Klassi­fizierung",
               "Mustererkennung": "Muster­erkennung", "Bereinigung": "Berei­nigung"}


def stepper_html(stage_index: int, state: RunState) -> str:
    """Die 9 Pipeline-Schritte als waagerechte Leiste."""
    steps = []
    for index, name in enumerate(PIPELINE_STAGES):
        if state == RunState.FINISHED or index < stage_index:
            css, mark = "done", "✓"
        elif index == stage_index:
            css, mark = {RunState.RUNNING: ("active", str(index + 1)), RunState.CANCELLED: ("stopped", "⏹"),
                         RunState.FAILED: ("failed", "✕")}[state]
        else:
            css, mark = "todo", str(index + 1)
        steps.append(f'<div class="step {css}"><div class="dot">{mark}</div><div class="name">{esc(STEP_LABELS.get(name, name))}</div></div>')
    return '<div class="stepper">' + "".join(steps) + "</div>"


@st.fragment(run_every=2)
def live_progress(run_dir: Path, shown_state: RunState) -> None:
    info = run_control.load_run(run_dir)
    if info.state != shown_state:
        st.rerun(scope="app")  # Zustand hat sich geaendert -> auch Kopfzeile und Auswahl aktualisieren
    status = info.status
    if status is None:
        with st.container(key="card_legacy"):
            st.markdown('<div class="card-text">Für diesen älteren Lauf gibt es keine Fortschrittsdaten.</div>',
                        unsafe_allow_html=True)
            if info.has_report and st.button("📊 Ergebnisse ansehen", type="primary"):
                open_results(info.run_id)
        return

    running = info.state == RunState.RUNNING
    percent = status.fraction_done
    step_number = max(status.stage_index + 1, 0)
    if info.state == RunState.FINISHED:
        detail = f"Lauf abgeschlossen in {format_duration(status.started_at, info.finished_at)}."
    elif info.state == RunState.FAILED:
        detail = f"Fehlgeschlagen: {info.error or 'unbekannter Fehler'}"
    elif info.state == RunState.CANCELLED:
        detail = "Lauf angehalten, es wurde kein Report gespeichert."
    elif stop_requested(run_dir):
        detail = "Stopp angefordert: Der Agent hält nach dem aktuellen Arbeitsschritt an."
    else:
        detail = status.detail or "Wird gestartet …"

    with st.container(key="card_progress"):
        st.markdown(
            f'<div class="prog-head"><span class="card-title" style="margin:0">Schritt {step_number} von '
            f'{len(PIPELINE_STAGES)} · {esc(status.stage_name)}</span><span class="pct">{percent:.0%}</span></div>'
            f'<div class="bar"><div class="fill" style="width:{percent * 100:.1f}%;background:{BAR_COLOR[info.state]}"></div></div>'
            f'<div class="prog-detail {"error" if info.state == RunState.FAILED else ""}">{esc(shorten(detail, 160))}</div>'
            + stepper_html(status.stage_index, info.state),
            unsafe_allow_html=True,
        )

    tiles = [
        ("Laufzeit", format_duration(status.started_at, info.finished_at), "läuft noch" if running else "gesamt"),
        ("Gestartet", format_local(status.started_at), "lokale Zeit"),
        ("Videos pro Suchbegriff", status.max_results_per_query or "–", "Einstellung beim Start"),
    ]
    st.markdown(
        '<div class="tile-grid insight spaced">'
        + "".join(
            f'<div class="tile"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>'
            f'<div class="sub">{esc(sub)}</div></div>'
            for label, value, sub in tiles
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    col1, _, col3 = st.columns([1, 2, 1], gap="small")
    if running:
        if stop_requested(run_dir):
            if col1.button("Sofort beenden", use_container_width=True,
                           help="Beendet den Prozess hart. Bereits gesammelte Daten gehen verloren."):
                run_control.kill_run(run_dir)
                st.rerun(scope="fragment")
        elif col1.button("⏹ Lauf anhalten", use_container_width=True,
                         help="Der Agent hört nach dem aktuellen Video bzw. der aktuellen Suchanfrage auf."):
            request_stop(run_dir)
            st.rerun(scope="fragment")
    elif info.state == RunState.FINISHED:
        if col1.button("📊 Ergebnisse ansehen", type="primary", use_container_width=True):
            open_results(info.run_id)
    else:
        if col1.button("🚀 Neuer Lauf", use_container_width=True):
            st.switch_page(PAGES["new"])

    log_path = run_dir / LOG_FILE
    if log_path.exists():
        with col3.popover("📄 Log anzeigen", use_container_width=True, help="Ausgabe des Agenten (log.txt)"):
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            st.code(log_text[-5000:] or "(noch keine Ausgabe)", language="text")


def page_progress() -> None:
    runs = run_control.list_runs(PROJECT_ROOT)
    if not runs:
        st.markdown('<div class="page-head"><span class="title">⏱️ Fortschritt</span></div>', unsafe_allow_html=True)
        st.info("Es gibt noch keine Läufe.")
        if st.button("Neuen Lauf starten"):
            st.switch_page(PAGES["new"])
        return

    run_ids = [run.run_id for run in runs]
    active = next((run.run_id for run in runs if run.state == RunState.RUNNING), None)
    # ?lauf=<run_id> in der Adresse oeffnet direkt einen bestimmten Lauf
    preferred = st.query_params.get("lauf") or st.session_state.get("selected_run") or active or run_ids[0]
    labels = {run.run_id: f"{STATE_BADGE[run.state][1].split()[0]} {format_local(run.started_at)}" for run in runs}
    with st.sidebar:
        run_id = st.selectbox(
            "Lauf",
            options=run_ids,
            index=run_ids.index(preferred) if preferred in run_ids else 0,
            format_func=labels.get,
        )
    st.session_state["selected_run"] = run_id
    run = next(run for run in runs if run.run_id == run_id)

    chips = [format_local(run.started_at), ", ".join(run.categories) if run.categories else "alle Themen"]
    st.markdown(
        '<div class="page-head"><span class="title">⏱️ Fortschritt</span>'
        + state_badge(run.state)
        + "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)
        + "</div>",
        unsafe_allow_html=True,
    )
    live_progress(DATA_DIR / run_id, run.state)


def page_all_runs() -> None:
    st.title("🗂️ Alle Läufe")
    runs = run_control.list_runs(PROJECT_ROOT)
    if not runs:
        st.info("Es gibt noch keine Läufe.")
        return

    table = pd.DataFrame(
        [
            {
                "Gestartet": format_local(run.started_at),
                "Status": state_label(run.state),
                "Themen": ", ".join(run.categories) if run.categories else "alle",
                "Gültige Shorts": "–" if run.videos_valid is None else str(run.videos_valid),
                "Dauer": format_duration(run.started_at, run.finished_at) if run.state != RunState.RUNNING else "läuft …",
                "Lauf-ID": run.run_id,
            }
            for run in runs
        ]
    )
    st.caption("Zeile anklicken, um den Lauf zu öffnen. Mehrere Zeilen auswählen, um sie zu löschen.")
    event = st.dataframe(
        table, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="multi-row"
    )
    selected = [runs[i] for i in event.selection.rows]
    if not selected:
        return

    if len(selected) == 1:
        run = selected[0]
        col1, col2 = st.columns(2)
        if col1.button("⏱️ Fortschritt anzeigen", use_container_width=True):
            open_progress(run.run_id)
        if col2.button("📊 Ergebnisse ansehen", use_container_width=True, disabled=not run.has_report, type="primary"):
            open_results(run.run_id)

    deletable = [run for run in selected if run.state != RunState.RUNNING]
    if len(deletable) < len(selected):
        st.info("Laufende Läufe können nicht gelöscht werden. Bitte zuerst auf der Seite „Fortschritt“ anhalten.")
    label = "🗑️ Lauf löschen" if len(deletable) == 1 else f"🗑️ {len(deletable)} Läufe löschen"
    if deletable and st.button(label):
        confirm_delete([run.run_id for run in deletable])


@st.dialog("Läufe löschen")
def confirm_delete(run_ids: list[str]) -> None:
    st.write(
        f"Diese {len(run_ids)} Läufe werden mit allen Dateien (Rohdaten, Report, Log) endgültig gelöscht:"
        if len(run_ids) > 1
        else "Dieser Lauf wird mit allen Dateien (Rohdaten, Report, Log) endgültig gelöscht:"
    )
    for run_id in run_ids:
        st.markdown(f"- `{run_id}`")
    st.warning("Das lässt sich nicht rückgängig machen.")
    col1, col2 = st.columns(2)
    if col1.button("Endgültig löschen", type="primary", use_container_width=True):
        errors = []
        for run_id in run_ids:
            try:
                run_control.delete_run(PROJECT_ROOT, run_id)
            except (ValueError, OSError) as exc:
                errors.append(str(exc))
        if st.session_state.get("selected_run") in run_ids:
            del st.session_state["selected_run"]
        if errors:
            st.error("\n\n".join(errors))
        else:
            st.rerun()
    if col2.button("Abbrechen", use_container_width=True):
        st.rerun()


def page_results() -> None:
    runs = find_runs(DATA_DIR)

    if not runs:
        st.title("📊 Ergebnisse")
        st.info("Noch kein fertiger Report vorhanden. Starte zuerst einen Lauf.")
        if st.button("Neuen Lauf starten"):
            st.switch_page(PAGES["new"])
        return

    preferred = st.session_state.get("selected_run")
    run_names = [p.name for p in runs]
    with st.sidebar:
        selected_dir = st.selectbox(
            "Report-Lauf",
            options=runs,
            index=run_names.index(preferred) if preferred in run_names else 0,
            format_func=lambda p: f"{p.name} " + ("(neuester)" if p == runs[0] else ""),
        )
    st.session_state["selected_run"] = selected_dir.name

    report = load_report(selected_dir)
    meta = report.run_metadata

    retention_available = report.analysis.data_completeness.get("retention", 0.0) > 0
    chips = [", ".join(meta.categories_used) or "alle Themen", format_local(meta.started_at),
             f"{meta.videos_valid} von {meta.videos_examined} Videos ausgewertet"]
    retention_note = "" if retention_available else (
        '<span class="badge warn" title="Für fremde Kanäle liefert YouTube keine Zuschauerbindung. '
        'Vergleiche basieren deshalb auf Aufrufen.">⚠ ohne Retention-Daten</span>'
    )
    st.markdown(
        '<div class="page-head"><span class="title">📊 Ergebnisse</span>'
        + "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)
        + retention_note
        + "</div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(
        ["Überblick", "Themen", "Einstieg", "Formate", "Videolänge", "Top 3", "Muster", "Empfehlungen", "Daten", "Lauf-Details"]
    )

    with tabs[0]:
        render_overview(report)
    with tabs[1]:
        render_group_section("topic", report.analysis.by_topic)
    with tabs[2]:
        render_group_section("hook", report.analysis.by_hook_type)
    with tabs[3]:
        render_group_section("format", report.analysis.by_format)
    with tabs[4]:
        render_group_section("duration", report.analysis.by_duration_bucket)
    with tabs[5]:
        render_leaderboard(report)
    with tabs[6]:
        render_patterns(report.patterns)
    with tabs[7]:
        rec_col, limit_col = st.columns(2, gap="medium")
        # Überschrift fest oben in der Karte, nur der Text darunter scrollt
        with rec_col.container(key="card_recommendations"):
            st.markdown('<div class="card-title">Konkrete Handlungsempfehlungen</div>', unsafe_allow_html=True)
            with st.container(key="textbody_recommendations"):
                if not report.recommendations:
                    st.info("Keine automatisch generierten Empfehlungen verfügbar.")
                for number, recommendation in enumerate(report.recommendations, start=1):
                    st.markdown(
                        f'<div class="hl-item"><span class="hl-no">{number}</span>'
                        f"<div>{highlight(recommendation, lead_verb=True)}</div></div>",
                        unsafe_allow_html=True,
                    )
        with limit_col.container(key="card_limitations"):
            st.markdown('<div class="card-title">Einschränkungen der Daten</div>', unsafe_allow_html=True)
            with st.container(key="textbody_limitations"):
                all_limitations = list(report.limitations) + list(meta.limitations)
                if not all_limitations:
                    st.info("Keine besonderen Einschränkungen protokolliert.")
                for limitation in all_limitations:
                    st.markdown(
                        f'<div class="hl-item"><span class="hl-no warn">!</span><div>{highlight(limitation)}</div></div>',
                        unsafe_allow_html=True,
                    )
    with tabs[8]:
        render_data_tab(selected_dir, report)
    with tabs[9]:
        render_run_details(meta)


def render_overview(report: Report) -> None:
    analysis = report.analysis

    st.markdown('<div class="section-title">Die wichtigsten Erkenntnisse'
                '<span class="hint">je Kategorie die Gruppe mit den meisten Aufrufen</span></div>', unsafe_allow_html=True)
    insights = [
        ("red", "🏆 Top-Thema", "topic", best_group(analysis.by_topic)),
        ("blue", "🎣 Bester Einstieg", "hook", best_group(analysis.by_hook_type)),
        ("teal", "⏱️ Beste Länge", "duration", best_group(analysis.by_duration_bucket)),
    ]
    cards = []
    for color, eyebrow, kind, group in insights:
        if group is None:
            cards.append(f'<div class="tile insight {color}"><div class="eyebrow">{eyebrow}</div>'
                         '<div class="value">–</div><div class="sub">keine Daten</div></div>')
            continue
        if group.mean_retention is not None:
            number, meaning = format_percent(group.mean_retention), "des Videos im Schnitt angesehen"
        else:
            number, meaning = format_views(group.mean_views), "Aufrufe pro Video im Schnitt"
        meaning += f", aus {group.sample_size} Video{'s' if group.sample_size != 1 else ''}"
        cards.append(
            f'<div class="tile insight {color}"><div class="head"><span class="eyebrow">{eyebrow}</span>'
            f'{reliability_badge(group.is_reliable, group.sample_size)}</div>'
            f'<div class="value" title="{esc(pretty_group(group.group))}">{esc(pretty_group(group.group))}</div>'
            f'<div class="explain">{esc(group_explanation(kind, group.group))}</div>'
            f'<div class="figure"><div class="num">{esc(number)}</div><div class="what">{esc(meaning)}</div></div></div>'
        )
    st.markdown('<div class="tile-grid hero">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    if any(group is not None and not group.is_reliable for *_, group in insights):
        st.markdown(
            f'<div class="muted">○ nur Tendenz = weniger als {MIN_RELIABLE_SAMPLE_SIZE} Videos in der Gruppe: '
            "ein erster Hinweis, noch nicht gesichert.</div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Was heißt das für dich?</div>', unsafe_allow_html=True)
    reco_col, summary_col = st.columns([1, 1], gap="large")
    with reco_col.container(key="card_reco"):
        recommendation = shorten(humanize(report.recommendations[0]), 140) if report.recommendations else "–"
        more = len(report.recommendations) - 1
        st.markdown(
            '<div class="card-title">🎯 Top-Empfehlung</div>'
            f'<div class="card-text">{esc(recommendation)}</div>'
            + (f'<div class="hint">+ {more} weitere im Reiter „Empfehlungen“</div>' if more > 0 else ""),
            unsafe_allow_html=True,
        )
    with summary_col.container(key="card_summary"):
        st.markdown(
            '<div class="card-title">📝 Kernaussage</div>'
            f'<div class="card-text teaser">{esc(teaser(humanize(report.executive_summary), 280))}</div>',
            unsafe_allow_html=True,
        )
        with st.popover("Ganze Zusammenfassung lesen", type="tertiary", icon=":material/article:"):
            st.write(humanize(report.executive_summary))


@st.dialog("Alle Videos dieses Laufs", width="large")
def show_video_table(table: pd.DataFrame) -> None:
    st.caption("Sortiert nach Aufrufen. Leere Zellen: Wert nicht verfügbar. Spaltenköpfe anklicken zum Sortieren.")
    st.dataframe(
        table, use_container_width=True, hide_index=True, height=min(480, 38 + 35 * len(table)),
        column_config={
            "Platz": st.column_config.NumberColumn(width=50),
            "Titel": st.column_config.TextColumn(width="large"),
            "Video": st.column_config.LinkColumn("Video", display_text="▶ ansehen"),
            "Aufrufe": st.column_config.NumberColumn(format="localized"),
            "Likes": st.column_config.NumberColumn(format="localized"),
            "Kommentare": st.column_config.NumberColumn(format="localized"),
            "Interaktionsrate": st.column_config.NumberColumn(format="percent"),
            "Veröffentlicht": st.column_config.DateColumn(format="DD.MM.YYYY"),
        },
    )


def render_data_tab(run_dir: Path, report: Report) -> None:
    meta = report.run_metadata
    completeness = report.analysis.data_completeness
    clean_df = load_clean_data(run_dir)
    video_count = len(clean_df) if clean_df is not None else meta.videos_valid
    st.markdown(
        f'<div class="section-title">Welche Angaben gab es zu den {video_count} Videos?</div>'
        '<div class="muted" style="margin:-4px 0 12px">Je vollständiger eine Angabe, desto mehr kann man ihr trauen. '
        "Fehlende Werte werden nie geschätzt.</div>",
        unsafe_allow_html=True,
    )
    list_col, info_col = st.columns([3, 2], gap="medium")
    with list_col.container(key="card_scroll_fields"):
        if completeness:
            st.markdown(field_rows_html(completeness, video_count), unsafe_allow_html=True)
        else:
            st.info("Keine Angabe zur Vollständigkeit in diesem Lauf.")
    with info_col:
        takeaways = []
        if completeness.get("retention", 0.0) <= 0:
            takeaways.append(
                "<b>Ob Zuschauer bis zum Ende schauen, ist nicht messbar.</b> Diese Zahl gibt YouTube nur dem "
                "Besitzer des Kanals. Alle Reiter vergleichen deshalb die <b>Aufrufe</b>."
            )
        partial = [FIELD_INFO.get(k, (k,))[0] for k, v in completeness.items() if 0 < v < 1]
        if partial:
            takeaways.append(
                f"<b>{esc(', '.join(partial))}</b> fehlen bei einigen Videos, meist weil der Kanal sie "
                "ausgeblendet hat. Diese Videos zählen trotzdem bei den Aufrufen mit."
            )
        if not takeaways:
            takeaways.append("Alle Angaben sind für alle Videos vorhanden.")
        with st.container(key="card_data_meaning"):
            st.markdown(
                '<div class="card-title">💡 Was heißt das für die Ergebnisse?</div>'
                + "".join(f'<p class="card-text">{item}</p>' for item in takeaways),
                unsafe_allow_html=True,
            )
        with st.container(key="card_downloads"):
            st.markdown('<div class="card-title">⬇ Zum Weiterarbeiten herunterladen</div>', unsafe_allow_html=True)
            if clean_df is not None:
                classifications = load_classifications(run_dir)
                hook_labels, group_labels = export_labels(report)
                st.download_button(
                    "📊 Excel-Tabelle aller Videos",
                    data=excel_export.to_excel_bytes(report, clean_df, classifications, hook_labels, group_labels),
                    file_name=f"Shorts-Analyse_{meta.run_id[:8]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                    help="Aufgeräumt: ein Video pro Zeile, echte Zahlen, Links, KI-Einordnung, "
                         "dazu die Blätter „Auswertung“ und „Erklärung“.",
                )
            report_md_path = run_dir / "report.md"
            if report_md_path.exists():
                st.download_button(
                    "Ganzer Bericht als Text (Markdown)",
                    data=report_md_path.read_text(encoding="utf-8").encode("utf-8"),
                    file_name=f"{meta.run_id}_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            if clean_df is not None:
                if st.button(f"Alle {len(clean_df)} Videos als Tabelle ansehen", use_container_width=True):
                    show_video_table(excel_export.build_video_table(
                        clean_df, classifications, report.analysis.outlier_video_ids, hook_labels
                    ))



SOURCE_LABELS = {
    "public": "Öffentliche YouTube-Daten",
    "own_analytics": "Eigene YouTube-Analytics-Daten",
    "derived": "Daraus berechnete Werte",
    "unavailable": "nicht verfügbar",
}


def kpi_tile(icon: str, color: str, label: str, value: str, sub: str) -> str:
    return (f'<div class="tile kpi-tile"><div class="kpi-icon {color}">{icon}</div><div class="kpi-body">'
            f'<div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>'
            f'<div class="sub" title="{esc(sub)}">{esc(sub)}</div></div></div>')


def render_run_details(meta) -> None:
    """Lauf als kleine Geschichte: was gesucht wurde, was dabei herauskam, womit ausgewertet wurde."""
    dropped = max(meta.videos_examined - meta.videos_valid, 0)
    per_query = meta.filters.get("max_results_per_query")
    st.markdown(
        '<div class="section-title">So ist dieser Lauf abgelaufen</div>'
        '<div class="tile-grid kpi4 spaced">'
        + kpi_tile("🔍", "blue", "Gefunden", f"{meta.videos_examined} Videos", "über die YouTube-Suche")
        + kpi_tile("✅", "green", "Ausgewertet", f"{meta.videos_valid} Videos", "gingen in die Ergebnisse ein")
        + kpi_tile("🗑️", "gray", "Aussortiert", f"{dropped} Video{'' if dropped == 1 else 's'}",
                   "doppelt oder ohne verwertbare Daten")
        + kpi_tile("⏱️", "amber", "Dauer", format_duration(meta.started_at, meta.finished_at),
                   f"{format_local(meta.started_at)[-5:]} bis {format_local(meta.finished_at)[-5:]} Uhr")
        + "</div>",
        unsafe_allow_html=True,
    )

    # Drei Karten als ein HTML-Raster: gleich hoch, gleiche Abstaende wie die Kacheln darueber
    terms = "".join(f'<span class="term">„{esc(topic.split(": ", 1)[-1])}“</span>' for topic in meta.search_topics)
    categories = "".join(f'<span class="chip">{esc(c)}</span>' for c in meta.categories_used) or "–"
    search_card = (
        '<div class="card-title">🔍 Wonach gesucht wurde</div>'
        f'<div class="dl"><div class="dt">Kategorie</div><div class="dd">{categories}</div>'
        f'<div class="dt">Suchbegriffe bei YouTube</div><div class="dd terms">{terms or "–"}</div></div>'
        + (f'<div class="foot">Je Suchbegriff bis zu <b>{esc(per_query)}</b> Videos, die meistgesehenen zuerst.</div>'
           if per_query else "")
    )
    sources = ", ".join(SOURCE_LABELS.get(s.value, s.value) for s in meta.data_sources) or "–"
    tech_card = (
        '<div class="card-title">⚙️ Womit ausgewertet wurde</div><div class="dl">'
        f'<div class="dt">Datenquelle</div><div class="dd">{esc(sources)}</div>'
        f'<div class="dt">KI-Modell</div><div class="dd">{esc(meta.model_used or "–")}'
        '<div class="muted">ordnet Thema, Einstieg und Format ein und schreibt die Texte</div></div></div>'
        f'<div class="foot">Lauf-Nummer <span class="mono">{esc(meta.run_id)}</span></div>'
    )
    if not meta.errors:
        state_card = (
            '<div class="card-title">🩺 Zustand</div>'
            '<div class="all-good"><span class="big">✓</span><div><b>Ohne Fehler durchgelaufen</b>'
            '<div class="muted">Alle Schritte wurden vollständig ausgeführt.</div></div></div>'
        )
    else:
        items = "".join(f"<li>{esc(error)}</li>" for error in meta.errors)
        state_card = (f'<div class="card-title">⚠️ {len(meta.errors)} Fehler im Lauf</div>'
                      f'<ul class="error-list">{items}</ul>')
    st.markdown(
        '<div class="detail-grid">'
        + "".join(f'<div class="tile detail-card">{card}</div>' for card in (search_card, tech_card, state_card))
        + "</div>",
        unsafe_allow_html=True,
    )



def main() -> None:
    st.set_page_config(page_title="Shorts Analytics – Control Panel", page_icon="📊", layout="wide")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    PAGES["new"] = st.Page(page_new_run, title="Neuer Lauf", icon="🚀", default=True)
    PAGES["progress"] = st.Page(page_progress, title="Fortschritt", icon="⏱️", url_path="fortschritt")
    PAGES["results"] = st.Page(page_results, title="Ergebnisse", icon="📊", url_path="ergebnisse")
    PAGES["runs"] = st.Page(page_all_runs, title="Alle Läufe", icon="🗂️", url_path="laeufe")
    st.navigation(list(PAGES.values())).run()


if __name__ == "__main__":
    main()
