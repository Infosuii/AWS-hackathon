"""Validation metrics for Rush Threat Explorer.

Owner module for validation metrics. Checks whether the rush threat metrics
from ``src.data`` (closing speed, forward-sector time) track real outcomes.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_validation_panel(df_all_plays: pd.DataFrame) -> None:
    """Render the validation panel in the current Streamlit container.

    Intended implementation:
        - Aggregate per-rusher, per-play metrics (e.g. peak ``closing_speed``,
          frames with ``in_forward_sector`` True).
        - Join outcomes from ``pffScoutingData.csv`` (``pff_hit``,
          ``pff_hurry``, ``pff_sack``) on ``gameId``, ``playId``, ``nflId``,
          and play-level ``passResult == "S"`` from ``plays.csv``.
        - Report correlations / AUC of threat metrics vs. pressure and sack,
          with supporting Plotly charts.

    Args:
        df_all_plays: Processed tracking rows across many plays, following
            ``TRACKING_COLUMNS`` plus ``closing_speed`` and
            ``in_forward_sector``.

    Returns:
        None. Renders directly to Streamlit.
    """
    # TODO: Compute metrics vs. pressure/sack outcomes and render charts.
    st.subheader("Validation Metrics")
    st.info(
        "Validation metrics are not implemented yet. This panel will correlate "
        "rush threat metrics with pressure and sack outcomes from PFF scouting data."
    )
