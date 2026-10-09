# Paste into Kiro Agent 1 (user-selected Opus 5.5)

You are Agent 1, responsible for the data engine of Rush Threat Explorer. Repository: https://github.com/Infosuii/AWS-hackathon/. The team has only 90–120 minutes total, and three agents work concurrently. Read SHARED_CONTRACT.md first and follow its exact public APIs, schemas, math, and windows. It is the authority for implementation scope; do not expand the product.

Your exclusive files: rush_threat/geometry.py, rush_threat/data.py, precompute.py, tests/test_geometry.py, tests/test_data.py, tests/test_precompute.py. Do not edit app.py, figure.py, validation.py, requirements.txt, package initializer, or shared documentation. Agent 3 owns environment/dependency versions and integration. Use your own clone/worktree and branch feat/data-engine from the shared bootstrap commit. Do not switch branches in a checkout used by another agent.

The full dataset is available locally. Find its root; accept --data-dir and RUSH_DATA_DIR instead of hard-coding a Windows path. The coordinator's copy is C:/projects/AWS Hackathon/nfl-big-data-bowl-regional-event-data-main/data. Check the Python interpreter locally and coordinate dependencies with Agent 3. Do not invent pinned versions or commit data/virtual environments.

Build in this order:

1. Implement geometry and importable data APIs immediately. Return the exact players/threats/metadata bundle from the contract. Use nullable sector status for missing orientation and deliberate handling of zero-distance bearings. Include QB movement in distance derivatives, real frame gaps, and grouped rolling smoothing. Keep geometry functions pure where useful.
2. Verify real play 2021090900/97: five rushers, pressure True, snap 6, earliest release 38, validation end 31. Publish a working checkpoint and a concise real bundle example to the team within about 25–30 minutes. Agent 2 should already be able to render it; do not wait for all-game preprocessing.
3. Implement build_game_summaries and precompute.py --games 2|all --data-dir PATH --output-dir artifacts. Iterate game files one at a time. Prefer vectorized joins/groupby within each game; do not spend the budget on elaborate optimization. Enumerate actual events and confirm terminal mappings. Retain flagged/excluded play summaries for the replay selector; write explicit exclusion counts.
4. Verify two games, then coordinate with Agent 3 before starting the all-game run so the full pipeline is not run redundantly. Write Parquet if available, CSV otherwise; output identical columns. Report actual timings. Generated summaries remain local in artifacts; teammates regenerate them or transfer them outside Git when necessary.

Meaningful tests: orientation convention and wrap; constant-distance movement; head-on closing; equal QB/rusher velocity; missing-frame denominator; no derivative crossover between rushers/plays; play-97 anchors; play-level OR pressure counting; unique summary keys; exclusions for missing boundaries/orientation; score zero only for valid no-outside observations; minima use capped validation, peaks use replay.

Avoid brittle tests that require a two-game pressure rate of 35–40%, and do not treat every missing tracking player as a fatal whole-run error: report coverage/exclusion problems with useful context. Tests needing the local dataset should skip clearly if it is absent. Keep generic geometry tests runnable anywhere.

Send early checkpoint handoffs using: branch/commit SHA, implemented APIs, commands and results, blockers, any proposed interface change. Never alter interfaces without Agent 3 and Agent 2 agreeing. Commit only your owned files; push your branch when access permits. Do not merge into main, deploy, or rewrite other agents' code. You are done when the real two-game API path and all-game preprocessing work (or a clearly documented external blocker is reported), your tests pass, and integration has the exact contract outputs.
