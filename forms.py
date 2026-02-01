from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from db import (
    add_medication,
    add_medication_name,
    add_measurement,
    fetch_medication_names,
)
from utils.time import iso_from_date_time


def render_add_measurement_form() -> None:
    st.subheader("Add temperature measurement")
    with st.form("measurement_form", clear_on_submit=True):
        today = date.today()
        now = datetime.now().time().replace(second=0, microsecond=0)
        col1, col2 = st.columns(2)
        with col1:
            d = st.date_input("Date", value=today)
        with col2:
            t = st.time_input("Time", value=now, step=60)
        temp_c = st.number_input(
            "Temperature (°C)",
            min_value=30.0,
            max_value=45.0,
            step=0.1,
            value=37.0,
            format="%.1f",
        )
        notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Add measurement")
        if submitted:
            recorded_at = iso_from_date_time(d, t)
            add_measurement(recorded_at, temp_c, notes or None)
            st.success("Measurement added.")


def render_add_medication_form() -> None:
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
        med_name = st.selectbox(
            "Medication name",
            options=name_options,
            index=0 if name_options else None,
            placeholder="Select medication",
        )
        with st.popover("Add new medication name"):
            new_name = st.text_input("New name", placeholder="e.g., Ibuprofen")
            if st.form_submit_button("Add name", use_container_width=True):
                try:
                    add_medication_name(new_name)
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
                given_at = iso_from_date_time(d, t)
                add_medication(
                    given_at,
                    str(med_name).strip(),
                    dose_desc.strip() or None,
                    notes.strip() or None,
                )
                st.success("Medication added.")

