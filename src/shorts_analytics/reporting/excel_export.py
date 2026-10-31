"""Excel-Export eines Laufs: aufgeraeumte Videotabelle statt Roh-CSV.

Die Roh-CSV enthaelt Kennzahlen als Text wie "{'value': 123, 'source': 'public'}",
lange Beschreibungen und technische IDs. Hier wird daraus eine lesbare Arbeitsmappe:

* Blatt "Videos"      - ein Video pro Zeile, deutsche Spaltennamen, echte Zahlen,
                        Link zum Video, KI-Einordnung (Thema, Einstieg, Format)
* Blatt "Auswertung"  - Kennzahlen je Thema / Einstieg / Format / Videolaenge
* Blatt "Erklärung"   - was jede Spalte bedeutet

Fehlende Werte bleiben leer - es wird nichts geschaetzt.
"""

from __future__ import annotations

import ast
import io
import re
from typing import Any, Iterable, Mapping

import pandas as pd

from shorts_analytics.models import ClassificationResult, GroupStats, Report

HEADER_FILL = "1F2430"
BAND_FILL = "F5F5F2"

# (Spaltenname, Erklaerung, Excel-Zahlenformat, Breite oder None = automatisch, Zeilenumbruch)
VIDEO_COLUMNS: list[tuple[str, str, str | None, int | None, bool]] = [
    ("Platz", "Rang nach Aufrufen innerhalb dieses Laufs (1 = meiste Aufrufe).", "0", 7, False),
    ("Titel", "Titel des Shorts, ohne Hashtags.", None, 50, True),
    ("Kanal", "Name des YouTube-Kanals.", None, None, False),
    ("Video", "Link zum Short auf YouTube.", None, 11, False),
    ("Veröffentlicht", "Datum der Veröffentlichung.", "DD.MM.YYYY", 14, False),
    ("Länge (Sek.)", "Dauer des Shorts in Sekunden.", "0", 12, False),
    ("Thema", "Von der KI eingeordnetes Thema.", None, None, False),
    ("Unterthema", "Genauere Einordnung durch die KI.", None, 30, True),
    ("Einstieg (Hook)", "Wie die ersten Sekunden Aufmerksamkeit holen (KI-Einordnung).", None, None, False),
    ("Format", "Art des Videos, z. B. Lied, Experiment, Story (KI-Einordnung).", None, None, False),
    ("Aufrufe", "Anzahl Aufrufe laut YouTube.", "#,##0", 16, False),
    ("Likes", "Anzahl Likes laut YouTube. Leer = vom Kanal ausgeblendet.", "#,##0", 13, False),
    ("Kommentare", "Anzahl Kommentare. Leer = Kommentare abgeschaltet oder ausgeblendet.", "#,##0", 13, False),
    ("Interaktionsrate", "(Likes + Kommentare) geteilt durch Aufrufe.", "0.00%", 15, False),
    ("Zuschauerbindung", "Anteil des Videos, den Zuschauer im Schnitt ansehen. Nur für eigene Kanäle verfügbar.", "0.0%", 17, False),
    ("Ausreißer", "„ja“ = ungewöhnlich viele Aufrufe im Vergleich zu den anderen Videos.", None, 11, False),
    ("KI-Begründung", "Warum die KI Thema, Einstieg und Format so eingeordnet hat.", None, 60, True),
]

SUMMARY_COLUMNS = ["Bereich", "Gruppe", "Videos", "Ø Aufrufe", "Mittlerer Wert (Median)", "Belastbar"]


def metric_value(cell: Any) -> float | None:
    """Liest den Zahlenwert aus "{'value': 123, 'source': 'public'}" (oder einer reinen Zahl)."""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    if isinstance(cell, dict):
        value = cell.get("value")
        return None if value is None else float(value)
    text = str(cell).strip()
    if not text:
        return None
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    return metric_value(parsed)


def clean_title(title: Any) -> str:
    """Titel ohne Hashtags und @-Erwaehnungen, Leerzeichen aufgeraeumt."""
    text = "" if title is None or (isinstance(title, float) and pd.isna(title)) else str(title)
    text = re.sub(r"[#@][\w-]+", "", text)
    text = re.sub(r"\s*[|,]\s*(?=[|,]|$)", "", text)  # leere Trenner am Ende
    return re.sub(r"\s{2,}", " ", text).strip(" |,-")


def build_video_table(
    clean_df: pd.DataFrame,
    classifications: Iterable[ClassificationResult],
    outlier_ids: Iterable[str] = (),
    hook_labels: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Eine Zeile pro Video mit lesbaren Spalten, sortiert nach Aufrufen."""
    hook_labels = hook_labels or {}
    by_id = {c.video_id: c for c in classifications}
    outliers = set(outlier_ids)
    rows = []
    for record in clean_df.to_dict("records"):
        video_id = str(record.get("video_id", ""))
        cls = by_id.get(video_id)
        views = metric_value(record.get("views"))
        likes = metric_value(record.get("likes"))
        comments = metric_value(record.get("comments"))
        engagement = metric_value(record.get("engagement_rate"))
        retention = metric_value(record.get("average_view_percentage"))
        published = pd.to_datetime(record.get("published_at"), errors="coerce", utc=True)
        hook = cls.hook_type.value if cls else None
        rows.append({
            "Titel": clean_title(record.get("title")),
            "Kanal": record.get("channel_title") or "",
            "Video": f"https://www.youtube.com/shorts/{video_id}" if video_id else "",
            "Veröffentlicht": published.tz_localize(None).date() if pd.notna(published) else None,
            "Länge (Sek.)": metric_value(record.get("duration_seconds")),
            "Thema": cls.topic if cls else record.get("search_topic"),
            "Unterthema": (cls.subtopic or "") if cls else "",
            "Einstieg (Hook)": hook_labels.get(hook, hook) if hook else "",
            "Format": cls.format_type if cls else "",
            "Aufrufe": views,
            "Likes": likes,
            "Kommentare": comments,
            "Interaktionsrate": engagement,
            # YouTube liefert Prozent (z.B. 63.5), Excel-Prozentformat erwartet 0.635
            "Zuschauerbindung": retention / 100 if retention is not None and retention > 1 else retention,
            "Ausreißer": "ja" if video_id in outliers else "",
            "KI-Begründung": cls.reasoning if cls else "",
        })
    table = pd.DataFrame(rows)
    if table.empty:
        return pd.DataFrame(columns=[c[0] for c in VIDEO_COLUMNS])
    table = table.sort_values("Aufrufe", ascending=False, na_position="last").reset_index(drop=True)
    table.insert(0, "Platz", range(1, len(table) + 1))
    # Spalten ohne einen einzigen Wert (z.B. Zuschauerbindung bei fremden Kanaelen) weglassen
    empty = [c for c in ("Zuschauerbindung", "Ausreißer") if table[c].replace("", None).isna().all()]
    return table.drop(columns=empty)


def build_summary_table(report: Report, group_labels: Mapping[str, str] | None = None) -> pd.DataFrame:
    group_labels = group_labels or {}
    sections: list[tuple[str, list[GroupStats]]] = [
        ("Thema", report.analysis.by_topic),
        ("Einstieg (Hook)", report.analysis.by_hook_type),
        ("Format", report.analysis.by_format),
        ("Videolänge", report.analysis.by_duration_bucket),
    ]
    rows = []
    for section, groups in sections:
        for g in sorted(groups, key=lambda g: g.mean_views or 0, reverse=True):
            rows.append({
                "Bereich": section,
                "Gruppe": group_labels.get(g.group, g.group),
                "Videos": g.sample_size,
                "Ø Aufrufe": g.mean_views,
                "Mittlerer Wert (Median)": g.median_views,
                "Belastbar": "ja" if g.is_reliable else "nur Tendenz",
            })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _style_sheet(ws, formats: Mapping[str, str | None], widths: Mapping[str, int | None],
                 wraps: Mapping[str, bool], table_name: str) -> None:
    """Kopfzeile, Tabellenformat mit Filter, Zahlenformate, passende Spaltenbreiten, fixierte Kopfzeile."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    headers = [cell.value for cell in ws[1]]
    for col_idx, header in enumerate(headers, start=1):
        letter = get_column_letter(col_idx)
        head = ws.cell(row=1, column=col_idx)
        head.font = Font(bold=True, color="FFFFFF")
        head.fill = PatternFill("solid", fgColor=HEADER_FILL)
        head.alignment = Alignment(vertical="center", wrap_text=True)

        values = [ws.cell(row=r, column=col_idx).value for r in range(2, ws.max_row + 1)]
        width = widths.get(header)
        if width is None:  # automatisch: laengster Inhalt, begrenzt
            longest = max([len(str(header))] + [len(str(v)) for v in values if v is not None])
            width = min(max(longest + 2, 10), 40)
        ws.column_dimensions[letter].width = width

        fmt, wrap = formats.get(header), wraps.get(header, False)
        for r in range(2, ws.max_row + 1):
            cell = ws.cell(row=r, column=col_idx)
            if fmt:
                cell.number_format = fmt
            cell.alignment = Alignment(vertical="top", wrap_text=wrap)

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "C2" if "Titel" in headers else "A2"
    if ws.max_row > 1:
        ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"
        table = Table(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
        ws.add_table(table)


def to_excel_bytes(
    report: Report,
    clean_df: pd.DataFrame,
    classifications: Iterable[ClassificationResult],
    hook_labels: Mapping[str, str] | None = None,
    group_labels: Mapping[str, str] | None = None,
) -> bytes:
    """Arbeitsmappe mit den Blaettern Videos, Auswertung und Erklärung als Bytes (fuer Download)."""
    from openpyxl.styles import Alignment, Font

    videos = build_video_table(clean_df, classifications, report.analysis.outlier_video_ids, hook_labels)
    summary = build_summary_table(report, group_labels)
    explanation = pd.DataFrame(
        [(name, text) for name, text, *_ in VIDEO_COLUMNS if name in videos.columns],
        columns=["Spalte", "Bedeutung"],
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        videos.to_excel(writer, sheet_name="Videos", index=False)
        summary.to_excel(writer, sheet_name="Auswertung", index=False)
        explanation.to_excel(writer, sheet_name="Erklärung", index=False)

        ws = writer.sheets["Videos"]
        spec = {name: (fmt, width, wrap) for name, _, fmt, width, wrap in VIDEO_COLUMNS}
        _style_sheet(ws, {k: v[0] for k, v in spec.items()}, {k: v[1] for k, v in spec.items()},
                     {k: v[2] for k, v in spec.items()}, "Videos")
        headers = [cell.value for cell in ws[1]]
        if "Video" in headers:  # Links klickbar, kurzer Text statt langer URL
            col = headers.index("Video") + 1
            for r in range(2, ws.max_row + 1):
                cell = ws.cell(row=r, column=col)
                if cell.value:
                    cell.hyperlink, cell.value = cell.value, "▶ ansehen"
                    cell.font = Font(color="1F63B5", underline="single")

        _style_sheet(writer.sheets["Auswertung"],
                     {"Ø Aufrufe": "#,##0", "Mittlerer Wert (Median)": "#,##0", "Videos": "0"},
                     {"Ø Aufrufe": 16, "Mittlerer Wert (Median)": 22}, {}, "Auswertung")

        ws = writer.sheets["Erklärung"]
        _style_sheet(ws, {}, {"Spalte": 20, "Bedeutung": 90}, {"Bedeutung": True}, "Erklaerung")
        note_row = ws.max_row + 2
        ws.cell(row=note_row, column=1, value="Hinweis").font = Font(bold=True)
        note = ws.cell(row=note_row, column=2, value=(
            f"Lauf {report.run_metadata.run_id}. Leere Zellen bedeuten: Wert nicht verfügbar – "
            "es wird nichts geschätzt. Aufrufe, Likes und Kommentare sind öffentliche YouTube-Zahlen; "
            "Thema, Einstieg und Format hat die KI aus Titel und Beschreibung eingeordnet."
        ))
        note.alignment = Alignment(wrap_text=True, vertical="top")
    return buffer.getvalue()
