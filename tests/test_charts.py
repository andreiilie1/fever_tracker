import pandas as pd
import plotly.graph_objects as go

from charts import build_temperature_figure
from constants import TEMP_CRITICAL


def make_df_measurements():
    return pd.DataFrame(
        [
            {"id": 1, "recorded_at": "2026-02-01T10:00", "temperature_c": 37.2, "notes": None},
            {"id": 2, "recorded_at": "2026-02-01T12:00", "temperature_c": 39.9, "notes": "high"},
        ]
    )


def make_df_medications():
    return pd.DataFrame(
        [
            {"id": 1, "given_at": "2026-02-01T11:00", "med_name": "Paracetamol", "dose_desc": "120 mg", "notes": None},
            {"id": 2, "given_at": "2026-02-01T17:00", "med_name": "Ibuprofen", "dose_desc": None, "notes": None},
        ]
    )


def test_build_temperature_figure_basic_properties():
    fig = build_temperature_figure(make_df_measurements(), make_df_medications(), height=500)
    assert isinstance(fig, go.Figure)

    # One visible temperature trace
    names = [t.name for t in fig.data]
    assert "Temperature (°C)" in names

    # Y-axis title present
    assert fig.layout.yaxis.title.text == "Temperature (°C)"

    # Critical guideline label annotation exists
    ann_texts = [a.text for a in fig.layout.annotations]
    assert f"{TEMP_CRITICAL:.1f}°C" in ann_texts

    # Y range includes around the default floor/headroom
    yr = fig.layout.yaxis.range
    assert yr[0] <= 36.0 and yr[1] >= TEMP_CRITICAL

