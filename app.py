"""Rush Threat Explorer - Streamlit app (run: streamlit run app.py)."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from rush_threat import validation as V

APP_DIR = Path(__file__).resolve().parent
DEFAULT_PLAY = (2021090900, 97)
DATA_CANDIDATES = [APP_DIR / "nfl-big-data-bowl-regional-event-data-main" / "data", APP_DIR / "data"]
PASS_RESULTS = {"C": "Complete", "I": "Incomplete", "S": "Sack", "R": "Scramble", "IN": "Interception"}
PRESSURE_LABELS = {"All": "All plays", "Yes": "Pressured", "No": "Not pressured"}
FILTER_DEFAULTS = {"f_team": "All", "f_pressure": "All", "f_pass": []}
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

STYLE = """<style>
.block-container {padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1500px;}
[data-testid="stMetricValue"] {font-size: 1.45rem; font-weight: 650;}
[data-testid="stMetricLabel"] p {font-size: 0.78rem; text-transform: uppercase; letter-spacing: .04em; opacity: .75;}
[data-testid="stSidebar"] h3 {margin-top: 0.4rem;}
</style>"""

# Restrained palettes: slate/navy base with one amber accent (matches the replay alert colour).
PALETTES = {
    True: dict(bg="#0f1621", panel="#151f2c", text="#e8edf5", muted="#9aa6b8", border="#2a3748", accent="#f2b84b"),
    False: dict(bg="#f5f7fa", panel="#ffffff", text="#1b2533", muted="#5b6778", border="#d9dee6", accent="#c9861a"),
}


def theme_css(dark: bool) -> str:
    p = PALETTES[dark]
    return f"""<style>
.stApp, [data-testid="stHeader"] {{background: {p['bg']}; color: {p['text']};}}
[data-testid="stSidebar"] {{background: {p['panel']}; border-right: 1px solid {p['border']};}}
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label, .stApp li, [data-testid="stMetricValue"],
[data-testid="stSidebar"] * {{color: {p['text']};}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{color: {p['muted']} !important;}}
[data-testid="stVerticalBlockBorderWrapper"] {{background: {p['panel']}; border-color: {p['border']} !important;}}
.stApp h1 {{border-bottom: 3px solid {p['accent']}; display: inline-block; padding-bottom: .15rem;}}
button[data-baseweb="tab"][aria-selected="true"] p {{color: {p['accent']}; font-weight: 650;}}
div[data-baseweb="tab-highlight"] {{background-color: {p['accent']};}}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {{background: {p['bg']}; border-color: {p['border']};}}
</style>"""


def resolve_data_dir() -> Path | None:
    env = os.environ.get("RUSH_DATA_DIR")
    for cand in ([Path(env)] if env else DATA_CANDIDATES):
        if (cand / "plays.csv").exists():
            return cand
    return None


def resolve_artifact_dir() -> Path:
    return Path(os.environ.get("RUSH_ARTIFACT_DIR", APP_DIR / "artifacts"))


def summary_path(artifact_dir: Path) -> Path | None:
    parquet, csv = artifact_dir / "play_summary.parquet", artifact_dir / "play_summary.csv"
    if parquet.exists():
        try:
            import pyarrow  # noqa: F401
            return parquet
        except ImportError:
            pass
    return csv if csv.exists() else None


@st.cache_data(show_spinner=False)
def load_summary(path: str, mtime: float) -> pd.DataFrame:
    raw = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
    return V.normalize_summary(raw)


@st.cache_resource(show_spinner="Loading play context...")
def cached_context(data_dir: str):
    from rush_threat.data import load_context
    return load_context(data_dir)


@st.cache_resource(show_spinner="Loading tracking for this game...", max_entries=2)
def cached_tracking(data_dir: str, game_id: int):
    from rush_threat.data import load_game_tracking
    return load_game_tracking(data_dir, game_id)


def filter_plays(summary: pd.DataFrame, team: str, pressure: str, pass_results: list[str]) -> pd.DataFrame:
    df = summary
    if team != "All":
        df = df[(df["possessionTeam"] == team) | (df["defensiveTeam"] == team)]
    if pressure != "All":
        df = df[df["pressure"].fillna(False).astype(bool) == (pressure == "Yes")]
    if pass_results:
        df = df[df["passResult"].fillna("(missing)").isin(pass_results)]
    return df.sort_values(["gameId", "playId"]).reset_index(drop=True)


def default_index(plays: pd.DataFrame) -> tuple[int, bool]:
    """Index of the default play; second value is False when it was filtered out."""
    hit = plays.index[(plays["gameId"] == DEFAULT_PLAY[0]) & (plays["playId"] == DEFAULT_PLAY[1])]
    return (int(hit[0]), True) if len(hit) else (0, False)


def down_distance(down, to_go) -> str:
    if pd.isna(down) or pd.isna(to_go):
        return "n/a"
    return f"{ORDINAL.get(int(down), str(int(down)))} & {int(to_go)}"


def pass_result_name(code) -> str:
    if code is None or pd.isna(code) or str(code).strip() == "":
        return "Not recorded"
    return PASS_RESULTS.get(str(code).strip(), str(code))


def play_label(row) -> str:
    desc = str(row.get("playDescription") or "")
    desc = desc if len(desc) <= 60 else desc[:57] + "..."
    return (f"{row['possessionTeam']} vs {row['defensiveTeam']} · "
            f"{down_distance(row.get('down'), row.get('yardsToGo'))} · {desc}  [{row['gameId']}/{row['playId']}]")


def fmt_auc(x: float) -> str:
    return "unavailable" if pd.isna(x) else f"{x:.3f}"


def reset_filters() -> None:
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def context_card(m: dict) -> None:
    """Compact play-level context. Pressure here is the play-level PFF label, not a frame state."""
    def g(k):
        v = m.get(k)
        return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) else v
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.4])
        c1.metric("Matchup (offense vs defense)", f"{g('possessionTeam')} vs {g('defensiveTeam')}")
        c2.metric("Down & distance", down_distance(m.get("down"), m.get("yardsToGo")))
        c3.metric("Pass result", pass_result_name(m.get("passResult")))
        c4.metric("Recorded PFF pressure (whole play)", "Yes" if m.get("pressure") else "No",
                  help="Play-level label: any defender credited with a hit, hurry or sack. "
                       "It does not say when pressure happened.")
        reasons = ", ".join(m.get("exclusion_reasons") or []) or "none"
        st.expander("More play details").caption(f"{g('offenseFormation')} · {g('dropBackType')} dropback · play action "
                   f"{'yes' if m.get('pff_playAction') else 'no'} · {g('rushers')} rushers, {g('blockers')} "
                   f"blockers, {g('routes')} routes · snap frame {g('snap_frame')}, terminal frame "
                   f"{g('terminal_frame')} ({g('terminal_event')}) · validation window frames "
                   f"{g('snap_frame')}–{g('validation_end_frame')}, eligible "
                   f"{'yes' if m.get('validation_eligible') else 'no'} (exclusions: {reasons})"
                   + (f" · {m['replay_note']}" if m.get("replay_note") else ""))


def render_replay(data_dir: Path | None, game_id: int, play_id: int, sector_deg: float) -> None:
    if data_dir is None:
        st.warning("Replay unavailable: tracking data not found. Set RUSH_DATA_DIR to the folder containing "
                   "games.csv, plays.csv, players.csv, pffScoutingData.csv and tracking/.")
        return
    try:
        from rush_threat.data import build_play_bundle
        from rush_threat.figure import build_figure
        bundle = build_play_bundle(cached_tracking(str(data_dir), game_id), cached_context(str(data_dir)),
                                   game_id, play_id, sector_deg=sector_deg)
    except Exception as exc:  # missing module/file or bad play: report, don't crash
        st.error(f"Replay unavailable for {game_id}/{play_id}: {exc}")
        return
    meta = bundle["metadata"]
    context_card(meta)
    if not meta.get("replay_available"):
        st.warning(f"Replay unavailable: {meta.get('replay_note') or 'no identifiable QB'}")
        return
    threats = bundle["threats"]
    if len(threats) and threats["outside_sector"].isna().any():
        st.caption("Orientation is missing for some frames: the wedge is hidden and inside/outside is unknown there.")
    try:
        st.plotly_chart(build_figure(bundle), width="stretch")
    except Exception as exc:
        st.error(f"Figure could not be built: {exc}")
    st.caption(f"Wedge = assumed forward sector ({sector_deg:.0f}°) from QB player orientation; orientation is "
               "not gaze. Distance in yards; closing speed in yards/second (positive = approaching the QB), "
               "computed retrospectively. Rusher colors match across the field and both charts.")


def render_validation(summary: pd.DataFrame, artifact_dir: Path) -> None:
    import plotly.express as px

    sc = V.scope(summary)
    st.subheader("Validation: does rusher proximity line up with recorded pressure?")
    st.markdown(f"Scope: **entire precomputed dataset** (sidebar filters ignored) · {sc['games']} games, "
                f"{sc['plays']:,} plays, {sc['eligible']:,} validation-eligible · season "
                f"{', '.join(map(str, sc['seasons']))} weeks {sc['weeks'][0] if sc['weeks'] else '?'}–"
                f"{sc['weeks'][-1] if sc['weeks'] else '?'} · sector fixed at **120°**.")
    if sc["games"] < V.FULL_DATASET_GAMES:
        st.warning(f"Partial data: {sc['games']} of {V.FULL_DATASET_GAMES} games processed. "
                   "Results below describe only these games.")
    st.caption("**AUC** = the chance that a randomly chosen pressured play has a higher score than a randomly "
               "chosen non-pressured play (0.5 = no better than a coin flip, 1.0 = perfect ordering). "
               "score_any uses the closest rusher; score_outside uses only rushers outside the 120° sector.")
    rows = []
    for name, ex in (("All eligible plays", False), ("Excluding sacks (passResult S)", True)):
        r = V.compare(summary, exclude_sacks=ex)
        rows.append({"Cohort": name, "n plays": r["n"], "Pressure rate": f"{r['pressure_rate']:.1%}"
                     if r["n"] else "n/a", "AUC score_any (baseline)": fmt_auc(r["auc_any"]),
                     "AUC score_outside (outside 120° sector)": fmt_auc(r["auc_outside"]),
                     "Dropped (missing score)": r["dropped_missing_score"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Descriptive, retrospective association on the same eligible plays for both scores; not a trained "
               "model and no tuned threshold. Comparing the two AUCs does not establish incremental predictive value.")

    cohort_rows, _ = V.cohort(summary)
    long = cohort_rows.melt(value_vars=["score_any", "score_outside"], id_vars=["pressure"],
                            var_name="feature", value_name="score")
    long["recorded pressure"] = long["pressure"].map({True: "yes", False: "no"})
    fig = px.box(long, x="feature", y="score", color="recorded pressure", points=False,
                 color_discrete_map={"yes": "#f2b84b", "no": "#5b8def"},
                 title="Score distributions by recorded PFF pressure (all eligible plays)")
    fig.update_layout(height=380, margin=dict(t=50, b=20), colorway=["#f2b84b", "#5b8def"])
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown(f"**Exclusions** · {sc['plays'] - sc['eligible']} plays not validation-eligible "
                    "(still selectable for replay). A play can have several reasons.")
        st.dataframe(V.exclusion_counts(summary), hide_index=True, width="stretch")
        exc_file = artifact_dir / "exclusions.csv"
        if exc_file.exists():
            with st.expander(f"Preprocessing report ({exc_file.name})"):
                st.dataframe(pd.read_csv(exc_file), hide_index=True, width="stretch")


def methodology() -> None:
    with st.container():
        st.subheader("Methodology and caveats")
        st.markdown(f"""
- **Data**: NFL Big Data Bowl tracking, 2021 regular season Weeks 1–8 (122 games in the full dataset; not the
  2023 split described in the event brief). Roles are initial PFF scouting roles: rushers = Pass Rush, QB = Pass.
- **Pressure**: a play counts as pressured if any defender is credited with pff_hit, pff_hurry or pff_sack (once
  per play). This is a play-level label, not a frame-level onset.
- **Geometry**: 0° points +y, 90° +x, clockwise; bearing = atan2(dx, dy). A rusher is *outside* the assumed
  forward sector when its bearing differs from QB player orientation by more than half the sector angle.
  Orientation is player orientation, not gaze. Missing orientation is unknown, not inside.
- **Validation window**: snap to min(snap + 25, terminal − 1) frames; terminal = earliest pass release, sack or
  scramble event after the snap. score_any = 1/(1 + minimum rusher distance); score_outside uses only observations
  outside the fixed 120° sector (0 when orientation is valid but no rusher is outside).
- **Alert**: per frame, the rusher within 5 yards with the highest positive smoothed closing speed (yards/second,
  centered 3-sample smoothing, retrospective).
- **Caveats**: retrospective association only; play-level PFF labels; QB turning and alignment confounding; early
  sacks are close by construction and observation lengths differ; initial-role rushers may drop into coverage; the
  sector comparison does not establish incremental prediction value.
- Context on pressure modelling: [Next Gen Stats: introduction to pressure probability]({V.NGS_PRESSURE_URL}).
""")


def main() -> None:
    st.set_page_config(page_title="Rush Threat Explorer", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.title("Rush Threat Explorer")
    st.markdown("Replay a single NFL dropback and watch the pass rush close in. The field shows every tracked "
                "player; the charts on the right show each rusher's distance to the quarterback and how fast he "
                "is closing. **Pick a play in the sidebar, then press Play or drag the time slider.**")
    data_dir, artifact_dir = resolve_data_dir(), resolve_artifact_dir()
    path = summary_path(artifact_dir)
    if path is None:
        st.error("No preprocessing output found in " f"`{artifact_dir}`. Run:\n\n```\npython precompute.py --games 2 "
                 f"--data-dir \"{data_dir or '/path/to/data'}\" --output-dir \"{artifact_dir}\"\n```\n"
                 "(use `--games all` for the full dataset), then reload. Set RUSH_ARTIFACT_DIR if the output is elsewhere.")
        st.stop()
    summary = load_summary(str(path), path.stat().st_mtime)
    for key, value in FILTER_DEFAULTS.items():
        st.session_state.setdefault(key, value)

    with st.sidebar:
        dark = st.toggle("Dark mode", value=True, key="dark_mode")
        st.markdown(theme_css(dark), unsafe_allow_html=True)
        st.subheader("1 · Filter plays")
        teams = sorted(set(summary["possessionTeam"].dropna()) | set(summary["defensiveTeam"].dropna()))
        team = st.selectbox("Team", ["All", *teams], key="f_team", help="Matches the offense or the defense.",
                            format_func=lambda t: "All teams" if t == "All" else t)
        pressure = st.radio("Recorded PFF pressure", ["All", "Yes", "No"], key="f_pressure", horizontal=True,
                            format_func=PRESSURE_LABELS.get)
        results = sorted(summary["passResult"].fillna("(missing)").unique())
        pass_results = st.multiselect("Pass result", results, key="f_pass", placeholder="All results",
                                      format_func=pass_result_name)
        plays = filter_plays(summary, team, pressure, pass_results)

        st.subheader("2 · Choose a play")
        selected = None
        if plays.empty:
            st.warning("No plays match these filters.")
            st.button("Reset filters", on_click=reset_filters, key="reset_sidebar", width="stretch")
        else:
            idx, found = default_index(plays)
            labels = [play_label(r) for r in plays.to_dict("records")]
            choice = st.selectbox(f"Play · {len(plays):,} match", range(len(plays)), index=idx,
                                  format_func=lambda i: labels[i])
            if not found:
                st.caption(f"Default play {DEFAULT_PLAY[0]}/{DEFAULT_PLAY[1]} is filtered out; "
                           "showing the first match.")
            selected = plays.iloc[choice]

        st.subheader("3 · Replay wedge")
        sector = st.slider("Assumed forward sector (degrees)", 60, 180, 120, step=5,
                           help="Widens or narrows the wedge drawn from the QB's orientation and the "
                                "inside/outside status in the replay. Validation always uses 120°.")
        st.caption("Changes the replay only; validation stays fixed at 120°.")

    tab_replay, tab_validation, tab_method = st.tabs(
        ["▶ Play replay", "Does proximity track pressure?", "How it works"])
    with tab_replay:
        if selected is not None:
            render_replay(data_dir, int(selected["gameId"]), int(selected["playId"]), float(sector))
        else:
            with st.container(border=True):
                st.markdown("**No plays match the sidebar filters.** Try another team or pass result, or reset.")
                st.button("Reset filters", on_click=reset_filters, key="reset_main")
    with tab_validation:
        render_validation(summary, artifact_dir)
    with tab_method:
        methodology()


if __name__ == "__main__":
    main()
