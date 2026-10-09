# Frozen contract: Rush Threat Explorer v1

All three agents must implement this contract. Time budget is 90–120 minutes. Build a local visualization/comparison tool, not a pressure prediction model. No new metric weights, time-to-contact, causal claims, or feature expansion.

## Paths and dependencies

Source package: `rush_threat/`. Entry points: `precompute.py` and `app.py`.
Dataset root contains games.csv, plays.csv, players.csv, pffScoutingData.csv, and tracking/tracking_<gameId>.csv. On the coordinator's machine it is `C:/projects/AWS Hackathon/nfl-big-data-bowl-regional-event-data-main/data`; other machines may use another path. Accept `--data-dir` in preprocessing and `RUSH_DATA_DIR` in the app; never hard-code a collaborator's path.
Output directory: `artifacts/`, ignored by Git. Primary output `play_summary.parquet`; CSV fallback `play_summary.csv`; exclusions report `exclusions.csv`. App accepts `RUSH_ARTIFACT_DIR`, default artifacts.
Agent 3 owns dependency versions: pandas, numpy, streamlit, plotly, pyarrow (optional with CSV fallback), pytest (development). Avoid extra dependencies, sklearn, kaleido, and deployment setup.

## Public data API (Agent 1)

```python
load_context(data_dir) -> dict[str, pandas.DataFrame]
# keys: games, plays, players, scouting

load_game_tracking(data_dir, game_id: int) -> pandas.DataFrame

build_play_bundle(game_tracking, context, game_id: int, play_id: int,
                  sector_deg: float = 120.0) -> dict
# keys: players, threats, metadata; schemas below

build_game_summaries(game_tracking, context) -> pandas.DataFrame
# fixed 120-degree sector; all plays retained with eligibility flags
```

Return schemas are also usable as synthetic fixtures; the figure must not import the data loader or assume it can access CSVs. Game/play/nfl IDs are numerically joinable; nullable nflId is reserved for the ball.

### bundle['players']: one row per frame/entity

Required columns: frameId, nflId, x, y, o, jerseyNumber, displayName, role, time_from_snap.
Role vocabulary: qb, rusher, blocker, route, coverage, ball, other. Use normalized PFF roles to map players; football is ball. Preserve native field coordinates (x 0–120, y 0–53.3), without mirroring. Include all tracked players and the ball. Unknown roles become other. This table covers the replay window.

### bundle['threats']: one row per frame/rusher

Required columns: frameId, nflId, displayName, jerseyNumber, x, y, qb_x, qb_y, qb_o, time_from_snap, distance, closing_speed, bearing_deg, outside_sector, in_validation.
outside_sector is nullable Boolean: missing orientation is unknown, not inside. distance is yards and closing_speed is yards/second. First derivative samples may be NaN. Return the requested sector angle. No duplicated (frameId, nflId) keys.

### bundle['metadata']: plain dict

Required keys: gameId, playId, playDescription, possessionTeam, defensiveTeam, passResult, down, yardsToGo, offenseFormation, dropBackType, pff_playAction, blockers, rushers, routes, pressure, snap_frame, terminal_frame, terminal_event, validation_end_frame, sector_deg, validation_eligible, exclusion_reasons, replay_available, replay_note.
Use None for missing frames. exclusion_reasons is a list of short codes. For missing snap/terminal, provide a flagged whole-play fallback replay if a QB is available; inferred boundaries must not enter validation. Missing QB means replay unavailable and a clear note, not a crash.

### Summary: one row per (gameId, playId)

Fields: gameId, playId, season, week, playDescription, possessionTeam, defensiveTeam, passResult, down, yardsToGo, offenseFormation, dropBackType, pff_playAction, blockers, rushers, routes, pressure, snap_frame, terminal_frame, terminal_event, validation_end_frame, validation_duration_s, validation_eligible, exclusion_reasons, replay_available, d_min_any, d_min_outside, score_any, score_outside, peak_close_5yd, peak_rusher_id, peak_frame.
exclusion_reasons is a delimiter-separated string in saved tables. Retain ineligible plays for selection, but filter them out for validation. peak values describe the full replay window; minima/scores describe only the validation window. No qualifying alert gives NaN peak values, not a fabricated zero-time event. Metadata fields need safe missing-value handling in CSV and Parquet.

## Football and math definitions

- Pressure: any defender credited with pff_hit OR pff_hurry OR pff_sack == 1, once per play. Include pressure labels for all defenders, even if their initial PFF role was coverage. For the visualization, rushers are initial PFF Pass Rush; QB is PFF Pass. Normalize capitalization/whitespace. Require one identifiable QB.
- Roles are scouting classifications, not proof that every blocker stayed in throughout the play.
- Angles: 0 degrees points +y, 90 points +x, clockwise. unit_vec(angle) = (sin(angle), cos(angle)); bearing = degrees(atan2(dx, dy)) modulo 360. Wrapped angular difference is 0–180. Outside means difference > sector_deg/2. Zero-distance bearing is undefined; flag/handle it explicitly rather than inventing awareness.
- time_from_snap = (frameId - snap_frame)/10. Closing speed = -delta(distance)/(delta(frameId)/10), sorted/grouped by gameId, playId, nflId. Centered 3-observation rolling smoothing, within the replay window only; never use post-terminal positions. This is retrospective. A missing frame gap changes the derivative denominator. Constant-distance motion has approximately zero closing speed.
- Replay begins at ball_snap (use a documented autoevent_ballsnap fallback if needed). Terminal is the earliest recognized release, sack, or scramble onset after snap. Release candidates: pass_forward, autoevent_passforward, pass_shovel. Enumerate actual dataset events to confirm sack/scramble mappings; document fallbacks. Earliest event is a consistent convention, not independently verified exact release time.
- Validation ends at min(snap_frame + 25, terminal_frame - 1), inclusive, starts at snap, and requires at least one valid pre-terminal distance sample. Thus play 97 uses frames 6–31. Missing snap/terminal, missing QB/rushers, or missing/undefined orientation within the otherwise eligible threat observations is conservatively flagged for exclusion. Both feature scores use the same eligible plays. Do not drop raw excluded plays from the selector.
- score_any = 1/(1 + minimum validation-window distance). score_outside = the same formula for validation-window observations outside the fixed 120-degree sector. If orientation is valid but there are no outside observations: d_min_outside = NaN and score_outside = 0. Missing/invalid orientation is not this zero case.
- Alert: at each frame, select the highest positive smoothed closing_speed among rushers at distance <= 5 yards. Ignore nonfinite speed. A deterministic nflId tie-break is sufficient. Zero or no eligible candidates means no alert. Sector status describes the selected rusher; it does not gate selection. Peak alert is the greatest qualifying closing speed over the replay window.

## Public figure API (Agent 2)

```python
build_figure(bundle: dict) -> plotly.graph_objects.Figure
select_alert(frame_threats: pandas.DataFrame, radius_yd: float = 5.0)
# returns selected row (Series) or None
```

One figure: field left; distance and closing-speed timelines right. Plotly frames/slider update players, wedge, alert line/annotation, and both cursors. Rusher color consistent across panels. Static curves come from bundle threats; markers identify terminal and peak alert. No Streamlit calls or CSV reading in figure.py. The app's angle slider rebuilds the bundle and figure; validation stays at 120 degrees.
Annotate distance and speed, and inside/outside/unknown assumed forward sector. Missing orientation hides the wedge and clearly shows unknown. Never say unseen, gaze, actual vision, guaranteed contact, or frame-level PFF pressure onset.

## Validation API (Agent 3)

```python
auc(scores, labels) -> float
# average ranks for ties; NaN if fewer than two classes
```

One observation per eligible play. Show baseline and sector AUC, sample size, pressure prevalence, distributions, exclusion counts, and repeat after excluding passResult == 'S'. Report actual results even if orientation performs worse. App team/play filters affect selection; the main validation panel remains on the entire precomputed dataset and explicitly states its scope. No training or tuned threshold claims.

NGS_PRESSURE_URL = https://www.nfl.com/news/next-gen-stats-introduction-to-pressure-probability
Caveats: retrospective association; play-level PFF labels; QB turning and alignment confounding; early sack proximity and differing observation lengths; initial-role rusher coverage; sector comparison does not establish incremental prediction value. Put brief relevant labels inline and fuller methodology in an expander.

## Verified fixture and presentation

2021090900 / play 97: five rushers, pressure True, snap frame 6, terminal frame 38 (autoevent_passforward), validation end 31. Later pass_forward occurs at 40. Dataset is 2021 Weeks 1–8, not the 2023 split described in the event brief.
App title: Rush Threat Explorer. Wedge label: assumed forward sector. Orientation is player orientation, not gaze. Default example: play 97 until a clearer real example is selected. No fake validation numbers. Final deliverables: runnable Python, requirements, screenshot/output, and a 3–5-sentence README.
