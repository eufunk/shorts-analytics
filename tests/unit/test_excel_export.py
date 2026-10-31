import io

import pandas as pd
import pytest

from shorts_analytics.models import ClassificationResult, HookType
from shorts_analytics.reporting.excel_export import (
    build_video_table,
    clean_title,
    metric_value,
    to_excel_bytes,
)


def raw_row(video_id: str, views: int, comments: str = "{'value': 5, 'source': 'public'}") -> dict:
    return {
        "video_id": video_id,
        "channel_title": "Kanal",
        "title": f"Video {video_id} #shorts #abc @someone",
        "description": "sehr lange Beschreibung mit Links https://example.com",
        "published_at": "2023-06-07T00:46:51Z",
        "duration_seconds": 38,
        "search_topic": "Wissen / Bildung",
        "views": f"{{'value': {views}, 'source': 'public'}}",
        "likes": "{'value': 100, 'source': 'public'}",
        "comments": comments,
        "average_view_percentage": "{'value': None, 'source': 'unavailable'}",
        "engagement_rate": "{'value': 0.01, 'source': 'derived'}",
    }


def classification(video_id: str) -> ClassificationResult:
    return ClassificationResult(video_id=video_id, topic="Wissenschaft", hook_type=HookType.SOFORTIGE_HANDLUNG,
                                format_type="Experiment", reasoning="weil")


def test_metric_value_parses_dict_strings_and_missing_values():
    assert metric_value("{'value': 2049118937, 'source': 'public'}") == 2049118937
    assert metric_value("{'value': None, 'source': 'unavailable'}") is None
    assert metric_value(None) is None
    assert metric_value(38) == 38


def test_clean_title_removes_hashtags_and_mentions():
    assert clean_title("ABC Song! 📚 #shorts #abcd @graciescorner") == "ABC Song! 📚"
    assert clean_title("New Gadgets! Cycle gadget, beauty,#shorts #short") == "New Gadgets! Cycle gadget, beauty"


def test_video_table_is_readable_sorted_and_without_raw_columns():
    df = pd.DataFrame([raw_row("a", 10), raw_row("b", 30, "{'value': None, 'source': 'unavailable'}")])
    table = build_video_table(df, [classification("a")], outlier_ids=["b"],
                              hook_labels={"sofortige_handlung": "Sofortige Handlung"})

    assert list(table["Platz"]) == [1, 2]
    assert list(table["Aufrufe"]) == [30, 10]  # meiste Aufrufe zuerst, echte Zahlen
    assert pd.isna(table.loc[0, "Kommentare"])  # fehlend bleibt leer, nicht 0
    assert table.loc[1, "Einstieg (Hook)"] == "Sofortige Handlung"
    assert table.loc[0, "Ausreißer"] == "ja"
    assert "description" not in table.columns and "Zuschauerbindung" not in table.columns


def test_excel_workbook_has_sheets_formats_and_links(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from shorts_analytics.models import AnalysisResult, Report, RunMetadata
    import datetime as dt

    report = Report(run_metadata=RunMetadata(run_id="r1", started_at=dt.datetime(2026, 10, 30)),
                    executive_summary="", analysis=AnalysisResult())
    data = to_excel_bytes(report, pd.DataFrame([raw_row("a", 1234567)]), [classification("a")])
    wb = openpyxl.load_workbook(io.BytesIO(data))

    assert wb.sheetnames == ["Videos", "Auswertung", "Erklärung"]
    ws = wb["Videos"]
    headers = [c.value for c in ws[1]]
    views = ws.cell(row=2, column=headers.index("Aufrufe") + 1)
    assert views.value == 1234567 and views.number_format == "#,##0"
    link = ws.cell(row=2, column=headers.index("Video") + 1)
    assert link.hyperlink.target == "https://www.youtube.com/shorts/a"
    assert ws.freeze_panes == "C2"
    assert ws.column_dimensions["B"].width == 50
