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


def play_label(row) -> str:
    desc = str(row.get("playDescription") or "")
    desc = desc if len(desc) <= 70 else desc[:67] + "..."
    down = "" if pd.isna(row.get("down")) else f"{int(row['down'])}&{int(row['yardsToGo'])} "
    return f"{row['gameId']}/{row['playId']} {row['possessionTeam']} v {row['defensiveTeam']} {down}{desc}"


def fmt_auc(x: float) -> str:
    return "unavailable" if pd.isna(x) else f"{x:.3f}"


def context_card(m: dict) -> None:
    def g(k):
        v = m.get(k)
        return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) else v
    reasons = ", ".join(m.get("exclusion_reasons") or []) or "none"
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**{g('possessionTeam')} offense vs {g('defensiveTeam')}**  \n"
                f"Down {g('down')} & {g('yardsToGo')} · passResult **{g('passResult')}**  \n"
                f"{g('offenseFormation')} · {g('dropBackType')} · play action {g('pff_playAction')}")
    c2.markdown(f"Blockers {g('blockers')} · rushers {g('rushers')} · routes {g('routes')}  \n"
                f"Recorded PFF pressure (play-level): **{'yes' if m.get('pressure') else 'no'}**  \n"
                f"Snap frame {g('snap_frame')} · terminal {g('terminal_frame')} ({g('terminal_event')})")
    c3.markdown(f"Validation window: frames {g('snap_frame')}–{g('validation_end_frame')}  \n"
                f"Validation eligible: **{'yes' if m.get('validation_eligible') else 'no'}** · "
                f"exclusions: {reasons}  \n{m.get('replay_note') or ''}")
    st.caption(str(m.get("playDescription") or ""))


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
    st.caption(f"Wedge = assumed forward sector ({sector_deg:.0f}°) from QB player orientation; orientation is not gaze. "
               "Distance in yards; closing speed in yards/second (positive = approaching the QB), retrospective. "
               "Recorded PFF pressure is a play-level label (hit/hurry/sack), not a frame-level onset.")


def render_validation(summary: pd.DataFrame, artifact_dir: Path) -> None:
    import plotly.express as px

    sc = V.scope(summary)
    st.header("Validation: proximity vs recorded pressure")
    st.markdown(f"Scope: **entire precomputed dataset** (sidebar filters ignored) · {sc['games']} games, "
                f"{sc['plays']:,} plays, {sc['eligible']:,} validation-eligible · season "
                f"{', '.join(map(str, sc['seasons']))} weeks {sc['weeks'][0] if sc['weeks'] else '?'}–"
                f"{sc['weeks'][-1] if sc['weeks'] else '?'} · sector fixed at **120°**.")
    if sc["games"] < V.FULL_DATASET_GAMES:
        st.warning(f"Partial data: {sc['games']} of {V.FULL_DATASET_GAMES} games processed. "
                   "Results below describe only these games.")
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
                 title="Score distributions by recorded PFF pressure (all eligible plays)")
    fig.update_layout(height=380, margin=dict(t=50, b=20))
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown(f"**Exclusions** · {sc['plays'] - sc['eligible']} plays not validation-eligible "
                    "(kept in the play selector). Plays can carry several reasons.")
        st.dataframe(V.exclusion_counts(summary), hide_index=True, width="stretch")
        exc_file = artifact_dir / "exclusions.csv"
        if exc_file.exists():
            st.caption(f"Preprocessing report {exc_file.name}:")
            st.dataframe(pd.read_csv(exc_file), hide_index=True, width="stretch")


def methodology() -> None:
    with st.expander("Methodology and caveats"):
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
    st.title("Rush Threat Explorer")
    st.caption("Exploratory, retrospective replay of pass-rush proximity to the QB, with an assumed forward sector.")
    data_dir, artifact_dir = resolve_data_dir(), resolve_artifact_dir()
    path = summary_path(artifact_dir)
    if path is None:
        st.error("No preprocessing output found in " f"`{artifact_dir}`. Run:\n\n```\npython precompute.py --games 2 "
                 f"--data-dir \"{data_dir or '/path/to/data'}\" --output-dir \"{artifact_dir}\"\n```\n"
                 "(use `--games all` for the full dataset), then reload. Set RUSH_ARTIFACT_DIR if the output is elsewhere.")
        st.stop()
    summary = load_summary(str(path), path.stat().st_mtime)

    with st.sidebar:
        st.header("Play selection")
        teams = sorted(set(summary["possessionTeam"].dropna()) | set(summary["defensiveTeam"].dropna()))
        team = st.selectbox("Team (offense or defense)", ["All", *teams])
        pressure = st.radio("Recorded PFF pressure", ["All", "Yes", "No"], horizontal=True)
        results = sorted(summary["passResult"].fillna("(missing)").unique())
        pass_results = st.multiselect("passResult", results, help="C complete, I incomplete, S sack, R scramble, "
                                      "IN interception; empty = all")
        plays = filter_plays(summary, team, pressure, pass_results)
        sector = st.slider("Sector angle (degrees)", 60, 180, 120, step=5)
        st.caption("Assumed forward sector for the replay only; validation is fixed at 120°.")
        selected = None
        if plays.empty:
            st.warning("No plays match these filters.")
        else:
            idx, found = default_index(plays)
            labels = [play_label(r) for r in plays.to_dict("records")]
            choice = st.selectbox(f"Play ({len(plays):,} matching)", range(len(plays)), index=idx,
                                  format_func=lambda i: labels[i])
            if not found:
                st.info(f"Default play {DEFAULT_PLAY[0]}/{DEFAULT_PLAY[1]} is filtered out; showing the first match.")
            selected = plays.iloc[choice]

    if selected is not None:
        st.subheader(f"Replay · game {selected['gameId']} play {selected['playId']}")
        render_replay(data_dir, int(selected["gameId"]), int(selected["playId"]), float(sector))
    else:
        st.info("Adjust the sidebar filters to select a play.")
    render_validation(summary, artifact_dir)
    methodology()


if __name__ == "__main__":
    main()
