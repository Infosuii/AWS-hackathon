# Rush Threat Explorer

Rush Threat Explorer replays NFL tracking data on a football field alongside synchronized charts of each pass rusher's distance and closing speed to the quarterback. Select a play, move the replay slider or press Play, and adjust the assumed forward sector to explore the rush; a validation panel compares proximity measures against recorded play-level PFF pressure.

The data covers 2021 Weeks 1–8. This is retrospective exploration, not a prediction model; QB orientation is not gaze. Results cover only the games you preprocess.

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

3. Point the app at your dataset and output folder. Replace the example data path:

   ```powershell
   $env:RUSH_DATA_DIR = "C:\path\to\data"
   $env:RUSH_ARTIFACT_DIR = "artifacts"
   ```

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
