# Endowment Payout Risk Lab — v2.2

A simplified planning dashboard with advanced analysis tools. This package updates the interface of v2.1 and retains its calculation engine.

## Run locally

Use Python 3.10 or newer (tested on Python 3.12):

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, open PowerShell in the extracted project folder before running these commands. The folder must directly contain app.py and data/.

## Update your existing GitHub main_v2 branch

1. Extract this ZIP.
2. Select main_v2 in your repository.
3. Upload/replace all project files from the extracted folder, including the data/ and tests/ folders. Upload the folder contents, not the ZIP or an extra enclosing folder.
4. Replace the old stress_testing.py and stress_tab.py as well as app.py and the engine. The old stress modules are incompatible.
5. Keep Streamlit's entrypoint as app.py and branch as main_v2. If needed, reboot the existing app after committing.

Do not change main_v1. No new Python packages beyond the previous requirements are required.

## App tabs

1. Overview: three risk cards, real-payout and real-endowment charts with 10th–90th percentile bands, plus expandable detailed outcomes.
2. Strategies: spending/reserve policy comparisons and optional allocation comparisons.
3. Stress tests: adverse market conditions and return sensitivities.
4. Return models: Normal, mixture and bootstrap comparisons.
5. Data & downloads: workbook import, current assumptions, and CSV/settings downloads.
6. Model checks: historical reconstruction, holdout and simulation stability.

The sidebar shows institution type, starting endowment, spending rule, spending rate and horizon. Select Run analysis to populate the dashboard. Technical controls are in Advanced options. Changing settings clears previous results so charts cannot display stale outputs.

The main dashboard has no version, cohort, research-status or pending-data banners. Detailed modeling limitations remain in METHODOLOGY.md and PENDING_INPUTS.md.

To use the new design, upload **app.py**, **dashboard_ui.py**, and **.streamlit/config.toml** along with the other package files. The .streamlit folder supplies the dark teal theme. Keep it in the same project root as app.py.

Unless you enable “Use past endowment values”, the two prior starting values equal your selected starting endowment. Imported workbook histories are selected by default. The three-year spending rule uses three annual valuation points.

## Allocation files

- Return CSV: quarter (e.g. 2007Q1), then one column per asset. Values must be decimal quarterly returns, not percentage numbers or price levels.
- Weight CSV: asset, weight, liquidity_class. Weights must sum to 1. Liquidity classes: Very High, High, Moderate, Low, Very Low.
- Asset names must exactly match the weight file. For the rebuilt anchor, use the exact names in data/p4_weights.csv. The asset CSV must cover both anchor and alternative assets for the same consecutive quarters, with at least 12 quarters.
- Conditions and inflation must match quarters in data/condition_history.csv. Extend this file with documented labels and CPI when extending the return history.
- data/p4_weights.csv is downloadable as the structural template. No invented asset-return template is bundled as empirical data.

Both portfolios are rebuilt from the same quarters; fixed-weight return calibration assumes quarterly rebalancing. Liquidity buckets in the spending engine are carried forward separately as an aggregate capacity approximation.

## Project files

- dashboard_ui.py: chart styling, percentile bands and readable result tables.
- .streamlit/config.toml: application theme.
- endowment_simulation_model.py: core return sampling, annual accounting and payout-risk measures.
- portfolio_return_simulation.py: mixture calibration and three-way comparison.
- strategy_analysis.py: policy comparisons and portfolio construction.
- stress_testing.py: scenarios and one-factor mixture sensitivity.
- stress_tab.py: app stress-results display.
- validation.py: calibration diagnostics, chronological holdout and stability checks.
- tests/: accounting, edge-case and integration checks.
- METHODOLOGY.md: assumptions, timing, risk definitions and limitations.
- PENDING_INPUTS.md: data/decisions still needed from the research teams.
- CHANGELOG.md: changes from the uploaded model.

Run checks from this folder:

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p 'test_app.py' -v
```
