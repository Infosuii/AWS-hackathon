"""Retrospective comparison of two proximity scores against recorded PFF pressure.

Descriptive only: no training, thresholds, or incremental-value claims.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

NGS_PRESSURE_URL = "https://www.nfl.com/news/next-gen-stats-introduction-to-pressure-probability"
FULL_DATASET_GAMES = 122  # 2021 regular season Weeks 1-8 in this dataset

_TRUE = {"true", "t", "1", "1.0", "yes", "y"}
_FALSE = {"false", "f", "0", "0.0", "no", "n"}


def parse_bool(values) -> pd.Series:
    """Explicit, dtype-agnostic Boolean parsing; unknown values become <NA>."""
    s = pd.Series(values)

    def one(v):
        if v is None or v is pd.NA:
            return pd.NA
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if isinstance(v, (int, float, np.integer, np.floating)):
            if isinstance(v, (float, np.floating)) and math.isnan(v):
                return pd.NA
            return True if v == 1 else False if v == 0 else pd.NA
        text = str(v).strip().lower()
        return True if text in _TRUE else False if text in _FALSE else pd.NA

    return pd.Series([one(v) for v in s], index=s.index, dtype="boolean")


def auc(scores, labels) -> float:
    """Average-rank (Mann-Whitney) AUC; ties get average ranks.

    Observations with a non-finite score or unknown label are dropped.
    Returns NaN with no usable observations or fewer than two label classes.
    """
    s = pd.to_numeric(pd.Series(scores).reset_index(drop=True), errors="coerce").astype("float64")
    y = parse_bool(pd.Series(labels).reset_index(drop=True))
    keep = np.isfinite(s.to_numpy()) & y.notna().to_numpy()
    s, y = s[keep], y[keep].astype(bool)
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = s.rank(method="average")
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def normalize_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce saved Parquet/CSV summaries to consistent dtypes."""
    out = df.copy()
    for col in ("gameId", "playId"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    out = out[out["gameId"].notna() & out["playId"].notna()].copy()
    for col in ("pressure", "validation_eligible", "replay_available"):
        out[col] = parse_bool(out[col]) if col in out else pd.Series(pd.NA, index=out.index, dtype="boolean")
    for col in ("season", "week", "down", "yardsToGo", "blockers", "rushers", "routes", "snap_frame",
                "terminal_frame", "validation_end_frame", "validation_duration_s", "d_min_any",
                "d_min_outside", "score_any", "score_outside", "peak_close_5yd", "peak_rusher_id",
                "peak_frame"):
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ("passResult", "possessionTeam", "defensiveTeam", "exclusion_reasons", "playDescription"):
        if col in out:
            out[col] = out[col].astype("string").str.strip()
    return out.reset_index(drop=True)


def split_reasons(value) -> list[str]:
    if isinstance(value, (list, tuple, np.ndarray)):
        return [str(v).strip() for v in value if str(v).strip()]
    if value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value)):
        return []
    return [p for p in re.split(r"[;|,\s]+", str(value)) if p]


def cohort(summary: pd.DataFrame, exclude_sacks: bool = False) -> tuple[pd.DataFrame, dict]:
    """Eligible plays with a known label and BOTH scores finite (same rows for both features)."""
    df = summary
    if exclude_sacks:
        df = df[df["passResult"].fillna("").astype(str).str.strip().str.upper() != "S"]
    eligible = df[df["validation_eligible"].fillna(False).astype(bool)]
    labelled = eligible[eligible["pressure"].notna()]
    both = np.isfinite(labelled["score_any"].astype("float64")) & np.isfinite(
        labelled["score_outside"].astype("float64"))
    rows = labelled[both]
    return rows, {
        "eligible": len(eligible),
        "dropped_unknown_pressure": len(eligible) - len(labelled),
        "dropped_missing_score": int((~both).sum()),
    }


def compare(summary: pd.DataFrame, exclude_sacks: bool = False) -> dict:
    rows, info = cohort(summary, exclude_sacks)
    y = rows["pressure"].astype(bool)
    n = len(rows)
    return {
        **info,
        "n": n,
        "n_pressure": int(y.sum()),
        "pressure_rate": float(y.mean()) if n else float("nan"),
        "auc_any": auc(rows["score_any"], y),
        "auc_outside": auc(rows["score_outside"], y),
    }


def exclusion_counts(summary: pd.DataFrame) -> pd.DataFrame:
    """Per-reason counts among ineligible plays (a play may have several reasons)."""
    ineligible = summary[~summary["validation_eligible"].fillna(False).astype(bool)]
    reasons = [r for v in ineligible["exclusion_reasons"] for r in split_reasons(v)]
    counts = pd.Series(reasons, dtype="string").value_counts()
    return counts.rename_axis("reason").reset_index(name="plays")


def scope(summary: pd.DataFrame) -> dict:
    weeks = sorted(int(w) for w in summary["week"].dropna().unique()) if "week" in summary else []
    seasons = sorted(int(s) for s in summary["season"].dropna().unique()) if "season" in summary else []
    return {
        "games": int(summary["gameId"].nunique()),
        "plays": len(summary),
        "eligible": int(summary["validation_eligible"].fillna(False).astype(bool).sum()),
        "weeks": weeks,
        "seasons": seasons,
    }
