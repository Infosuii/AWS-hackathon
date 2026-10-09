"""Synchronized replay from the frozen players/threats/metadata bundle.

Coordinates remain native yards. Orientation is a player heading, not gaze.
The figure is deliberately independent of data loading and app infrastructure.
"""

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


_COLORS = ("#ff6b6b", "#f9c74f", "#b695ff", "#4dd9d2", "#ff9f43",
           "#f58ed1", "#a3d977", "#79b8ff", "#e3a981", "#d1cf66")
_ROLES = {
    "qb": ("QB", "#ffffff", "star", 24),
    "blocker": ("Blocker", "#66b9ff", "square", 21),
    "route": ("Route", "#9bddff", "circle", 21),
    "coverage": ("Coverage", "#aaaec3", "diamond", 21),
    "other": ("Other", "#c6cbd3", "circle", 21),
    "ball": ("Football", "#a96937", "diamond", 11),
}


def select_alert(frame_threats: pd.DataFrame, radius_yd: float = 5.0):
    """Fastest finite, positively closing rusher within radius (ties: nflId).

    Sector membership never gates selection. Return the original row or None.
    """
    if frame_threats.empty:
        return None
    speed = pd.to_numeric(frame_threats["closing_speed"], errors="coerce")
    distance = pd.to_numeric(frame_threats["distance"], errors="coerce")
    valid = (np.isfinite(speed) & (speed > 0) & np.isfinite(distance)
             & (distance >= 0) & (distance <= radius_yd))
    candidates = frame_threats.loc[valid].copy()
    if candidates.empty:
        return None
    candidates["_speed"] = speed.loc[valid]
    candidates["_id"] = pd.to_numeric(candidates["nflId"], errors="coerce")
    position = candidates.sort_values(
        ["_speed", "_id"], ascending=[False, True], kind="stable"
    ).iloc[0]
    return position.drop(labels=["_speed", "_id"])


def _finite(value):
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _label(value):
    if pd.isna(value):
        return "?"
    if isinstance(value, (float, np.floating)) and value.is_integer():
        return str(int(value))
    return escape(str(value))


def _sector(qb, sector_deg):
    """Seven-yard display wedge, clockwise from +y: (sin, cos)."""
    if qb is None or not all(_finite(qb[k]) for k in ("x", "y", "o")):
        return [], []
    angles = np.deg2rad(np.linspace(qb["o"] - sector_deg / 2,
                                    qb["o"] + sector_deg / 2, 61))
    return ([float(qb["x"])] + (qb["x"] + 7 * np.sin(angles)).tolist()
            + [float(qb["x"])],
            [float(qb["y"])] + (qb["y"] + 7 * np.cos(angles)).tolist()
            + [float(qb["y"])])


def _range(values, default, padding):
    values = pd.to_numeric(values, errors="coerce")
    values = values[np.isfinite(values)]
    if values.empty:
        return default
    return [min(default[0], float(values.min()) - padding),
            max(default[1], float(values.max()) + padding)]


def build_figure(bundle: dict) -> go.Figure:
    """Build field + distance/speed panels with explicit animation trace maps.

    Replay frames are the sorted union of observed players/threats frameIds.
    Each frame clears absent entities; transitions have zero duration. Timeline
    gaps are inserted for absent frame/entity observations and never connected.
    ``layout.meta.dynamic_traces`` exposes the stable trace map for inspection.
    """
    players, threats, metadata = (bundle[k] for k in ("players", "threats", "metadata"))
    fig = make_subplots(rows=2, cols=2, specs=[[{"rowspan": 2}, {}], [None, {}]],
                        column_widths=[0.62, 0.38], horizontal_spacing=0.09,
                        vertical_spacing=0.17,
                        subplot_titles=("Tracking · native field coordinates",
                                        "Distance to QB", "Closing speed · smoothed"))
    dynamic = {}

    def add_dynamic(key, trace, row=1, col=1):
        dynamic[key] = len(fig.data)
        fig.add_trace(trace, row=row, col=col)

    add_dynamic("wedge", go.Scatter(x=[], y=[], mode="lines", fill="toself",
                fillcolor="rgba(135,206,250,0.18)", line=dict(color="#85caff", width=1),
                name="Assumed forward sector", hoverinfo="skip", showlegend=False))
    rusher_ids = sorted(pd.concat([players.loc[players.role == "rusher", "nflId"],
                                   threats["nflId"]]).dropna().unique(), key=float)
    colors = {nfl_id: _COLORS[i % len(_COLORS)] for i, nfl_id in enumerate(rusher_ids)}
    entities = []
    for role, (name, color, symbol, size) in _ROLES.items():
        entities.append((role, None))
        add_dynamic(role, go.Scatter(x=[], y=[], mode="markers+text", name=name,
                    marker=dict(color=color, symbol=symbol, size=size,
                                line=dict(color="#172839", width=1.5)),
                    textfont=dict(size=11, color="#ffffff" if role == "qb" else "#172839"),
                    textposition="top center" if role == "qb" else "middle center",
                    hovertemplate="%{customdata[0]}<br>%{customdata[1]} · #%{customdata[2]}"
                                  "<br>x %{x:.2f} yd · y %{y:.2f} yd<extra></extra>"))
    for nfl_id in rusher_ids:
        entities.append(("rusher", nfl_id))
        samples = threats.loc[threats.nflId == nfl_id]
        if samples.empty:
            samples = players.loc[players.nflId == nfl_id]
        jersey = _label(samples.iloc[0].jerseyNumber)
        add_dynamic(f"rusher:{nfl_id}", go.Scatter(x=[], y=[], mode="markers+text",
                    name=f"Rusher #{jersey}", legendgroup=str(nfl_id),
                    marker=dict(color=colors[nfl_id], size=23,
                                line=dict(color="#172839", width=1.5)),
                    textfont=dict(size=11, color="#172839"), textposition="middle center",
                    hovertemplate="%{customdata[0]} · #%{customdata[2]}"
                                  "<br>x %{x:.2f} yd · y %{y:.2f} yd<extra></extra>"))
    add_dynamic("alert", go.Scatter(x=[], y=[], mode="lines", name="Current alert",
                line=dict(color="#ffd76a", width=4), hoverinfo="skip", showlegend=False))

    frame_ids = sorted(set(players.frameId.dropna()) | set(threats.frameId.dropna()))
    frame_times = {}
    for table in (players, threats):
        for frame_id, group in table.groupby("frameId", sort=True):
            finite = group.time_from_snap.map(_finite)
            if finite.any():
                frame_times.setdefault(frame_id, float(group.loc[finite, "time_from_snap"].iloc[0]))
    snap = metadata.get("snap_frame")
    origin = snap if _finite(snap) else (frame_ids[0] if frame_ids else 0)
    for frame_id in frame_ids:
        frame_times.setdefault(frame_id, (frame_id - origin) / 10)
    time_range = _range(pd.Series(list(frame_times.values()), dtype=float), [0, 0.1], 0.08)
    distance_range = _range(threats.distance, [0, 6], 1)
    distance_range[0] = 0
    speed_range = _range(threats.closing_speed, [-1, 1], 0.8)

    # Full integer frame grid makes even globally missing observations visible as gaps.
    grid = list(range(int(frame_ids[0]), int(frame_ids[-1]) + 1)) if frame_ids else []
    grid_times = [frame_times.get(frame, (frame - origin) / 10) for frame in grid]
    for nfl_id in rusher_ids:
        observed = threats.loc[threats.nflId == nfl_id].set_index("frameId").reindex(grid)
        for row, metric in ((1, "distance"), (2, "closing_speed")):
            units = "yards" if row == 1 else "yards/second"
            fig.add_trace(go.Scatter(x=grid_times, y=observed[metric], mode="lines",
                          line=dict(color=colors[nfl_id], width=2), connectgaps=False,
                          name=f"Rusher #{_label(observed.jerseyNumber.dropna().iloc[0])}"
                               if observed.jerseyNumber.notna().any() else "Rusher",
                          legendgroup=str(nfl_id), showlegend=False,
                          hovertemplate=f"t %{{x:.2f}} s<br>{metric.replace('_', ' ')} "
                                        f"%{{y:.2f}} {units}<extra>%{{fullData.name}}</extra>"),
                          row=row, col=2)
    for key, row, limits in (("distance_cursor", 1, distance_range),
                              ("speed_cursor", 2, speed_range)):
        add_dynamic(key, go.Scatter(x=[], y=limits, mode="lines", showlegend=False,
                    name="Replay time", hoverinfo="skip",
                    line=dict(color="#f5f8ff", width=2, dash="dot")), row, 2)
    fig.add_hline(y=5, row=1, col=2, line=dict(color="#ffd76a", dash="dash"),
                  annotation_text="5 yd alert radius", annotation_position="bottom right")
    fig.add_hline(y=0, row=2, col=2, line=dict(color="#627388", width=1))

    terminal = metadata.get("terminal_frame")
    if _finite(terminal):
        terminal_time = frame_times.get(terminal, (terminal - origin) / 10)
        for row in (1, 2):
            fig.add_vline(x=terminal_time, row=row, col=2,
                          line=dict(color="#bbc5d6", width=1, dash="dash"))
        fig.add_annotation(x=terminal_time, y=1.03, xref="x2", yref="y2 domain",
                           text=f"Terminal · {escape(str(metadata.get('terminal_event') or 'event'))}",
                           showarrow=False, xanchor="right", font=dict(size=10))

    alerts = [select_alert(group) for _, group in threats.groupby("frameId", sort=True)]
    alerts = [alert for alert in alerts if alert is not None]
    if alerts:
        peak = sorted(alerts, key=lambda r: (-float(r.closing_speed), float(r.frameId), float(r.nflId)))[0]
        for row, metric in ((1, "distance"), (2, "closing_speed")):
            fig.add_trace(go.Scatter(x=[frame_times[peak.frameId]], y=[peak[metric]],
                          mode="markers", marker=dict(symbol="diamond", size=12,
                          color=colors[peak.nflId], line=dict(color="white", width=2)),
                          name="Peak qualifying alert", showlegend=row == 1,
                          legendgroup="peak", hovertemplate="Peak qualifying alert"
                          "<br>t %{x:.2f} s<br>%{y:.2f} "
                          + ("yards" if row == 1 else "yards/second") + "<extra></extra>"),
                          row=row, col=2)

    # Native-coordinate field markings; no transform or mirror.
    fig.add_shape(type="rect", x0=0, x1=120, y0=0, y1=53.3, xref="x", yref="y",
                  fillcolor="#173d32", line=dict(color="#cce1d5"), layer="below")
    for yard in range(10, 111, 5):
        fig.add_shape(type="line", x0=yard, x1=yard, y0=0, y1=53.3,
                      xref="x", yref="y", line=dict(color="rgba(230,245,235,0.25)",
                      width=1 if yard % 10 else 2), layer="below")
    for yard in range(10, 111, 10):
        fig.add_annotation(x=yard, y=3, xref="x", yref="y", showarrow=False,
                           text=str(min(yard - 10, 110 - yard)), font=dict(color="#94ad9d", size=11))
    finite_positions = players.loc[players.x.map(_finite) & players.y.map(_finite)]
    if finite_positions.empty:
        field_x, field_y = [0, 120], [0, 53.3]
    else:
        field_x = [max(0, float(finite_positions.x.min()) - 9),
                   min(120, float(finite_positions.x.max()) + 9)]
        field_y = [max(0, float(finite_positions.y.min()) - 9),
                   min(53.3, float(finite_positions.y.max()) + 9)]
    fig.update_xaxes(range=field_x, title_text="Native x (yards)", showgrid=False,
                     zeroline=False, constrain="domain", row=1, col=1)
    fig.update_yaxes(range=field_y, title_text="Native y (yards)", showgrid=False,
                     zeroline=False, scaleanchor="x", scaleratio=1,
                     constrain="domain", row=1, col=1)
    for row, limits, title in ((1, distance_range, "Distance (yards)"),
                                (2, speed_range, "Closing speed (yards/second)")):
        fig.update_xaxes(range=time_range, matches="x2" if row == 2 else None,
                         title_text="Time from snap (seconds)" if row == 2 else None,
                         row=row, col=2)
        fig.update_yaxes(range=limits, title_text=title, row=row, col=2)

    sector_deg = metadata["sector_deg"]
    base_annotations = list(fig.layout.annotations)
    frames = []
    for frame_id in frame_ids:
        current = players.loc[players.frameId == frame_id]
        current_threats = threats.loc[threats.frameId == frame_id]
        qb_rows = current.loc[current.role == "qb"]
        qb = qb_rows.iloc[0] if len(qb_rows) == 1 else None
        updates = {"wedge": go.Scatter(x=[], y=[])}
        wedge_x, wedge_y = _sector(qb, sector_deg)
        updates["wedge"] = go.Scatter(x=wedge_x, y=wedge_y)
        for role, nfl_id in entities:
            rows = current.loc[current.role == role]
            if nfl_id is not None:
                rows = rows.loc[rows.nflId == nfl_id]
            rows = rows.loc[rows.x.map(_finite) & rows.y.map(_finite)]
            key = role if nfl_id is None else f"rusher:{nfl_id}"
            text = ([""] * len(rows) if role == "ball" else
                    [f"QB {_label(j)}" if role == "qb" else _label(j) for j in rows.jerseyNumber])
            custom = [[escape(str(r.displayName)), role, _label(r.jerseyNumber)]
                      for _, r in rows.iterrows()]
            updates[key] = go.Scatter(x=rows.x.tolist(), y=rows.y.tolist(),
                                      text=text, customdata=custom)
        alert = select_alert(current_threats)
        if alert is None:
            updates["alert"] = go.Scatter(x=[], y=[])
            alert_text = "No qualifying alert · positive closing speed within 5 yards required"
        else:
            coordinates = [alert[k] for k in ("qb_x", "qb_y", "x", "y")]
            line_x, line_y = ([alert.qb_x, alert.x], [alert.qb_y, alert.y]) \
                if all(_finite(v) for v in coordinates) else ([], [])
            updates["alert"] = go.Scatter(x=line_x, y=line_y,
                                          line=dict(color=colors[alert.nflId], width=4))
            status = "unknown"
            if (wedge_x and _finite(alert.qb_o) and _finite(alert.bearing_deg)
                    and not pd.isna(alert.outside_sector)):
                status = "outside" if bool(alert.outside_sector) else "inside"
            alert_text = (f"Alert · #{_label(alert.jerseyNumber)} {escape(str(alert.displayName))}"
                          f" · {alert.distance:.2f} yd · +{alert.closing_speed:.2f} yd/s"
                          f"<br>{status.capitalize()} assumed forward sector")
        orientation_text = (f"Assumed forward sector {sector_deg:g}° · orientation, not gaze"
                            if wedge_x else "Assumed forward sector unknown · missing QB orientation/position")
        now = frame_times[frame_id]
        for key in ("distance_cursor", "speed_cursor"):
            updates[key] = go.Scatter(x=[now, now],
                                      y=distance_range if key == "distance_cursor" else speed_range)
        annotations = base_annotations + [go.layout.Annotation(
            x=0, y=-0.1, xref="paper", yref="paper", xanchor="left", yanchor="top",
            showarrow=False, align="left", font=dict(size=12),
            text=f"Frame {int(frame_id)} · t {now:.2f} s<br>{orientation_text}<br>{alert_text}")]
        frames.append(go.Frame(name=str(int(frame_id)),
                      data=[updates[key] for key in dynamic], traces=list(dynamic.values()),
                      layout=go.Layout(annotations=annotations)))
    if frames:
        for index, trace in zip(frames[0].traces, frames[0].data):
            fig.data[index].update(trace.to_plotly_json())
        fig.update_layout(annotations=frames[0].layout.annotations)
    else:
        fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                           text=escape(str(metadata.get("replay_note") or "Replay unavailable")))
    fig.frames = frames
    immediate = dict(mode="immediate", frame=dict(duration=0, redraw=True),
                     transition=dict(duration=0))
    fig.update_layout(
        template="plotly_dark", height=830, autosize=True,
        title=dict(text=f"Rush Threat Explorer · Play {_label(metadata.get('playId'))}"
                        f"<br><sup>{escape(str(metadata.get('playDescription') or ''))}</sup>",
                   font=dict(size=19), x=0.02),
        margin=dict(l=60, r=35, t=110, b=280),
        legend=dict(orientation="h", x=0, y=-0.48, xanchor="left", yanchor="top",
                    font=dict(size=11)),
        hovermode="closest", uirevision=f"{metadata.get('gameId')}-{metadata.get('playId')}",
        meta=dict(dynamic_traces=dynamic, sector_display_radius_yd=7,
                  coordinate_convention="native x/y yards; angle (sin, cos)"),
        sliders=[dict(active=0, x=0.14, len=0.86, y=-0.29,
                      currentvalue=dict(prefix="Frame "), pad=dict(t=8),
                      steps=[dict(label=str(int(fid)), method="animate",
                                  args=[[str(int(fid))], immediate]) for fid in frame_ids])],
        updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.29,
                         showactive=False, buttons=[
            dict(label="▶", method="animate", args=[None, dict(
                fromcurrent=True, mode="immediate", frame=dict(duration=100, redraw=True),
                transition=dict(duration=0))]),
            dict(label="Ⅱ", method="animate", args=[[None], immediate])])],
    )
    return fig
