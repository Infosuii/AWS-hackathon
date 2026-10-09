"""Data engine for Rush Threat Explorer (SHARED_CONTRACT v1).

Public API:
    load_context(data_dir) -> dict with keys games, plays, players, scouting
    load_game_tracking(data_dir, game_id) -> tracking DataFrame for one game
    build_play_bundle(game_tracking, context, game_id, play_id, sector_deg=120.0)
        -> {"players": DataFrame, "threats": DataFrame, "metadata": dict}
    build_game_summaries(game_tracking, context) -> one row per (gameId, playId)

Boundary conventions (confirmed by enumerating every event in the 122 tracking files):
    * Snap: earliest ``ball_snap`` frame; fallback earliest ``autoevent_ballsnap``
      when a play has no ``ball_snap`` (1 play in the dataset). 24 plays have neither.
    * Terminal: earliest frame strictly after the snap among
        release  : pass_forward, autoevent_passforward, pass_shovel
        sack     : qb_sack, qb_strip_sack
        scramble : run   (443 of 449 passResult == 'R' plays carry it)
      Same-frame ties resolve release > sack > scramble. ``handoff``, ``lateral`` and
      ``fumble`` are not terminal. The earliest event is a consistent convention, not an
      independently verified exact release time.
    * Replay window: [snap, terminal] inclusive. When snap or terminal is missing, the
      whole tracked play is replayed, flagged, and never enters validation.
    * Validation window: [snap, min(snap + 25, terminal - 1)] inclusive.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from rush_threat import geometry as geo

KEYS = ["gameId", "playId"]
TRACK_KEYS = ["gameId", "playId", "nflId"]

SNAP_EVENT = "ball_snap"
SNAP_FALLBACK_EVENT = "autoevent_ballsnap"
RELEASE_EVENTS = ("pass_forward", "autoevent_passforward", "pass_shovel")
SACK_EVENTS = ("qb_sack", "qb_strip_sack")
SCRAMBLE_EVENTS = ("run",)
# Lower value wins a same-frame tie.
TERMINAL_PRIORITY = {
    **{e: 0 for e in RELEASE_EVENTS},
    **{e: 1 for e in SACK_EVENTS},
    **{e: 2 for e in SCRAMBLE_EVENTS},
}

VALIDATION_MAX_FRAMES = 25
SUMMARY_SECTOR_DEG = 120.0
ALERT_RADIUS_YD = 5.0
REASON_SEP = ";"

ROLE_MAP = {
    "pass": "qb",
    "pass rush": "rusher",
    "pass block": "blocker",
    "pass route": "route",
    "coverage": "coverage",
}
ROLE_VOCAB = ("qb", "rusher", "blocker", "route", "coverage", "ball", "other")

PLAYER_COLUMNS = ["frameId", "nflId", "x", "y", "o", "jerseyNumber", "displayName",
                  "role", "time_from_snap"]
THREAT_COLUMNS = ["frameId", "nflId", "displayName", "jerseyNumber", "x", "y", "qb_x",
                  "qb_y", "qb_o", "time_from_snap", "distance", "closing_speed",
                  "bearing_deg", "outside_sector", "in_validation"]
METADATA_KEYS = ["gameId", "playId", "playDescription", "possessionTeam", "defensiveTeam",
                 "passResult", "down", "yardsToGo", "offenseFormation", "dropBackType",
                 "pff_playAction", "blockers", "rushers", "routes", "pressure", "snap_frame",
                 "terminal_frame", "terminal_event", "validation_end_frame", "sector_deg",
                 "validation_eligible", "exclusion_reasons", "replay_available",
                 "replay_note"]
PLAY_META_COLUMNS = ["playDescription", "possessionTeam", "defensiveTeam", "passResult",
                     "down", "yardsToGo", "offenseFormation", "dropBackType",
                     "pff_playAction"]
SUMMARY_COLUMNS = ["gameId", "playId", "season", "week", "playDescription",
                   "possessionTeam", "defensiveTeam", "passResult", "down", "yardsToGo",
                   "offenseFormation", "dropBackType", "pff_playAction", "blockers",
                   "rushers", "routes", "pressure", "snap_frame", "terminal_frame",
                   "terminal_event", "validation_end_frame", "validation_duration_s",
                   "validation_eligible", "exclusion_reasons", "replay_available",
                   "d_min_any", "d_min_outside", "score_any", "score_outside",
                   "peak_close_5yd", "peak_rusher_id", "peak_frame"]

_TRACKING_DTYPES = {"gameId": "int64", "playId": "int64", "nflId": "Int64",
                    "frameId": "int64", "jerseyNumber": "Int64", "event": "string"}


# --------------------------------------------------------------------------- loading

def resolve_data_dir(data_dir: str | os.PathLike | None = None) -> Path:
    """Resolve the dataset root: explicit argument, then RUSH_DATA_DIR, then common
    relative locations. Raises FileNotFoundError with the paths that were tried."""
    candidates: list[Path] = []
    if data_dir:
        candidates.append(Path(data_dir))
    elif os.environ.get("RUSH_DATA_DIR"):
        candidates.append(Path(os.environ["RUSH_DATA_DIR"]))
    else:
        # cwd and the repository root, plus up to three parent folders of each, so a
        # checkout nested beside or below the dataset folder still finds it.
        bases: list[Path] = []
        for start in (Path.cwd(), Path(__file__).resolve().parent.parent):
            for base in [start, *list(start.parents)[:3]]:
                if base not in bases:
                    bases.append(base)
        for base in bases:
            candidates += [base / "data",
                           base / "nfl-big-data-bowl-regional-event-data-main" / "data"]
    for c in candidates:
        if (c / "games.csv").is_file() and (c / "tracking").is_dir():
            return c
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Dataset root not found (need games.csv and tracking/). Tried: {tried}. "
        "Pass --data-dir or set RUSH_DATA_DIR.")


def normalize_role(value) -> str | None:
    """Lower-case, trim and collapse whitespace of a PFF role string."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    return " ".join(str(value).split()).lower()


def load_context(data_dir) -> dict[str, pd.DataFrame]:
    """Load games, plays, players and PFF scouting tables.

    scouting gains ``pff_role_norm`` and ``role`` (contract vocabulary) columns.
    """
    root = resolve_data_dir(data_dir)
    games = pd.read_csv(root / "games.csv")
    plays = pd.read_csv(root / "plays.csv")
    players = pd.read_csv(root / "players.csv")
    scouting = pd.read_csv(root / "pffScoutingData.csv")
    scouting["nflId"] = scouting["nflId"].astype("Int64")
    players["nflId"] = players["nflId"].astype("Int64")
    scouting["pff_role_norm"] = scouting["pff_role"].map(normalize_role)
    scouting["role"] = scouting["pff_role_norm"].map(ROLE_MAP).fillna("other")
    return {"games": games, "plays": plays, "players": players, "scouting": scouting}


def _scouting(context: dict) -> pd.DataFrame:
    """Scouting table with normalized roles, also for hand-built (synthetic) contexts."""
    sc = context["scouting"]
    if "role" not in sc.columns:
        sc = sc.copy()
        sc["pff_role_norm"] = sc["pff_role"].map(normalize_role)
        sc["role"] = sc["pff_role_norm"].map(ROLE_MAP).fillna("other")
    return sc


def tracking_path(data_dir, game_id: int) -> Path:
    return resolve_data_dir(data_dir) / "tracking" / f"tracking_{int(game_id)}.csv"


def load_game_tracking(data_dir, game_id: int) -> pd.DataFrame:
    """Read one game's tracking file. nflId is nullable (NA = football)."""
    df = pd.read_csv(tracking_path(data_dir, game_id), dtype=_TRACKING_DTYPES)
    df = df.drop_duplicates(["gameId", "playId", "nflId", "frameId"], keep="first")
    return df.reset_index(drop=True)


# ----------------------------------------------------------------- play boundaries

def play_boundaries(game_tracking: pd.DataFrame) -> pd.DataFrame:
    """Per (gameId, playId): first/last frame, snap frame/source, terminal frame/event."""
    frames = (game_tracking.groupby(KEYS)["frameId"].agg(first_frame="min", last_frame="max")
              .reset_index())
    ev = game_tracking.loc[game_tracking["event"].notna(), KEYS + ["frameId", "event"]].copy()
    ev["event"] = ev["event"].astype(str).str.strip().str.lower()
    ev = ev.drop_duplicates()

    snap_bs = ev[ev["event"] == SNAP_EVENT].groupby(KEYS)["frameId"].min().rename("snap_bs")
    snap_auto = (ev[ev["event"] == SNAP_FALLBACK_EVENT].groupby(KEYS)["frameId"].min()
                 .rename("snap_auto"))
    out = frames.merge(snap_bs.reset_index(), on=KEYS, how="left")
    out = out.merge(snap_auto.reset_index(), on=KEYS, how="left")
    out["snap_source"] = np.where(out["snap_bs"].notna(), SNAP_EVENT,
                                  np.where(out["snap_auto"].notna(), SNAP_FALLBACK_EVENT, None))
    out["snap_frame"] = out["snap_bs"].fillna(out["snap_auto"]).astype("Int64")
    out = out.drop(columns=["snap_bs", "snap_auto"])

    cand = ev[ev["event"].isin(TERMINAL_PRIORITY)].merge(out[KEYS + ["snap_frame"]], on=KEYS)
    after_snap = (cand["frameId"] > cand["snap_frame"]).fillna(False).astype(bool)
    cand = cand[after_snap].copy()
    cand["prio"] = cand["event"].map(TERMINAL_PRIORITY)
    cand = cand.sort_values(KEYS + ["frameId", "prio"]).drop_duplicates(KEYS, keep="first")
    cand = cand.rename(columns={"frameId": "terminal_frame", "event": "terminal_event"})
    out = out.merge(cand[KEYS + ["terminal_frame", "terminal_event"]], on=KEYS, how="left")
    out["terminal_frame"] = out["terminal_frame"].astype("Int64")
    return out


# ------------------------------------------------------------------- play info

def _play_info(game_tracking: pd.DataFrame, context: dict, game_ids) -> pd.DataFrame:
    """One row per plays.csv play in game_ids with roles, labels, boundaries and windows."""
    game_ids = [int(g) for g in game_ids]
    plays = context["plays"]
    info = plays.loc[plays["gameId"].isin(game_ids), KEYS + PLAY_META_COLUMNS].copy()
    games = context["games"][["gameId", "season", "week"]]
    info = info.merge(games, on="gameId", how="left")

    sc = _scouting(context)
    sc = sc[sc["gameId"].isin(game_ids)]
    role_cols = {"blocker": "blockers", "rusher": "rushers", "route": "routes",
                 "qb": "qb_count"}
    counts = (sc[KEYS].assign(**{v: (sc["role"] == k).astype("int64")
                                 for k, v in role_cols.items()})
              .groupby(KEYS, as_index=False).sum())
    info = info.merge(counts, on=KEYS, how="left")
    for c in ["blockers", "rushers", "routes", "qb_count"]:
        info[c] = info[c].fillna(0).astype("int64")

    flags = sc[["pff_hit", "pff_hurry", "pff_sack"]].eq(1).any(axis=1)
    pressure = flags.groupby([sc["gameId"], sc["playId"]]).any().rename("pressure").reset_index()
    info = info.merge(pressure, on=KEYS, how="left")
    info["pressure"] = info["pressure"].eq(True)

    qbs = sc[sc["role"] == "qb"].groupby(KEYS)["nflId"].first().rename("qb_nflId").reset_index()
    info = info.merge(qbs, on=KEYS, how="left")
    info["qb_nflId"] = info["qb_nflId"].astype("Int64").where(info["qb_count"] == 1)

    trk = game_tracking[game_tracking["gameId"].isin(game_ids)]
    info = info.merge(play_boundaries(trk), on=KEYS, how="left")
    info["has_tracking"] = info["first_frame"].notna()

    tracked = trk.loc[trk["nflId"].notna(), TRACK_KEYS].drop_duplicates()
    qb_tr = tracked.merge(info[KEYS + ["qb_nflId"]].dropna(subset=["qb_nflId"]),
                          left_on=TRACK_KEYS, right_on=KEYS + ["qb_nflId"])
    qb_tr = qb_tr[KEYS].drop_duplicates().assign(qb_tracked=True)
    info = info.merge(qb_tr, on=KEYS, how="left")
    info["qb_tracked"] = info["qb_tracked"].eq(True)

    rush = sc.loc[sc["role"] == "rusher", TRACK_KEYS]
    rush_tr = rush.merge(tracked, on=TRACK_KEYS).groupby(KEYS).size().rename("rushers_tracked")
    info = info.merge(rush_tr.reset_index(), on=KEYS, how="left")
    info["rushers_tracked"] = info["rushers_tracked"].fillna(0).astype("int64")

    known = info["snap_frame"].notna() & info["terminal_frame"].notna()
    info["boundaries_known"] = known
    info["win_start"] = info["snap_frame"].where(known, info["first_frame"]).astype("Int64")
    info["win_end"] = info["terminal_frame"].where(known, info["last_frame"]).astype("Int64")
    info["time_base"] = info["snap_frame"].fillna(info["win_start"]).astype("Int64")
    val_end = np.minimum(info["snap_frame"] + VALIDATION_MAX_FRAMES, info["terminal_frame"] - 1)
    info["validation_end_frame"] = pd.array(val_end, dtype="Int64")
    info.loc[~known, "validation_end_frame"] = pd.NA
    info["replay_available"] = (info["qb_count"] == 1) & info["qb_tracked"] & info["has_tracking"]
    return info.reset_index(drop=True)


# --------------------------------------------------------------------- threats

def _window(trk: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    """Tracking rows inside each play's replay window, with time_from_snap."""
    w = trk.merge(info.loc[info["replay_available"], KEYS + ["win_start", "win_end", "time_base"]],
                  on=KEYS)
    w = w[(w["frameId"] >= w["win_start"]) & (w["frameId"] <= w["win_end"])].copy()
    w["time_from_snap"] = (w["frameId"] - w["time_base"]).astype(float) / geo.FPS
    return w


def _threats(win: pd.DataFrame, info: pd.DataFrame, context: dict,
             sector_deg: float) -> pd.DataFrame:
    """One row per (gameId, playId, frameId, rusher) within the replay window."""
    qb_ids = info.loc[info["replay_available"], KEYS + ["qb_nflId"]]
    qb = win.merge(qb_ids, left_on=TRACK_KEYS, right_on=KEYS + ["qb_nflId"])
    qb = qb[KEYS + ["frameId", "x", "y", "o"]].rename(
        columns={"x": "qb_x", "y": "qb_y", "o": "qb_o"})

    sc = _scouting(context)
    rush_ids = sc.loc[(sc["role"] == "rusher") & sc["gameId"].isin(info["gameId"].unique()),
                      TRACK_KEYS].drop_duplicates()
    r = win.merge(rush_ids, on=TRACK_KEYS)
    r = r.merge(qb, on=KEYS + ["frameId"], how="inner")
    names = context["players"][["nflId", "displayName"]].drop_duplicates("nflId")
    r = r.merge(names, on="nflId", how="left")
    r = r.merge(info[KEYS + ["snap_frame", "validation_end_frame"]], on=KEYS, how="left")

    r = r.sort_values(TRACK_KEYS + ["frameId"]).reset_index(drop=True)
    r["distance"] = geo.distance(r["qb_x"], r["qb_y"], r["x"], r["y"])
    r["bearing_deg"] = geo.bearing_deg(r["qb_x"], r["qb_y"], r["x"], r["y"])
    r["outside_sector"] = geo.outside_sector(r["bearing_deg"], r["qb_o"], sector_deg)

    g = r.groupby(TRACK_KEYS, sort=False)
    dd = g["distance"].diff()
    dfr = g["frameId"].diff().astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = -dd / (dfr / geo.FPS)
    raw = raw.where(dfr > 0)
    r["closing_speed"] = (raw.groupby([r[k] for k in TRACK_KEYS], sort=False)
                          .transform(lambda s: s.rolling(3, center=True, min_periods=1).mean()))
    ve = r["validation_end_frame"]
    r["in_validation"] = (ve.notna() & (r["frameId"] >= r["snap_frame"])
                          & (r["frameId"] <= ve)).fillna(False).astype(bool)
    return r


def frame_alerts(threats: pd.DataFrame, radius_yd: float = ALERT_RADIUS_YD) -> pd.DataFrame:
    """Per frame, the rusher with the highest positive finite closing_speed within
    radius_yd (ties -> lowest nflId). Frames without a candidate are absent."""
    keys = [k for k in KEYS if k in threats.columns]
    cs = threats["closing_speed"].astype(float)
    ok = np.isfinite(cs) & (cs > 0) & (threats["distance"] <= radius_yd)
    c = threats[ok]
    c = c.sort_values(keys + ["frameId", "closing_speed", "nflId"],
                      ascending=[True] * len(keys) + [True, False, True])
    return c.drop_duplicates(keys + ["frameId"], keep="first")


# ------------------------------------------------------------ eligibility/status

def _play_status(row, play_threats: pd.DataFrame) -> tuple[list[str], str]:
    """Exclusion reason codes and a replay note for one play."""
    reasons: list[str] = []
    notes: list[str] = []
    if not row["has_tracking"]:
        reasons.append("missing_tracking")
    if row["qb_count"] == 0:
        reasons.append("missing_qb")
    elif row["qb_count"] > 1:
        reasons.append("multiple_qb")
    elif row["has_tracking"] and not row["qb_tracked"]:
        reasons.append("qb_untracked")
    if row["has_tracking"]:
        if pd.isna(row["snap_frame"]):
            reasons.append("missing_snap")
        if pd.isna(row["terminal_frame"]):
            reasons.append("missing_terminal")
    if row["rushers"] == 0:
        reasons.append("missing_rushers")
    elif row["has_tracking"] and row["rushers_tracked"] < row["rushers"]:
        reasons.append("rusher_untracked")

    if row["replay_available"] and row["boundaries_known"]:
        v = play_threats[play_threats["in_validation"] & np.isfinite(play_threats["distance"])]
        if v.empty:
            reasons.append("no_validation_distance")
        else:
            if v["qb_o"].isna().any():
                reasons.append("missing_orientation")
            if (v["qb_o"].notna() & v["bearing_deg"].isna()).any():
                reasons.append("undefined_bearing")

    if not row["replay_available"]:
        if row["qb_count"] != 1:
            notes.append(f"Replay unavailable: {int(row['qb_count'])} PFF 'Pass' (QB) "
                         "players; one identifiable QB is required.")
        elif not row["has_tracking"]:
            notes.append("Replay unavailable: no tracking rows for this play.")
        else:
            notes.append("Replay unavailable: the QB has no tracking rows for this play.")
    elif not row["boundaries_known"]:
        notes.append("Snap or terminal event missing: showing the whole tracked play as a "
                     "flagged fallback; time is measured from "
                     + ("the snap" if pd.notna(row["snap_frame"]) else "the first tracked frame")
                     + "; excluded from validation.")
    if row.get("snap_source") == SNAP_FALLBACK_EVENT:
        notes.append("Snap taken from autoevent_ballsnap (no ball_snap event).")
    if "missing_orientation" in reasons:
        notes.append("QB orientation missing on some frames: sector status unknown there.")
    if "rusher_untracked" in reasons:
        notes.append(f"{int(row['rushers'] - row['rushers_tracked'])} of {int(row['rushers'])} "
                     "PFF rushers have no tracking rows.")
    return reasons, " ".join(notes)


def _py(v):
    """Convert pandas/numpy scalars to plain Python values (missing -> None)."""
    if v is None:
        return None
    if isinstance(v, (list, tuple, dict)):
        return v
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


# ------------------------------------------------------------------ public build

def _empty_players() -> pd.DataFrame:
    return pd.DataFrame({
        "frameId": pd.Series(dtype="int64"), "nflId": pd.Series(dtype="Int64"),
        "x": pd.Series(dtype=float), "y": pd.Series(dtype=float), "o": pd.Series(dtype=float),
        "jerseyNumber": pd.Series(dtype="Int64"), "displayName": pd.Series(dtype=object),
        "role": pd.Series(dtype=object), "time_from_snap": pd.Series(dtype=float)})


def _empty_threats() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype=float) for c in THREAT_COLUMNS})
    df["frameId"] = df["frameId"].astype("int64")
    df["nflId"] = df["nflId"].astype("Int64")
    df["jerseyNumber"] = df["jerseyNumber"].astype("Int64")
    df["displayName"] = df["displayName"].astype(object)
    df["outside_sector"] = df["outside_sector"].astype("boolean")
    df["in_validation"] = df["in_validation"].astype(bool)
    return df


def build_play_bundle(game_tracking: pd.DataFrame, context: dict, game_id: int, play_id: int,
                      sector_deg: float = 120.0) -> dict:
    """Replay bundle for one play: players, threats (requested sector) and metadata."""
    game_id, play_id = int(game_id), int(play_id)
    plays = context["plays"]
    if not ((plays["gameId"] == game_id) & (plays["playId"] == play_id)).any():
        raise KeyError(f"play ({game_id}, {play_id}) not found in plays.csv")
    trk = game_tracking[(game_tracking["gameId"] == game_id)
                        & (game_tracking["playId"] == play_id)]
    info = _play_info(trk, context, [game_id])
    info = info[info["playId"] == play_id].reset_index(drop=True)
    row = info.iloc[0]

    if row["replay_available"]:
        win = _window(trk, info)
        threats = _threats(win, info, context, sector_deg)
        players = _players_table(win, context)
    else:
        threats = _empty_threats().assign(gameId=game_id, playId=play_id,
                                          validation_end_frame=pd.NA)
        players = _empty_players()
    reasons, note = _play_status(row, threats)

    meta = {k: _py(row[k]) for k in KEYS + PLAY_META_COLUMNS
            + ["blockers", "rushers", "routes", "pressure", "snap_frame", "terminal_frame",
               "terminal_event", "validation_end_frame", "replay_available"]}
    meta.update(sector_deg=float(sector_deg), validation_eligible=not reasons,
                exclusion_reasons=reasons, replay_note=note)
    meta = {k: meta[k] for k in METADATA_KEYS}

    threats = (threats.sort_values(["frameId", "nflId"])[THREAT_COLUMNS]
               .reset_index(drop=True))
    return {"players": players, "threats": threats, "metadata": meta}


def _players_table(win: pd.DataFrame, context: dict) -> pd.DataFrame:
    sc = _scouting(context)
    sc = sc.loc[sc["gameId"].isin(win["gameId"].unique()),
                TRACK_KEYS + ["role"]].drop_duplicates(TRACK_KEYS)
    p = win.merge(sc, on=TRACK_KEYS, how="left")
    names = context["players"][["nflId", "displayName"]].drop_duplicates("nflId")
    p = p.merge(names, on="nflId", how="left")
    is_ball = p["nflId"].isna()
    p["role"] = p["role"].astype(object).where(p["role"].notna(), "other")
    p.loc[is_ball, "role"] = "ball"
    p["displayName"] = p["displayName"].astype(object)
    p.loc[is_ball, "displayName"] = "football"
    p = p.sort_values(["frameId", "nflId"], na_position="last")
    return p[PLAYER_COLUMNS].reset_index(drop=True)


def build_game_threats(game_tracking: pd.DataFrame, context: dict,
                       sector_deg: float = SUMMARY_SECTOR_DEG) -> pd.DataFrame:
    """Threat rows for every replayable play of the games in game_tracking: the contract
    threat columns plus gameId, playId (helper used by build_game_summaries)."""
    game_ids = sorted(game_tracking["gameId"].dropna().unique().tolist())
    info = _play_info(game_tracking, context, game_ids)
    threats = _threats(_window(game_tracking, info), info, context, sector_deg)
    return threats[KEYS + THREAT_COLUMNS].reset_index(drop=True)


def _summaries_for_games(game_tracking: pd.DataFrame, context: dict, game_ids) -> pd.DataFrame:
    info = _play_info(game_tracking, context, game_ids)
    trk = game_tracking[game_tracking["gameId"].isin([int(g) for g in game_ids])]
    win = _window(trk, info)
    threats = _threats(win, info, context, SUMMARY_SECTOR_DEG)

    # Summary peaks only for properly bounded replays (snap..terminal); a flagged
    # whole-play fallback would mix in post-release motion.
    bounded = info.loc[info["boundaries_known"], KEYS]
    alerts = frame_alerts(threats.merge(bounded, on=KEYS))
    peak = (alerts.sort_values(KEYS + ["closing_speed", "frameId", "nflId"],
                               ascending=[True, True, False, True, True])
            .drop_duplicates(KEYS, keep="first")
            [KEYS + ["closing_speed", "nflId", "frameId"]]
            .rename(columns={"closing_speed": "peak_close_5yd", "nflId": "peak_rusher_id",
                             "frameId": "peak_frame"}))
    info = info.merge(peak, on=KEYS, how="left")

    val = threats[threats["in_validation"] & np.isfinite(threats["distance"])]
    vg = val.groupby(KEYS)
    agg = pd.DataFrame({
        "d_min_any": vg["distance"].min(),
        "n_unknown": vg["outside_sector"].agg(lambda s: int(s.isna().sum())),
    })
    out_d = val[val["outside_sector"].fillna(False).astype(bool)].groupby(KEYS)["distance"].min()
    agg["d_min_outside"] = out_d
    info = info.merge(agg.reset_index(), on=KEYS, how="left")

    by_play = {k: g for k, g in threats.groupby(KEYS, sort=False)}
    empty = _empty_threats()
    reasons_col = []
    for _, row in info.iterrows():
        pt = by_play.get((row["gameId"], row["playId"]), empty)
        reasons, _ = _play_status(row, pt)
        reasons_col.append(reasons)
    info["validation_eligible"] = [not r for r in reasons_col]
    info["exclusion_reasons"] = [REASON_SEP.join(r) for r in reasons_col]

    window_ok = info["boundaries_known"] & info["replay_available"] & info["d_min_any"].notna()
    info["score_any"] = (1.0 / (1.0 + info["d_min_any"])).where(window_ok)
    orient_ok = window_ok & (info["n_unknown"] == 0)
    info["d_min_outside"] = info["d_min_outside"].where(orient_ok)
    info["score_outside"] = np.where(
        orient_ok, np.where(info["d_min_outside"].notna(),
                            1.0 / (1.0 + info["d_min_outside"]), 0.0), np.nan)
    info["validation_duration_s"] = ((info["validation_end_frame"] - info["snap_frame"])
                                     .astype("Float64") / geo.FPS).astype(float)
    info["peak_rusher_id"] = info["peak_rusher_id"].astype("Int64")
    info["peak_frame"] = info["peak_frame"].astype("Int64")
    info["peak_close_5yd"] = info["peak_close_5yd"].astype(float)
    info["terminal_event"] = info["terminal_event"].astype(object)
    out = info[SUMMARY_COLUMNS].sort_values(KEYS).reset_index(drop=True)
    return out


def build_game_summaries(game_tracking: pd.DataFrame, context: dict) -> pd.DataFrame:
    """One row per (gameId, playId) for every plays.csv play of the games present in
    game_tracking, using the fixed 120-degree sector. Ineligible plays are retained."""
    game_ids = sorted(game_tracking["gameId"].dropna().unique().tolist())
    return _summaries_for_games(game_tracking, context, game_ids)
