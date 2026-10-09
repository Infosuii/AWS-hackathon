# Rush Threat Explorer

Rush Threat Explorer is a local Streamlit app that replays NFL Big Data Bowl tracking data (2021 regular season, Weeks 1–8) for a selected dropback, showing each pass rusher's distance and smoothed closing speed to the quarterback beside the field, with an adjustable assumed forward sector drawn from the QB's player orientation (orientation, not gaze). Across all 122 games (8,532 validation-eligible plays, 37.5% with recorded PFF pressure), the closest rusher distance between the snap and the earlier of 2.5 s or the pass/sack/scramble ranks pressured plays above non-pressured ones with AUC 0.696, while proximity counted only outside the fixed 120° sector gives 0.651 (0.678 vs 0.634 when sacks are excluded), so in this data the outside-sector view shows no stronger association than plain proximity. It is meant for coaches, analysts and fans who want to see where and how fast pressure develops on a single play and check sector intuitions against the whole sample. It is exploratory and retrospective, comparing against play-level PFF labels rather than training a pressure model, and the app's methodology expander lists the caveats.

```bash
python -m pip install -r requirements.txt          # Python 3.13; details in submission/SETUP.md
python precompute.py --games all --data-dir /path/to/data --output-dir artifacts
RUSH_DATA_DIR=/path/to/data streamlit run app.py   # tests: RUSH_DATA_DIR=/path/to/data python -m pytest -q
```

Screenshot: `submission/screenshot.png`
