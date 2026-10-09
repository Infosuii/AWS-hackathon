"""Rush Threat Explorer: Streamlit entrypoint.

Layout only. Data processing lives in ``src.data``, charts in
``src.components``, and validation in ``src.validation``.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.components import render_2d_field_replay, render_proximity_timeline
from src.data import (
    DATA_DIR,
    TRACKING_COLUMNS,
    check_forward_sector,
    compute_relative_closing_speed,
    load_play_tracking,
)
from src.validation import render_validation_panel

st.set_page_config(page_title="Rush Threat Explorer", layout="wide")
st.title("Rush Threat Explorer")


@st.cache_data
def load_games() -> pd.DataFrame | None:
    """Load games.csv, or return None if it is missing."""
    path = DATA_DIR / "games.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


@st.cache_data
def load_plays() -> pd.DataFrame | None:
    """Load the plays.csv columns needed for the play selector, or None if missing."""
    path = DATA_DIR / "plays.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, usecols=["gameId", "playId", "quarter", "gameClock", "playDescription"])


# --- Sidebar -----------------------------------------------------------------
st.sidebar.header("Play Selection")

games = load_games()
plays = load_plays()

if games is None:
    st.error(f"Missing file: {DATA_DIR / 'games.csv'}")
    st.stop()
if plays is None:
    st.error(f"Missing file: {DATA_DIR / 'plays.csv'}")
    st.stop()

game_labels = {
    row.gameId: f"{row.gameId}: Wk {row.week} {row.visitorTeamAbbr} @ {row.homeTeamAbbr}"
    for row in games.itertuples(index=False)
}
game_id = st.sidebar.selectbox(
    "Game",
    options=list(game_labels),
    format_func=game_labels.get,
)

game_plays = plays[plays["gameId"] == game_id].sort_values("playId")
play_labels = {
    row.playId: f"{row.playId}: Q{row.quarter} {row.gameClock} | {row.playDescription}"
    for row in game_plays.itertuples(index=False)
}
play_id = st.sidebar.selectbox(
    "Play",
    options=list(play_labels),
    format_func=play_labels.get,
)

sector_angle = st.sidebar.slider(
    "Forward sector angle (degrees)",
    min_value=30,
    max_value=180,
    value=120,
    step=5,
)

if play_id is None:
    st.warning("No plays found for the selected game.")
    st.stop()

# --- Pipeline ----------------------------------------------------------------
df_play = load_play_tracking(game_id, play_id)
df_play = compute_relative_closing_speed(df_play)
df_play = check_forward_sector(df_play, sector_angle=sector_angle)

if df_play.empty:
    st.warning(
        "No tracking rows returned. `load_play_tracking` in src/data.py is still a placeholder."
    )

# --- Main area ---------------------------------------------------------------
tab_replay, tab_timeline, tab_validation = st.tabs(
    ["Play Replay", "Proximity Timeline", "Validation"]
)

with tab_replay:
    st.plotly_chart(render_2d_field_replay(df_play, sector_angle), width="stretch")

with tab_timeline:
    st.plotly_chart(render_proximity_timeline(df_play), width="stretch")

with tab_validation:
    render_validation_panel(pd.DataFrame(columns=TRACKING_COLUMNS))
