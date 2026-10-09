# Paste into Kiro Agent 2 (user-selected Opus 5.5)

You are Agent 2, responsible for the main visual of Rush Threat Explorer. Repository: https://github.com/Infosuii/AWS-hackathon/. Three agents have 90 minutes total. Read SHARED_CONTRACT.md and implement its exact bundle schema and figure API. Your job is the synchronized tracking visualization, not data preprocessing or app infrastructure.

Your exclusive files: rush_threat/figure.py and tests/test_figure.py. Agent 1 owns geometry/data/precompute; Agent 3 owns Streamlit, validation, requirements, package initialization, and integration. Use your own clone/worktree and branch feat/replay from the shared bootstrap commit. No shared-checkout branch switching. Do not edit another agent's files or independently change dependencies.

Implement build_figure(bundle) -> Plotly Figure and select_alert(frame_threats, radius_yd=5) -> Series|None exactly as the contract specifies. No CSV access or Streamlit imports in figure.py. Preserve native field coordinates and make x/y scale physically consistent on the field; do not mirror player positions without an agreed transform.

Start immediately with a small synthetic bundle matching the documented players/threats/metadata schemas, built inside your own test file. Label it synthetic wherever rendered for development. Do not wait for Agent 1 to complete preprocessing. Publish a working synthetic figure checkpoint within about 25–30 minutes, then replace the development fixture with Agent 1's real play-97 bundle for verification.

Visual target:

- One Plotly figure: field left; distance and closing-speed timelines stacked right, sharing time.
- QB visibly identifiable. Rushers have consistent distinct colors across field/timelines. Other offensive/defensive roles remain understandable; football is separate. Jersey labels are readable.
- Filled assumed-forward-sector wedge at current QB orientation, about 7-yard display radius. Use (sin, cos) angle convention. Read sector_deg from metadata. Missing orientation means no wedge and unknown sector status.
- Each Plotly animation frame updates positions, wedge, alert, annotation and both timeline cursors. Provide play/pause and frame slider. Keep trace indexes stable by explicitly mapping dynamic traces; static timelines must survive animation.
- Alert is the fastest positively closing rusher within 5 yards; if none, hide the line and show no qualifying alert. Direction relative to the sector is an annotation, not an extra selection condition. No unsupported claim that the QB cannot see a player.
- Static 5-yard distance reference, terminal marker, and peak-alert marker. No fabricated peak when no alert occurs. Timeline curves have consistent rusher colors; avoid elaborate per-frame line-style segmentation.
- Frame transitions should not visually interpolate players in ways that misrepresent missing observations. Missing tracking rows and NaN speeds must render gracefully. Hover details should explain yards and yards/second.

Tests: correct alert within radius; reject zero/negative/nonfinite closing speed; deterministic ties; no alert when empty; figure frame count matches replay frames; wedge convention; cursor and alert updates address intended traces; synthetic missing orientation/no-alert paths do not crash. These tests should require no dataset or app startup.

Prioritize a reliable synchronized slider and readable figure first, then play/pause. Do not add models, time-to-contact, rankings, extra chart libraries, or deployment. Agent 3 will inspect the real browser rendering; report any visual dimensions or defaults they need.

Handoff: branch/commit SHA, owned files, tested commands/results, screenshot/HTML preview if available without new dependencies, remaining issues. Push usable checkpoints to feat/replay when access permits; do not merge main. Final success is one figure that works with both synthetic and real contract bundles, synchronized cursor motion, honest wedge labels, and passing focused tests.
