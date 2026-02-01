import csv
from pathlib import Path

import pandas as pd
import pytest

import db


@pytest.fixture()
def temp_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db, raising=False)
    db.initialize_database()
    return test_db


def test_medication_names_crud(temp_db_path: Path):
    # add name
    rid = db.add_medication_name("Ibuprofen")
    names = db.fetch_medication_names()
    assert "Ibuprofen" in names["name"].tolist()
    assert rid in names["id"].astype(int).tolist()

    # update name
    db.update_medication_name(rid, "Ibuprofen 100mg")
    names2 = db.fetch_medication_names()
    assert "Ibuprofen 100mg" in names2["name"].tolist()
    assert "Ibuprofen" not in names2["name"].tolist()

    # delete name
    db.delete_medication_name(rid)
    names3 = db.fetch_medication_names()
    assert rid not in names3["id"].astype(int).tolist()


def test_measurements_crud_and_export(temp_db_path: Path):
    # add
    mid = db.add_measurement("2026-02-01T10:00", 38.2, "morning")
    df = db.fetch_measurements()
    assert len(df) == 1
    assert float(df.iloc[0]["temperature_c"]) == pytest.approx(38.2)

    # update
    db.update_measurement(mid, "2026-02-01T11:00", 37.8, None)
    df2 = db.fetch_measurements()
    assert df2.iloc[0]["recorded_at"] == "2026-02-01T11:00"
    assert float(df2.iloc[0]["temperature_c"]) == pytest.approx(37.8)
    assert pd.isna(df2.iloc[0]["notes"])

    # export CSV
    csv_text = db.export_table_as_csv("measurements")
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert len(rows) == 1
    assert rows[0]["recorded_at"] == "2026-02-01T11:00"

    # delete
    db.delete_entry("measurements", mid)
    df3 = db.fetch_measurements()
    assert df3.empty


def test_medications_crud(temp_db_path: Path):
    mid = db.add_medication("2026-02-01T12:00", "Paracetamol", "120 mg", "after meal")
    meds = db.fetch_medications()
    assert len(meds) == 1
    assert meds.iloc[0]["med_name"] == "Paracetamol"

    db.update_medication(mid, "2026-02-01T12:30", "Paracetamol", None, None)
    meds2 = db.fetch_medications()
    assert meds2.iloc[0]["given_at"] == "2026-02-01T12:30"
    assert pd.isna(meds2.iloc[0]["dose_desc"])
    assert pd.isna(meds2.iloc[0]["notes"])

    db.delete_entry("medications", mid)
    meds3 = db.fetch_medications()
    assert meds3.empty

