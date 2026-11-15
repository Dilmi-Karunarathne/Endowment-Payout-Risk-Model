# Endowment Planning & Risk

A Streamlit application for five-year endowment investment, payout and liquidity
analysis. The final release adds stress tests and policy comparisons to the
existing simplified model without replacing its financial engine.

Read **START_HERE.md** for setup and use, and **MODEL_GUIDE.md** for methodology.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Python 3.12 was used for validation. Monetary units are USD millions.

## Features

- Private and Public institutions, each with Low / Base / High profiles.
- Nine investment strategies; a matched comparison of the three main strategies.
- Standard and severe inflation/downturn tests, recession, weak-return,
  stagflation, gift, liquidity and historical-replay scenarios.
- Spending, gifts, reserve and institutional-profile sensitivities plus a custom case.
- Matched market paths, scenario-versus-baseline changes, explanatory assumptions,
  a model guide, and downloadable calculations.

## Files

| File | Purpose |
|---|---|
| app.py | User interface and exports |
| simple_analysis.py | Shared configuration, reconciliation and reporting |
| scenario_analysis.py | Stress presets, scenario transformations and comparisons |
| endowment_simulation_model.py | Existing annual endowment and Monte Carlo engine |
| investment_model.py | Joint asset/inflation bootstrap and quarterly holdings |
| payout_funding.py | Cash-first funding and asset-sale accounting |
| data/institutional_profiles.csv | Existing Private/Public benchmark profiles |
| data/institutional_stress.csv | Supplied institution-specific gift and expense stresses |
| data/investment/ | Existing portfolio data and supplied market-shock table |
| validation_output/ | Reproducible production validation summaries |

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q test_scenarios.py test_app.py
python test_dashboard_contract.py
python validate_production.py
```

The last command runs 5,000 paths for the Private/Base/HRP baseline and both main
severe stress tests, then writes summaries and a sample calculation path.

Complete management fees and a comparable 70/30 return history remain outside
this release. Scenarios are conditional illustrations, not forecasts.


### Quarterly rebalancing cash constraint (fixed)
The simulator now executes only *fundable* quarterly target-weight trades. Private holdings remain locked as specified, and the engine defers a trade rather than raising an error when its fees cannot be paid from accessible liquid holdings. See `REBALANCING_FIX.md`.
