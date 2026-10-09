# Rush Threat Explorer: three Kiro agents

Repository: https://github.com/Infosuii/AWS-hackathon/
Budget: 90–120 minutes. Use the user-selected Opus 5.5 model in each Kiro session if available; do not silently substitute a model.

## Assignments

1. Agent 1: data, geometry, preprocessing — `AGENT_1_DATA.md`.
2. Agent 2: synchronized Plotly replay — `AGENT_2_REPLAY.md`.
3. Agent 3: Streamlit, validation, environment, integration, submission — `AGENT_3_APP.md`.

Give each agent its prompt AND `SHARED_CONTRACT.md`. Put the contract in the repository so every agent can read the same copy. All collaborators have the complete dataset locally; dependencies need checking.

The repository appeared empty when inspected. Start Agent 3 first. Agent 3 creates the initial shared commit with the contract, package initializer, requirements, and .gitignore. Agents 1 and 2 can inspect data and prepare their local environment while waiting, then branch from that shared commit. Each agent should use a separate clone/worktree; do not have multiple agents switch branches in one checkout.

## Ownership

| Agent | Exclusive code ownership |
|---|---|
| 1 | rush_threat/geometry.py, rush_threat/data.py, precompute.py, tests/test_geometry.py, tests/test_data.py, tests/test_precompute.py |
| 2 | rush_threat/figure.py, tests/test_figure.py |
| 3 | app.py, rush_threat/validation.py, rush_threat/__init__.py, requirements.txt, .gitignore, README.md, tests/test_validation.py, tests/test_integration.py, submission/ |

Only Agent 3 updates the shared contract after kickoff, with the affected agent's agreement. Agents 1 and 2 should report proposed API changes instead of changing another owner's files. Agent 3 owns merges; all agents help verify.

## Milestones measured from kickoff

- 0–10 min: Agent 3 publishes bootstrap and dependency choices. Agents 1/2 acknowledge contract and send blockers immediately.
- 10–30 min: Agent 1 supplies an importable API and a real play-97 bundle; Agent 2 supplies a synthetic-bundle figure; Agent 3 supplies an app shell and tested AUC.
- 30–55 min: assemble a two-game end-to-end demo. Integrate usable checkpoints, not only final branches.
- 55–75 min: start all-game preprocessing once the two-game path is verified; finish visual and validation wiring in parallel.
- 75–90 min: freeze features, fix integration errors, run the walkthrough.
- If the full 120 min is available: improve readability, choose the clearest real example, capture screenshot and finalize README. Do not add new features.

## Branches and handoffs

Use `feat/data-engine`, `feat/replay`, and `feat/app-validation`; Agent 3 assembles `integration/rush-threat`. Push clean checkpoints to each agent's own branch when repository access permits. Do not force-push or commit generated tracking files, environments, secrets, or the full dataset. No deployment is needed.

Each handoff reports: branch + commit SHA; owned files; exact command executed; result; remaining blocker; interface changes (normally none). Agents 1/2 do not merge into main. Agent 3 merges checkpoint branches into the integration branch, resolves cross-module wiring, and reports the final working revision to the team. PRs are optional if they take time; the working integration branch is the priority.

## When something is late

- No pyarrow: write CSV using the same columns and continue.
- Full preprocessing slow: keep a clearly labeled two-game demo available while the all-game job continues. Do not present partial results as all 122 games.
- No animation yet: synchronized frame slider is the minimum; animation is still the preferred target.
- Missing orientation: render players and distance timelines with an explicit note; no wedge or inside/outside claim for that frame.
- One-class validation subset: show AUC unavailable.
- Interface mismatch: Agent 3 coordinates one agreed fix; do not independently invent adapters in three places.

## Final acceptance

Working local Streamlit app; real tracking replay with synchronized cursors; correct geometry and alerts; full-data or explicitly labeled partial validation with exclusions and no-sack sensitivity; clean startup/test check; Python source and requirements; an actual screenshot/output; a README of 3–5 sentences explaining what was built, what it reveals, and who uses it.
