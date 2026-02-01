from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
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

TEMP_CRITICAL = 39.8  # °C threshold for critical temperature


def _iso_from_date_time(d: date, t: time) -> str:
    dt = datetime.combine(d, t)
    # Store naive local time as ISO; simple and sufficient for local tracking
    return dt.isoformat(timespec="minutes")

def _to_iso_minutes_string(s: str) -> str:
    try:
        dt = pd.to_datetime(s)
    except Exception:
        return str(s)
    return dt.strftime("%Y-%m-%dT%H:%M")


def _render_add_measurement_form() -> None:
    st.subheader("Add temperature measurement")
    with st.form("measurement_form", clear_on_submit=True):
        today = date.today()
        now = datetime.now().time().replace(second=0, microsecond=0)
        col1, col2 = st.columns(2)
        with col1:
            d = st.date_input("Date", value=today)
        with col2:
            t = st.time_input("Time", value=now, step=60)
        temp_c = st.number_input("Temperature (°C)", min_value=30.0, max_value=45.0, step=0.1, value=37.0, format="%.1f")
        notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Add measurement")
        if submitted:
            recorded_at = _iso_from_date_time(d, t)
            add_measurement(recorded_at, temp_c, notes or None)
            st.success("Measurement added.")


def _render_add_medication_form() -> None:
    st.subheader("Add medication")
    with st.form("medication_form", clear_on_submit=True):
        today = date.today()
        now = datetime.now().time().replace(second=0, microsecond=0)
        col1, col2 = st.columns(2)
        with col1:
            d = st.date_input("Date ", value=today, key="med_date")
        with col2:
            t = st.time_input("Time ", value=now, step=60, key="med_time")
        names_df = fetch_medication_names()
        name_options = names_df["name"].tolist()
        med_name = st.selectbox("Medication name", options=name_options, index=0 if name_options else None, placeholder="Select medication")
        with st.popover("Add new medication name"):
            new_name = st.text_input("New name", placeholder="e.g., Ibuprofen")
            if st.form_submit_button("Add name", use_container_width=True):
                try:
                    new_id = add_medication_name(new_name)
                    st.success("Medication name added.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(str(e))
        dose_desc = st.text_input("Dose/amount", placeholder="e.g., 5 ml or 120 mg")
        notes = st.text_input("Notes (optional)", placeholder="e.g., after meal")
        submitted = st.form_submit_button("Add medication")
        if submitted:
            if not (med_name and str(med_name).strip()):
                st.error("Medication name is required.")
            else:
                given_at = _iso_from_date_time(d, t)
                add_medication(given_at, str(med_name).strip(), dose_desc.strip() or None, notes.strip() or None)
                st.success("Medication added.")


def _build_temperature_figure(measurements_df: pd.DataFrame, medications_df: pd.DataFrame, *, height: int = 700) -> go.Figure:
    fig = go.Figure()
    if not measurements_df.empty:
        m = measurements_df.copy()
        m["recorded_at"] = pd.to_datetime(m["recorded_at"])
        # Style markers based on critical threshold
        is_high = m["temperature_c"] >= TEMP_CRITICAL
        marker_colors = ["#d32f2f" if h else "#1976d2" for h in is_high]
        marker_sizes = [10 if h else 6 for h in is_high]
        fig.add_trace(
            go.Scatter(
                x=m["recorded_at"],
                y=m["temperature_c"],
                mode="lines+markers",
                name="Temperature (°C)",
                line=dict(color="#1976d2"),
                marker=dict(size=marker_sizes, color=marker_colors),
            )
        )
        # y_min = float(m["temperature_c"].min() * 0.95)
        # y_max = float(m["temperature_c"].max() * 1.05)
    
    y_min, y_max = 36.0, 41.0  # default bounds if empty

    # Hourly and 6-hour vertical dotted grid lines with labels
    combined_times = []
    if not measurements_df.empty:
        combined_times.append(pd.to_datetime(measurements_df["recorded_at"]))
    if not medications_df.empty:
        combined_times.append(pd.to_datetime(medications_df["given_at"]))
    if combined_times:
        tmin = min(s.min() for s in combined_times)
        tmax = max(s.max() for s in combined_times)
        start = pd.Timestamp(tmin).floor("H")
        end = pd.Timestamp(tmax).ceil("H")
        cur = start
        while cur <= end:
            # Dotted line spanning the entire plot area (paper coordinates for Y)
            fig.add_shape(
                type="line",
                x0=cur,
                x1=cur,
                y0=0,
                y1=1,
                xref="x",
                yref="paper",
                line=dict(color="rgba(0,0,0,0.25)", width=1, dash="dot"),
                layer="below",
            )
            # Labels at the bottom; larger and bolder every 6 hours
            is_major = (cur.hour % 6 == 0)
            label_text = cur.strftime("%H:%M")
            if is_major:
                label_text = f"<b>{label_text}</b>"
            fig.add_annotation(
                xref="x",
                x=cur,
                yref="paper",
                y=0,
                text=label_text,
                showarrow=False,
                font=dict(size=12 if is_major else 9, color="rgba(0,0,0,0.7)"),
                valign="bottom",
                yshift=6,
            )
            cur += pd.Timedelta(hours=1)

    # Add medication vertical markers with labels (stacked to reduce overlap)
    if not medications_df.empty:
        meds = medications_df.copy()
        meds["given_at"] = pd.to_datetime(meds["given_at"])
        meds = meds.sort_values("given_at").reset_index(drop=True)

        # Distribute labels across lanes when meds are close in time
        window_minutes = 180
        max_lanes = 3
        # Track last used time for each lane. Use None initially to avoid huge timedelta overflows.
        lane_last_time = [None] * max_lanes
        assigned_lanes = []
        for i, row in meds.iterrows():
            t = row["given_at"]
            lane_idx = None
            for li in range(max_lanes):
                last_time = lane_last_time[li]
                if last_time is None or (t - last_time).total_seconds() / 60.0 >= window_minutes:
                    lane_idx = li
                    break
            if lane_idx is None:
                lane_idx = i % max_lanes
            lane_last_time[lane_idx] = t
            assigned_lanes.append(lane_idx)

        lane_step = 0.35
        max_lane_used = 0
        hover_x = []
        hover_y = []
        hover_texts = []
        hover_ago = []

        for lane_idx, (_, row) in zip(assigned_lanes, meds.iterrows()):
            label = row["med_name"]
            if isinstance(row.get("dose_desc"), str) and row["dose_desc"]:
                label = f"{label} ({row['dose_desc']})"
            x_at = row["given_at"]
            y_for_label = y_max + 0.2 + lane_idx * lane_step
            # Dotted guide from label to x-axis
            fig.add_shape(
                type="line",
                x0=x_at,
                x1=x_at,
                y0=y_min,
                y1=y_for_label,
                xref="x",
                yref="y",
                line=dict(color="#e53935", width=2, dash="dot"),
                layer="below",
            )
            
            max_lane_used = max(max_lane_used, lane_idx)
            fig.add_annotation(
                x=x_at,
                y=y_for_label,
                text=label,
                showarrow=True,
                arrowhead=1,
                arrowsize=1,
                arrowcolor="#e53935",
                ax=0,
                ay=-(20 + lane_idx * 12),
                valign="top",
                bgcolor="rgba(229,57,53,0.05)",
                bordercolor="rgba(229,57,53,0.25)",
                borderwidth=1,
                font=dict(size=11),
            )
            # Collect invisible hover markers to show time on hover
            hover_x.append(x_at)
            hover_y.append(y_for_label)
            hover_texts.append(label)
            # Compute "time ago" string relative to now
            now_ts = pd.Timestamp.now()
            delta = now_ts - pd.Timestamp(x_at)
            if delta.total_seconds() < 0:
                ago_str = "in future"
            else:
                total_minutes = int(delta.total_seconds() // 60)
                hrs = total_minutes // 60
                mins = total_minutes % 60
                if hrs > 0 and mins > 0:
                    ago_str = f"{hrs}h{mins:02d}mins ago"
                elif hrs > 0:
                    ago_str = f"{hrs}h ago"
                elif mins > 0:
                    ago_str = f"{mins}mins ago"
                else:
                    ago_str = "just now"
            hover_ago.append(ago_str)

        # Add an invisible scatter layer to enable hover tooltips with hour/minute
        if hover_x:
            fig.add_trace(
                go.Scatter(
                    x=hover_x,
                    y=hover_y,
                    mode="markers",
                    name="Medication",
                    marker=dict(size=16, color="rgba(0,0,0,0)"),
                    hovertemplate="%{text}<br>%{x|%Y-%m-%d %H:%M}<br>%{customdata}<extra></extra>",
                    text=hover_texts,
                    customdata=hover_ago,
                    showlegend=False,
                )
            )

    # Critical temperature guideline
    fig.add_hline(y=TEMP_CRITICAL, line_dash="dash", line_color="#d32f2f", line_width=3)
    # Label on the y-axis for the critical temperature (bold, red)
    fig.add_annotation(
        xref="paper",
        x=0,
        xanchor="right",
        xshift=-16,
        yref="y",
        y=TEMP_CRITICAL,
        text=f"{TEMP_CRITICAL:.1f}°C",
        font=dict(color="#d32f2f", size=12, family=None),
        showarrow=False,
        align="right",
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        template="simple_white",
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Time",
        yaxis_title="Temperature (°C)",
    )
    # give a little headroom for annotations (account for stacked lanes)
    headroom = 0.8
    if not medications_df.empty:
        extra = 0.35 * (locals().get("max_lane_used", 0))
        headroom += extra
    fig.update_yaxes(range=[y_min - 0.5, y_max + headroom])
    return fig


def main() -> None:
    st.set_page_config(page_title="Kid Fever & Meds Tracker", page_icon="🩺", layout="wide")
    st.title("🩺 Kid Fever & Medication Tracker")
    st.caption("Track temperature measurements, medications, and visualize trends over time.")

    initialize_database()

    tabs = st.tabs(["Add data", "Visualize", "Data"])
    with tabs[0]:
        col_left, col_right = st.columns(2)
        with col_left:
            _render_add_measurement_form()
        with col_right:
            _render_add_medication_form()

    with tabs[1]:
        st.subheader("Temperature over time")
        m_df = fetch_measurements()
        meds_df = fetch_medications()
        if m_df.empty and meds_df.empty:
            st.info("No data yet. Add some measurements and medications to see the chart.")
        else:
            fig = _build_temperature_figure(m_df, meds_df)
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
                if st.button(f"Undo last delete ({count} from {tbl})", type="secondary", key="undo_delete"):
                    payload = st.session_state["last_deleted"]
                    if payload["table"] == "measurements":
                        for row in payload["rows"]:
                            add_measurement(row["recorded_at"], float(row["temperature_c"]), row.get("notes"))
                    elif payload["table"] == "medications":
                        for row in payload["rows"]:
                            add_medication(row["given_at"], row["med_name"], row.get("dose_desc"), row.get("notes"))
                    st.session_state["last_deleted"] = None
                    st.success("Restored deleted record(s).")
                    st.rerun()

        m_df = fetch_measurements()
        if not m_df.empty:
            m_df_disp = m_df.copy()
            m_df_disp["recorded_at"] = pd.to_datetime(m_df_disp["recorded_at"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(m_df_disp.sort_values("recorded_at", ascending=False), use_container_width=True, hide_index=True)
            st.download_button("Download measurements CSV", data=export_table_as_csv("measurements"), file_name="measurements.csv", mime="text/csv")
        else:
            st.info("No measurements recorded.")

        with st.expander("Delete measurements"):
            del_src = fetch_measurements()
            if del_src.empty:
                st.info("No measurements to delete.")
            else:
                df_del = del_src.copy()
                df_del["recorded_at"] = pd.to_datetime(df_del["recorded_at"]).dt.strftime("%Y-%m-%d %H:%M")
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
                        "temperature_c": st.column_config.NumberColumn("temperature_c", format="%.1f"),
                        "notes": st.column_config.TextColumn("notes", required=False),
                    },
                    key="delete_editor_measurements",
                )
                if st.button("Delete selected measurements", type="primary", key="btn_delete_measurements"):
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
                                    "recorded_at": _to_iso_minutes_string(row["recorded_at"]),
                                    "temperature_c": float(row["temperature_c"]),
                                    "notes": (str(row["notes"]).strip() if pd.notna(row["notes"]) and str(row["notes"]).strip() else None),
                                }
                                for _, row in to_delete.iterrows()
                            ],
                        }
                        # delete
                        for rid in to_delete["id"].astype(int).tolist():
                            delete_entry("measurements", int(rid))
                        st.success(f"Deleted {len(to_delete)} measurement record(s). You can undo above.")
                        st.rerun()

        st.divider()
        st.subheader("Medications")
        meds_df = fetch_medications()
        if not meds_df.empty:
            meds_df_disp = meds_df.copy()
            meds_df_disp["given_at"] = pd.to_datetime(meds_df_disp["given_at"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(meds_df_disp.sort_values("given_at", ascending=False), use_container_width=True, hide_index=True)
            st.download_button("Download medications CSV", data=export_table_as_csv("medications"), file_name="medications.csv", mime="text/csv")
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
                to_delete = edited_names[(edited_names["delete"] == True) & (edited_names["id"].notna())]  # noqa: E712
                for rid in to_delete["id"].astype(int).tolist():
                    delete_medication_name(int(rid))
                    updated += 1
                # Adds (new rows with NaN id, not marked delete, non-empty name)
                to_add = edited_names[(edited_names["id"].isna()) & (edited_names["delete"] == False) & (edited_names["name"].astype(str).str.strip() != "")]  # noqa: E712
                for _, row in to_add.iterrows():
                    try:
                        add_medication_name(str(row["name"]))
                        updated += 1
                    except Exception as e:
                        st.warning(f"Could not add '{row['name']}': {e}")
                # Updates (existing ids whose name changed)
                existing = edited_names[(edited_names["id"].notna()) & (edited_names["delete"] == False)]  # noqa: E712
                for _, row in existing.iterrows():
                    rid = int(row["id"])
                    new_name = str(row["name"]).strip()
                    if rid in orig_by_id.index and new_name and new_name != str(orig_by_id.loc[rid]["name"]):
                        try:
                            update_medication_name(rid, new_name)
                            updated += 1
                        except Exception as e:
                            st.warning(f"Could not update '{orig_by_id.loc[rid]['name']}' → '{new_name}': {e}")
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
                df_del_m["given_at"] = pd.to_datetime(df_del_m["given_at"]).dt.strftime("%Y-%m-%d %H:%M")
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
                        "dose_desc": st.column_config.TextColumn("dose_desc", required=False),
                        "notes": st.column_config.TextColumn("notes", required=False),
                    },
                    key="delete_editor_medications",
                )
                if st.button("Delete selected medications", type="primary", key="btn_delete_medications"):
                    to_delete_m = edited_del_m[edited_del_m["delete"] == True]  # noqa: E712
                    if to_delete_m.empty:
                        st.info("No rows selected.")
                    else:
                        # store undo payload
                        st.session_state["last_deleted"] = {
                            "table": "medications",
                            "rows": [
                                {
                                    "id": int(row["id"]),
                                    "given_at": _to_iso_minutes_string(row["given_at"]),
                                    "med_name": str(row["med_name"]),
                                    "dose_desc": (str(row["dose_desc"]).strip() if pd.notna(row["dose_desc"]) and str(row["dose_desc"]).strip() else None),
                                    "notes": (str(row["notes"]).strip() if pd.notna(row["notes"]) and str(row["notes"]).strip() else None),
                                }
                                for _, row in to_delete_m.iterrows()
                            ],
                        }
                        # delete
                        for rid in to_delete_m["id"].astype(int).tolist():
                            delete_entry("medications", int(rid))
                        st.success(f"Deleted {len(to_delete_m)} medication record(s). You can undo above.")
                        st.rerun()
        st.divider()
        st.subheader("Edit data")
        with st.expander("Edit measurements"):
            edit_src = fetch_measurements()
            if edit_src.empty:
                st.info("No measurements to edit.")
            else:
                editable = edit_src.copy()
                editable["recorded_at"] = pd.to_datetime(editable["recorded_at"]).dt.strftime("%Y-%m-%d %H:%M")
                edited = st.data_editor(
                    editable,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "id": st.column_config.NumberColumn("id", disabled=True, help="Record ID"),
                        "recorded_at": st.column_config.TextColumn("recorded_at", help="YYYY-MM-DD HH:MM"),
                        "temperature_c": st.column_config.NumberColumn("temperature_c", format="%.1f", min_value=30.0, max_value=45.0, step=0.1),
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
                                _to_iso_minutes_string(b.get("recorded_at")),
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
                editable_meds["given_at"] = pd.to_datetime(editable_meds["given_at"]).dt.strftime("%Y-%m-%d %H:%M")
                edited_meds = st.data_editor(
                    editable_meds,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "id": st.column_config.NumberColumn("id", disabled=True, help="Record ID"),
                        "given_at": st.column_config.TextColumn("given_at", help="YYYY-MM-DD HH:MM"),
                        "med_name": st.column_config.TextColumn("med_name"),
                        "dose_desc": st.column_config.TextColumn("dose_desc", required=False),
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
                                _to_iso_minutes_string(b.get("given_at")),
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


