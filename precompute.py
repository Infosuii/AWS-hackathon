"""Precompute per-play summaries for Rush Threat Explorer.

Usage:
    python precompute.py --games 2   --data-dir PATH --output-dir artifacts
    python precompute.py --games all --data-dir PATH --output-dir artifacts

--data-dir defaults to RUSH_DATA_DIR, then common relative dataset locations.
Games are processed one tracking file at a time (games.csv order, sorted by gameId).

Outputs (in --output-dir):
    play_summary.parquet  when pyarrow is importable, otherwise play_summary.csv
                          (identical columns; one row per (gameId, playId), ineligible
                          plays retained; exclusion_reasons is ';'-separated)
    exclusions.csv        reason, plays, description - explicit exclusion counts
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

from rush_threat import data as rd

REASON_DESCRIPTIONS = {
    "ALL_PLAYS": "plays in plays.csv for the processed games (summary rows)",
    "ELIGIBLE": "plays with no exclusion reason (validation set, 120-degree sector)",
    "EXCLUDED": "plays with at least one exclusion reason (a play may have several)",
    "REPLAY_UNAVAILABLE": "plays without a replay (no single tracked PFF QB)",
    "missing_tracking": "no tracking rows for the play",
    "missing_qb": "no PFF 'Pass' (QB) player",
    "multiple_qb": "more than one PFF 'Pass' (QB) player",
    "qb_untracked": "PFF QB has no tracking rows",
    "missing_snap": "no ball_snap/autoevent_ballsnap event (whole-play fallback replay)",
    "missing_terminal": "no release/sack/scramble event after the snap (fallback replay)",
    "missing_rushers": "no PFF 'Pass Rush' players",
    "rusher_untracked": "at least one PFF rusher has no tracking rows",
    "no_validation_distance": "no valid rusher-QB distance in the validation window",
    "missing_orientation": "QB orientation missing in validation-window observations",
    "undefined_bearing": "zero rusher-QB separation (undefined bearing) in validation window",
    "processing_error": "game failed to process; see console output",
}


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Precompute Rush Threat Explorer play summaries.")
    p.add_argument("--games", default="2",
                   help="'all' or a positive number of games (games.csv order). Default 2.")
    p.add_argument("--data-dir", default=None,
                   help="Dataset root (games.csv, plays.csv, ..., tracking/). "
                        "Defaults to RUSH_DATA_DIR.")
    p.add_argument("--output-dir", default="artifacts", help="Output directory.")
    p.add_argument("--format", choices=["auto", "parquet", "csv"], default="auto",
                   help="auto = Parquet if pyarrow is importable, else CSV.")
    args = p.parse_args(argv)
    if args.games != "all":
        try:
            n = int(args.games)
        except ValueError:
            p.error("--games must be 'all' or a positive integer")
        if n < 1:
            p.error("--games must be 'all' or a positive integer")
    return args


def _have_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def exclusion_counts(summary: pd.DataFrame) -> pd.DataFrame:
    """Explicit counts: totals first, then one row per reason code (incl. zero counts)."""
    reasons = summary["exclusion_reasons"].fillna("").astype(str)
    codes = reasons.str.split(rd.REASON_SEP).explode()
    codes = codes[codes != ""]
    per = codes.value_counts()
    rows = [("ALL_PLAYS", len(summary)),
            ("ELIGIBLE", int(summary["validation_eligible"].sum())),
            ("EXCLUDED", int((~summary["validation_eligible"].astype(bool)).sum())),
            ("REPLAY_UNAVAILABLE", int((~summary["replay_available"].astype(bool)).sum()))]
    known = [k for k in REASON_DESCRIPTIONS if k == k.lower()]
    for code in known + sorted(set(per.index) - set(known)):
        rows.append((code, int(per.get(code, 0))))
    out = pd.DataFrame(rows, columns=["reason", "plays"])
    out["description"] = out["reason"].map(REASON_DESCRIPTIONS).fillna("")
    return out


def _error_rows(context: dict, game_id: int) -> pd.DataFrame:
    """Placeholder rows so a failed game's plays stay visible and are excluded."""
    s = rd._summaries_for_games(_empty_tracking(), context, [game_id])
    s["validation_eligible"] = False
    s["replay_available"] = False
    s["exclusion_reasons"] = "processing_error"
    return s


def _empty_tracking() -> pd.DataFrame:
    cols = {"gameId": "int64", "playId": "int64", "nflId": "Int64", "frameId": "int64",
            "jerseyNumber": "Int64", "x": float, "y": float, "o": float, "event": "string"}
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in cols.items()})


def run(argv=None) -> int:
    args = _parse_args(argv)
    t_start = time.perf_counter()
    root = rd.resolve_data_dir(args.data_dir)
    context = rd.load_context(root)
    game_ids = sorted(context["games"]["gameId"].astype(int).unique().tolist())
    if args.games != "all":
        game_ids = game_ids[: int(args.games)]
    print(f"data dir: {root}")
    print(f"context loaded in {time.perf_counter() - t_start:.1f}s; "
          f"processing {len(game_ids)} game(s)")

    parts, failures, missing_files = [], [], []
    for i, gid in enumerate(game_ids, 1):
        t0 = time.perf_counter()
        try:
            if rd.tracking_path(root, gid).is_file():
                trk = rd.load_game_tracking(root, gid)
            else:
                missing_files.append(gid)
                trk = _empty_tracking()
            s = rd._summaries_for_games(trk, context, [gid])
        except Exception as exc:  # keep the run going; report with context
            failures.append((gid, repr(exc)))
            print(f"[{i}/{len(game_ids)}] game {gid}: ERROR {exc!r}", file=sys.stderr)
            traceback.print_exc()
            s = _error_rows(context, gid)
        parts.append(s)
        n_ok = int(s["validation_eligible"].sum())
        print(f"[{i}/{len(game_ids)}] game {gid}: {len(s)} plays, {n_ok} eligible, "
              f"{time.perf_counter() - t0:.2f}s", flush=True)

    summary = pd.concat(parts, ignore_index=True).sort_values(rd.KEYS).reset_index(drop=True)
    dup = int(summary.duplicated(rd.KEYS).sum())
    if dup:
        print(f"WARNING: {dup} duplicated (gameId, playId) keys", file=sys.stderr)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = args.format
    if fmt == "auto":
        fmt = "parquet" if _have_pyarrow() else "csv"
    target = out_dir / f"play_summary.{fmt}"
    stale = out_dir / f"play_summary.{'csv' if fmt == 'parquet' else 'parquet'}"
    if fmt == "parquet":
        summary.to_parquet(target, index=False)
    else:
        summary.to_csv(target, index=False)
    if stale.exists():
        stale.unlink()  # avoid a stale summary from a previous run in the other format
        print(f"removed stale {stale}")
    excl = exclusion_counts(summary)
    excl.to_csv(out_dir / "exclusions.csv", index=False)

    elapsed = time.perf_counter() - t_start
    print(f"\nwrote {target} ({len(summary)} rows, {len(summary.columns)} columns)")
    print(f"wrote {out_dir / 'exclusions.csv'}")
    print(excl[excl["plays"] > 0][["reason", "plays"]].to_string(index=False))
    elig = summary[summary["validation_eligible"].astype(bool)]
    if len(elig):
        print(f"eligible plays: {len(elig)}; pressure prevalence {elig['pressure'].mean():.3f}")
    if missing_files:
        print(f"games without a tracking file: {missing_files}")
    if failures:
        print(f"FAILED games ({len(failures)}): {failures}", file=sys.stderr)
    print(f"total time {elapsed:.1f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
