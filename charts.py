from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from constants import TEMP_CRITICAL


def build_temperature_figure(
    measurements_df: pd.DataFrame, medications_df: pd.DataFrame, *, height: int = 700
) -> go.Figure:
    fig = go.Figure()
    y_min, y_max = 36.0, 41.0  # default bounds if empty

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
            is_major = cur.hour % 6 == 0
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
                if (
                    last_time is None
                    or (t - last_time).total_seconds() / 60.0 >= window_minutes
                ):
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
