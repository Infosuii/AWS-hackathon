# Rush Threat Explorer

Rush Threat Explorer replays NFL tracking data on a football field alongside synchronized charts of each pass rusher's distance and closing speed to the quarterback. Select a play, move the replay slider or press Play, and adjust the assumed forward sector to explore the rush; a validation panel compares proximity measures against recorded play-level PFF pressure.

The data covers 2021 Weeks 1–8. This is retrospective exploration, not a prediction model; QB orientation is not gaze. Results cover only the games you preprocess.

> [!IMPORTANT]
> **Data is required. Cloning this GitHub repository alone does not give you a working demo.** Download the NFL Big Data Bowl tracking dataset separately and place it in the project folder as shown below, or point `RUSH_DATA_DIR` at an existing copy. The dataset and generated summaries are excluded from GitHub. **Run preprocessing before starting the app:** without summaries the app stops, and without the underlying dataset the replay is unavailable.

## Required data folder

Place the extracted dataset in `data/` next to the root `app.py`:

```text
AWS-hackathon/
├── app.py
├── precompute.py
├── requirements.txt
├── data/
│   ├── games.csv
│   ├── plays.csv
│   ├── players.csv
│   ├── pffScoutingData.csv
│   └── tracking/
│       ├── tracking_2021090900.csv
│       └── ...
└── artifacts/                 # created by preprocessing
    ├── play_summary.parquet   # or play_summary.csv
    └── exclusions.csv
```

The app also recognizes `nfl-big-data-bowl-regional-event-data-main/data/` inside the project folder. You can keep the dataset elsewhere by setting `RUSH_DATA_DIR` to the folder containing the four CSV files and `tracking/`; it does not have to be uploaded to GitHub. The data must be available on the computer or server running the app.

## Run locally (Windows PowerShell)

Use Python 3.13 and obtain the NFL Big Data Bowl tracking dataset separately. Its data folder must contain `games.csv`, `plays.csv`, `players.csv`, `pffScoutingData.csv`, and a `tracking/` folder containing the game tracking CSVs.

1. Clone the repository and open its root folder:

   ```powershell
   git clone https://github.com/Infosuii/AWS-hackathon.git
   cd AWS-hackathon
   ```

2. Create an environment and install the pinned dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Download and extract the dataset into `data/` as shown above, then point the app at it. Run these commands from the repository root, in the same PowerShell session used for preprocessing and starting the app:

   ```powershell
   $env:RUSH_DATA_DIR = (Resolve-Path ".\data").Path
   $env:RUSH_ARTIFACT_DIR = "artifacts"
   ```

   If your dataset is elsewhere, replace the first line with `$env:RUSH_DATA_DIR = "C:\path\to\data"` using your actual dataset location.

4. Prepare the summaries. Start with two games for a quick demo:

   ```powershell
   .\.venv\Scripts\python.exe precompute.py --games 2 --data-dir "$env:RUSH_DATA_DIR" --output-dir "$env:RUSH_ARTIFACT_DIR"
   ```

   Replace `--games 2` with `--games all` to process the full dataset. Generated summaries and raw tracking data stay local.

5. Start the website, then open [http://localhost:8501](http://localhost:8501):

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

   Keep that terminal open while using the app; press **Ctrl+C** to stop it.

To run the tests with the same data settings:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -ra
```

[Example screenshot](submission/screenshot.png) · [Additional setup details](submission/SETUP.md)
