---
inclusion: always
---

# Rush Threat Explorer: Project Guidelines

## Frameworks

- Streamlit (UI and app entrypoint)
- Pandas (tabular data handling)
- NumPy (vector math)
- Plotly (interactive charts)

## Python Version

- Python 3.10+ (use modern type-hint syntax such as `pd.DataFrame | None` and `list[str]`).

## Data Schema Contract

Tracking DataFrames contain columns:

```python
['gameId', 'playId', 'frameId', 'nflId', 'x', 'y', 's', 'o', 'dir', 'club', 'displayName', 'pff_role']
```

Notes on source mapping:

- Raw `data/tracking/tracking_<gameId>.csv` files name the team column `team`; it is renamed to `club`.
- `pff_role` comes from `data/pffScoutingData.csv`, joined on `gameId`, `playId`, `nflId`.
- `displayName` comes from `data/players.csv`, joined on `nflId`.

## Rules

- Never edit code outside your explicitly assigned module file.

## Module Ownership Map

| File | Responsibility |
| --- | --- |
| `src/data.py` | Vector math and preprocessing (loading, closing speed, forward sector) |
| `src/components.py` | Plotly charts (field replay, proximity timeline) |
| `src/validation.py` | Validation metrics (rush threat vs. pressure/sack outcomes) |
| `app.py` | Streamlit entrypoint and layout only; no business logic |
