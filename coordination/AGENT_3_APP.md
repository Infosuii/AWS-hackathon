# Paste into Kiro Agent 3 (user-selected Opus 5.5)

You are Agent 3, responsible for Streamlit, validation, environment bootstrap, integration, and submission artifacts for Rush Threat Explorer. Repository: https://github.com/Infosuii/AWS-hackathon/. Three agents have 90–120 minutes total. You are the single integration owner; all teammates can review/test, but avoid parallel merges or competing changes to shared files.

Read SHARED_CONTRACT.md. Your exclusive files: app.py, rush_threat/validation.py, rush_threat/__init__.py, requirements.txt, .gitignore, README.md, tests/test_validation.py, tests/test_integration.py, and submission/. Agent 1 owns geometry/data/precompute and Agent 2 owns figure.py. Do not silently change their interfaces. Own shared contract/document edits only when the affected agent agrees.

Bootstrap first, within about 10 minutes:

1. Inspect repository instructions and existing state. The repo appeared empty to the coordinator, so establish a shared initial commit if it is still empty. Include SHARED_CONTRACT.md, the package initializer, requirements, and .gitignore. Publish this bootstrap as the agreed starting revision; tell Agents 1 and 2 its SHA and branch. Do not overwrite a now-existing repo or force-push. Your development branch is feat/app-validation; assemble teammates on integration/rush-threat in your own checkout/worktree.
2. Check Python availability and install the minimal agreed dependencies in a local environment. pandas, numpy, streamlit, plotly; pyarrow if available; pytest for development. Record tested resolved versions in requirements.txt. Use CSV if Parquet causes delay. Share interpreter/version/install commands with collaborators so they can reproduce the environment. Do not assume the coordinator's runtime paths apply to their machines.
3. Ignore local datasets, artifacts/, virtual environments, caches, and secrets. Do not upload the 850 MB tracking dataset. Keep ignored artifact output available locally for the demo. The existing data folder name can differ by machine.

Your build:

- App title Rush Threat Explorer. Accept RUSH_DATA_DIR and RUSH_ARTIFACT_DIR. Read Parquet or CSV summaries without assuming identical inferred Boolean dtypes; parse pressure/eligibility explicitly. If preprocessing is missing, show an actionable command and stop cleanly.
- Sidebar: team, pressure yes/no, passResult, play selector, sector angle 60–180 degrees default 120. Selection shows a context card and the real full replay via Agent 1's build_play_bundle and Agent 2's build_figure. Cache context and per-game loading; do not read all tracking files on app startup. Angle changes rebuild only the selected play bundle/figure.
- Default to play 2021090900/97 when present; handle filtered-out defaults, empty selections, missing replay data, and missing orientation safely.
- Validation uses the whole precomputed dataset (not sidebar play filters), visibly states data scope and fixed 120 degrees, and filters validation_eligible. Display baseline score_any versus score_outside AUC, n, pressure rate, and distributions, plus the same comparison excluding passResult S. Show exclusions. Do not imply the outside-sector feature improves a model. No invented results.
- Implement average-rank AUC without sklearn. Correct ties; NaN/unavailable for a single label class or no usable observations. Test perfect/reversed/tied and single-class cases, and verify both features use the same cohort.
- Brief inline labels: assumed forward sector, player orientation is not gaze, closing speed units, recorded PFF pressure is play-level. Put full methodology and caveats in an expander using https://www.nfl.com/news/next-gen-stats-introduction-to-pressure-probability . Show actual 2021 Weeks 1–8 dataset scope and how many games were processed.

Integration schedule:

- By roughly minute 30: have an app shell and tested AUC; request Agents 1/2 checkpoint SHAs. Use lightweight contract fixtures in your own tests until their modules arrive; never present fixture numbers as real analysis.
- By minute 55: merge their usable checkpoints into integration/rush-threat and run the real two-game demo. Coordinate source fixes with the module owner rather than creating separate competing adapters. Ensure both timeline cursors move with the field slider in a browser.
- Once two-game processing and replay work: coordinate one full-data preprocessing run, record runtime and game/exclusion counts. Continue polish in parallel. Do not run multiple full jobs unnecessarily.
- Around minute 75: feature freeze. Run focused tests and a clean Streamlit startup/walkthrough. Use the remaining 15–45 minutes for bugs, readable layout, and actual submission output.

Final artifacts: committed runnable source and reproducible requirements, a real screenshot in submission/ (browser screenshot is fine; no extra export libraries solely for this), and README.md with the event-required 3–5 sentences covering what it does, what it reveals, who uses it, the exploratory nature, and compact startup instructions. Put detailed setup in app help or another owned submission file if necessary to preserve README length. Explicitly label partial-data results if the all-game run has not completed.

Report a concrete final handoff: integration branch/commit, exact setup/precompute/run/test commands, actual verification results, screenshot path, dataset scope, limitations, and any remaining blocker. Leave the working integration branch available to all collaborators. No website deployment, model expansion, force-push, or secret/data upload. If interface changes are unavoidable, inform both agents and update the single contract before they implement conflicting versions.
