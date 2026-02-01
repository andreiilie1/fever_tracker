from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from db import (
    add_medication,
    add_measurement,
    delete_entry,
    export_table_as_csv,
    fetch_medication_names,
    fetch_medications,
    fetch_measurements,
    initialize_database,
    add_medication_name,
    update_medication_name,
    delete_medication_name,
    update_medication,
    update_measurement,
)

from forms import render_add_measurement_form, render_add_medication_form
from charts import build_temperature_figure
from utils.time import to_iso_minutes_string

#
# Extracted helpers are now in dedicated modules:
# - forms: render_add_measurement_form, render_add_medication_form
# - charts: build_temperature_figure
# - utils.time: to_iso_minutes_string


def main() -> None:
    st.set_page_config(
        page_title="Kid Fever & Meds Tracker", page_icon="🩺", layout="wide"
    )
    st.title("🩺 Kid Fever & Medication Tracker")
    st.caption(
        "Track temperature measurements, medications, and visualize trends over time."
    )

    initialize_database()

    tabs = st.tabs(["Add data", "Visualize", "Data"])
    with tabs[0]:
        col_left, col_right = st.columns(2)
        with col_left:
            render_add_measurement_form()
        with col_right:
            render_add_medication_form()

    with tabs[1]:
        st.subheader("Temperature over time")
        m_df = fetch_measurements()
        meds_df = fetch_medications()
        if m_df.empty and meds_df.empty:
            st.info(
                "No data yet. Add some measurements and medications to see the chart."
            )
        else:
            fig = build_temperature_figure(m_df, meds_df)
            st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        st.subheader("Measurements")
        # Undo last delete
        if "last_deleted" not in st.session_state:
            st.session_state["last_deleted"] = None
        col_undo, _ = st.columns([1, 3])
        with col_undo:
            if st.session_state["last_deleted"] is not None:
                tbl = st.session_state["last_deleted"]["table"]
                count = len(st.session_state["last_deleted"]["rows"])
                if st.button(
                    f"Undo last delete ({count} from {tbl})",
                    type="secondary",
                    key="undo_delete",
                ):
                    payload = st.session_state["last_deleted"]
                    if payload["table"] == "measurements":
                        for row in payload["rows"]:
                            add_measurement(
                                row["recorded_at"],
                                float(row["temperature_c"]),
                                row.get("notes"),
                            )
                    elif payload["table"] == "medications":
                        for row in payload["rows"]:
                            add_medication(
                                row["given_at"],
                                row["med_name"],
                                row.get("dose_desc"),
                                row.get("notes"),
                            )
                    st.session_state["last_deleted"] = None
                    st.success("Restored deleted record(s).")
                    st.rerun()

        m_df = fetch_measurements()
        if not m_df.empty:
            m_df_disp = m_df.copy()
            m_df_disp["recorded_at"] = pd.to_datetime(
                m_df_disp["recorded_at"]
            ).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(
                m_df_disp.sort_values("recorded_at", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download measurements CSV",
                data=export_table_as_csv("measurements"),
                file_name="measurements.csv",
                mime="text/csv",
            )
        else:
            st.info("No measurements recorded.")

        with st.expander("Delete measurements"):
            del_src = fetch_measurements()
            if del_src.empty:
                st.info("No measurements to delete.")
            else:
                df_del = del_src.copy()
                df_del["recorded_at"] = pd.to_datetime(
                    df_del["recorded_at"]
                ).dt.strftime("%Y-%m-%d %H:%M")
                df_del.insert(0, "delete", False)
                edited_del = st.data_editor(
                    df_del,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "delete": st.column_config.CheckboxColumn("delete"),
                        "id": st.column_config.NumberColumn("id", disabled=True),
                        "recorded_at": st.column_config.TextColumn("recorded_at"),
                        "temperature_c": st.column_config.NumberColumn(
                            "temperature_c", format="%.1f"
                        ),
                        "notes": st.column_config.TextColumn("notes", required=False),
                    },
                    key="delete_editor_measurements",
                )
                if st.button(
                    "Delete selected measurements",
                    type="primary",
                    key="btn_delete_measurements",
                ):
                    to_delete = edited_del[edited_del["delete"] == True]  # noqa: E712
                    if to_delete.empty:
                        st.info("No rows selected.")
                    else:
                        # store undo payload
                        st.session_state["last_deleted"] = {
                            "table": "measurements",
                            "rows": [
                                {
                                    "id": int(row["id"]),
                                    "recorded_at": to_iso_minutes_string(
                                        row["recorded_at"]
                                    ),
                                    "temperature_c": float(row["temperature_c"]),
                                    "notes": (
                                        str(row["notes"]).strip()
                                        if pd.notna(row["notes"])
                                        and str(row["notes"]).strip()
                                        else None
                                    ),
                                }
                                for _, row in to_delete.iterrows()
                            ],
                        }
                        # delete
                        for rid in to_delete["id"].astype(int).tolist():
                            delete_entry("measurements", int(rid))
                        st.success(
                            f"Deleted {len(to_delete)} measurement record(s). You can undo above."
                        )
                        st.rerun()

        st.divider()
        st.subheader("Medications")
        meds_df = fetch_medications()
        if not meds_df.empty:
            meds_df_disp = meds_df.copy()
            meds_df_disp["given_at"] = pd.to_datetime(
                meds_df_disp["given_at"]
            ).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(
                meds_df_disp.sort_values("given_at", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download medications CSV",
                data=export_table_as_csv("medications"),
                file_name="medications.csv",
                mime="text/csv",
            )
        else:
            st.info("No medications recorded.")

        with st.expander("Manage medication names"):
            names_df = fetch_medication_names()
            if names_df.empty:
                st.info("No medication names saved yet. Add some below.")
            df_names = names_df.copy()
            df_names.insert(0, "delete", False)
            edited_names = st.data_editor(
                df_names,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "delete": st.column_config.CheckboxColumn("delete"),
                    "id": st.column_config.NumberColumn("id", disabled=True),
                    "name": st.column_config.TextColumn("name", help="Medication name"),
                },
                key="editor_medication_names",
            )
            if st.button("Apply changes to names"):
                orig_by_id = df_names.set_index("id")
                updated = 0
                # Deletes
                to_delete = edited_names[
                    (edited_names["delete"] == True) & (edited_names["id"].notna())
                ]  # noqa: E712
                for rid in to_delete["id"].astype(int).tolist():
                    delete_medication_name(int(rid))
                    updated += 1
                # Adds (new rows with NaN id, not marked delete, non-empty name)
                to_add = edited_names[
                    (edited_names["id"].isna())
                    & (edited_names["delete"] == False)
                    & (edited_names["name"].astype(str).str.strip() != "")
                ]  # noqa: E712
                for _, row in to_add.iterrows():
                    try:
                        add_medication_name(str(row["name"]))
                        updated += 1
                    except Exception as e:
                        st.warning(f"Could not add '{row['name']}': {e}")
                # Updates (existing ids whose name changed)
                existing = edited_names[
                    (edited_names["id"].notna()) & (edited_names["delete"] == False)
                ]  # noqa: E712
                for _, row in existing.iterrows():
                    rid = int(row["id"])
                    new_name = str(row["name"]).strip()
                    if (
                        rid in orig_by_id.index
                        and new_name
                        and new_name != str(orig_by_id.loc[rid]["name"])
                    ):
                        try:
                            update_medication_name(rid, new_name)
                            updated += 1
                        except Exception as e:
                            st.warning(
                                f"Could not update '{orig_by_id.loc[rid]['name']}' → '{new_name}': {e}"
                            )
                if updated:
                    st.success(f"Applied {updated} change(s) to medication names.")
                    st.rerun()
                else:
                    st.info("No changes to apply.")

        with st.expander("Delete medications"):
            del_src_m = fetch_medications()
            if del_src_m.empty:
                st.info("No medications to delete.")
            else:
                df_del_m = del_src_m.copy()
                df_del_m["given_at"] = pd.to_datetime(df_del_m["given_at"]).dt.strftime(
                    "%Y-%m-%d %H:%M"
                )
                df_del_m.insert(0, "delete", False)
                edited_del_m = st.data_editor(
                    df_del_m,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "delete": st.column_config.CheckboxColumn("delete"),
                        "id": st.column_config.NumberColumn("id", disabled=True),
                        "given_at": st.column_config.TextColumn("given_at"),
                        "med_name": st.column_config.TextColumn("med_name"),
                        "dose_desc": st.column_config.TextColumn(
                            "dose_desc", required=False
                        ),
                        "notes": st.column_config.TextColumn("notes", required=False),
                    },
                    key="delete_editor_medications",
                )
                if st.button(
                    "Delete selected medications",
                    type="primary",
                    key="btn_delete_medications",
                ):
                    to_delete_m = edited_del_m[
                        edited_del_m["delete"] == True
                    ]  # noqa: E712
                    if to_delete_m.empty:
                        st.info("No rows selected.")
                    else:
                        # store undo payload
                        st.session_state["last_deleted"] = {
                            "table": "medications",
                            "rows": [
                                {
                                    "id": int(row["id"]),
                                    "given_at": to_iso_minutes_string(row["given_at"]),
                                    "med_name": str(row["med_name"]),
                                    "dose_desc": (
                                        str(row["dose_desc"]).strip()
                                        if pd.notna(row["dose_desc"])
                                        and str(row["dose_desc"]).strip()
                                        else None
                                    ),
                                    "notes": (
                                        str(row["notes"]).strip()
                                        if pd.notna(row["notes"])
                                        and str(row["notes"]).strip()
                                        else None
                                    ),
                                }
                                for _, row in to_delete_m.iterrows()
                            ],
                        }
                        # delete
                        for rid in to_delete_m["id"].astype(int).tolist():
                            delete_entry("medications", int(rid))
                        st.success(
                            f"Deleted {len(to_delete_m)} medication record(s). You can undo above."
                        )
                        st.rerun()
        st.divider()
        st.subheader("Edit data")
        with st.expander("Edit measurements"):
            edit_src = fetch_measurements()
            if edit_src.empty:
                st.info("No measurements to edit.")
            else:
                editable = edit_src.copy()
                editable["recorded_at"] = pd.to_datetime(
                    editable["recorded_at"]
                ).dt.strftime("%Y-%m-%d %H:%M")
                edited = st.data_editor(
                    editable,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "id": st.column_config.NumberColumn(
                            "id", disabled=True, help="Record ID"
                        ),
                        "recorded_at": st.column_config.TextColumn(
                            "recorded_at", help="YYYY-MM-DD HH:MM"
                        ),
                        "temperature_c": st.column_config.NumberColumn(
                            "temperature_c",
                            format="%.1f",
                            min_value=30.0,
                            max_value=45.0,
                            step=0.1,
                        ),
                        "notes": st.column_config.TextColumn("notes", required=False),
                    },
                    key="editor_measurements",
                )
                if st.button("Save measurement changes"):
                    orig_by_id = editable.set_index("id")
                    edited_by_id = edited.set_index("id")
                    updated_count = 0
                    for rid in orig_by_id.index:
                        a = orig_by_id.loc[rid]
                        b = edited_by_id.loc[rid]
                        if not a.equals(b):
                            notes_val = None
                            if pd.notna(b.get("notes")):
                                txt = str(b.get("notes")).strip()
                                notes_val = txt or None
                            update_measurement(
                                int(rid),
                                to_iso_minutes_string(b.get("recorded_at")),
                                float(b.get("temperature_c")),
                                notes_val,
                            )
                            updated_count += 1
                    if updated_count:
                        st.success(f"Updated {updated_count} measurement record(s).")
                        st.rerun()
                    else:
                        st.info("No changes to save.")

        with st.expander("Edit medications"):
            edit_src_meds = fetch_medications()
            if edit_src_meds.empty:
                st.info("No medications to edit.")
            else:
                editable_meds = edit_src_meds.copy()
                editable_meds["given_at"] = pd.to_datetime(
                    editable_meds["given_at"]
                ).dt.strftime("%Y-%m-%d %H:%M")
                edited_meds = st.data_editor(
                    editable_meds,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "id": st.column_config.NumberColumn(
                            "id", disabled=True, help="Record ID"
                        ),
                        "given_at": st.column_config.TextColumn(
                            "given_at", help="YYYY-MM-DD HH:MM"
                        ),
                        "med_name": st.column_config.TextColumn("med_name"),
                        "dose_desc": st.column_config.TextColumn(
                            "dose_desc", required=False
                        ),
                        "notes": st.column_config.TextColumn("notes", required=False),
                    },
                    key="editor_medications",
                )
                if st.button("Save medication changes"):
                    orig_by_id_m = editable_meds.set_index("id")
                    edited_by_id_m = edited_meds.set_index("id")
                    updated_count_m = 0
                    for rid in orig_by_id_m.index:
                        a = orig_by_id_m.loc[rid]
                        b = edited_by_id_m.loc[rid]
                        if not a.equals(b):
                            dose_val = None
                            if pd.notna(b.get("dose_desc")):
                                dtxt = str(b.get("dose_desc")).strip()
                                dose_val = dtxt or None
                            notes_val = None
                            if pd.notna(b.get("notes")):
                                ntxt = str(b.get("notes")).strip()
                                notes_val = ntxt or None
                            update_medication(
                                int(rid),
                                to_iso_minutes_string(b.get("given_at")),
                                str(b.get("med_name")).strip(),
                                dose_val,
                                notes_val,
                            )
                            updated_count_m += 1
                    if updated_count_m:
                        st.success(f"Updated {updated_count_m} medication record(s).")
                        st.rerun()
                    else:
                        st.info("No changes to save.")


if __name__ == "__main__":
    main()
