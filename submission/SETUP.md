# Environment and run commands

Tested interpreter: CPython 3.13.15. Python 3.11+ is expected to work; `requirements.txt` pins the versions actually tested (note pandas 3.x: copy-on-write and the default string dtype are on).

```bash
# from the repository root; paths below are examples, use your own dataset location
python3.13 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt

# run tests (python -m puts the repo root on sys.path)
python -m pytest -q
```

The dataset is never committed. Point the tools at your local copy (folder containing games.csv, plays.csv, players.csv, pffScoutingData.csv and tracking/):

```bash
export RUSH_DATA_DIR="/path/to/nfl-big-data-bowl-regional-event-data-main/data"   # PowerShell: $env:RUSH_DATA_DIR="C:/..."
python precompute.py --games 2 --data-dir "$RUSH_DATA_DIR" --output-dir artifacts     # quick demo
python precompute.py --games all --data-dir "$RUSH_DATA_DIR" --output-dir artifacts   # full run (one person)
streamlit run app.py                                     # optional: RUSH_ARTIFACT_DIR=artifacts
```

If `pyarrow` is unavailable, skip it; preprocessing writes `play_summary.csv` and the app reads either format.
