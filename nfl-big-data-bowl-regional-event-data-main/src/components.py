"""Plotly chart builders for Rush Threat Explorer.

Owner module for Plotly charts. Functions take preprocessed play DataFrames
(see ``src.data``) and return ``plotly.graph_objects.Figure`` objects; they do
not call Streamlit directly.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

FIELD_LENGTH: float = 120.0
FIELD_WIDTH: float = 53.3


def _placeholder_annotation(fig: go.Figure) -> go.Figure:
    """Add a centered "Not implemented yet" annotation to ``fig``."""
    fig.add_annotation(
        text="Not implemented yet",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 18},
    )
    return fig


def render_2d_field_replay(df_play: pd.DataFrame, sector_angle: float) -> go.Figure:
    """Build an animated top-down field replay of a single play.

    Intended visual:
        - Field drawn on x in [0, 120] and y in [0, 53.3] yards, equal aspect.
        - One marker per player (colored by ``club``, hover with
          ``displayName`` and ``pff_role``) plus the football.
        - Animation frames keyed on ``frameId`` with a play/pause button and
          a frame slider.
        - For each pass rusher, a translucent wedge of width ``sector_angle``
          centered on their heading (``dir``/``o``), highlighted when
          ``in_forward_sector`` is True.

    Args:
        df_play: Play DataFrame after ``compute_relative_closing_speed`` and
            ``check_forward_sector``.
        sector_angle: Full width of the rusher forward wedge in degrees.

    Returns:
        Plotly Figure. Placeholder returns an empty field with a
        "Not implemented yet" annotation.
    """
    # TODO: Build player traces, sector wedges, and frameId animation.
    fig = go.Figure()
    fig.update_layout(
        title=f"2D Field Replay (sector angle: {sector_angle}°)",
        xaxis={"range": [0, FIELD_LENGTH], "title": "x (yards)"},
        yaxis={"range": [0, FIELD_WIDTH], "title": "y (yards)"},
    )
    return _placeholder_annotation(fig)


def render_proximity_timeline(df_play: pd.DataFrame) -> go.Figure:
    """Build a per-rusher proximity / closing-speed timeline for a play.

    Intended visual:
        - x-axis: ``frameId`` (time within the play).
        - One line per pass rusher showing distance to the QB, with a
          secondary y-axis for ``closing_speed``.
        - Shaded spans where ``in_forward_sector`` is True.

    Args:
        df_play: Play DataFrame after ``compute_relative_closing_speed`` and
            ``check_forward_sector``.

    Returns:
        Plotly Figure. Placeholder returns an empty chart with a
        "Not implemented yet" annotation.
    """
    # TODO: Build per-rusher distance and closing-speed traces.
    fig = go.Figure()
    fig.update_layout(
        title="Proximity Timeline",
        xaxis={"title": "frameId"},
        yaxis={"title": "Distance to QB (yards)"},
    )
    return _placeholder_annotation(fig)
