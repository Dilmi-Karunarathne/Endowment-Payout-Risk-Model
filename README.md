**Current version: v11 — Dashboard usability and comparison-column correction.**
Read [`INTERFACE_V11_RELEASE_NOTES.md`](INTERFACE_V11_RELEASE_NOTES.md) first.
The latest Research 1 investment data, payout and liquidity formulas, scenario
engine and cash-flow calculations remain unchanged from v10.

**Portfolio update (15 Nov 2026):** The model now uses the 10 final portfolios supplied in `R3HandoffPackage.zip`. The Payout Risk Measures tab is visible after a run. See `UPDATED_R1_HANDOFF_AND_PAYOUT_RISKS.md`. Previous validation outputs and benchmark returns **do not apply** to these portfolios.

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
- Ten Research 1 November 2026 portfolios (five final strategies × Static/Dynamic); a matched comparison of three representative Dynamic portfolios.
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
| data/investment/ | Updated November 2026 portfolio inputs, asset-shock recommendations, and source-specific liquidity profiles |
| validation_updated_r1/ | New 5,000-path HRP Dynamic baseline validation summaries for Private and Public |

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q test_updated_handoff.py test_scenarios.py test_stress_policy_improvements.py test_rebalancing_cash_constraints.py
# Dashboard AppTest additionally requires the Streamlit package; run `python -m pytest -q test_app.py` in your Streamlit environment.
python test_dashboard_contract.py
python validate_production.py
```

The last command runs 5,000 paths for Private/Base HRP Dynamic under baseline and two severe shocks; this is a separate, potentially long production test. Current updated-handoff baselines are provided in `validation_updated_r1/`.

Complete management fees and a comparable 70/30 return history remain outside
this release. Scenarios are conditional illustrations, not forecasts.


### Quarterly rebalancing cash constraint (fixed)
The simulator now executes only *fundable* quarterly target-weight trades. Private holdings remain locked as specified, and the engine defers a trade rather than raising an error when its fees cannot be paid from accessible liquid holdings. See `REBALANCING_FIX.md`.


## NEW: Stress impact and policy-response analysis

Choose **Stress testing** to compare the supplied adverse conditions with matched unchanged baselines. Choose **Policy responses under stress** to keep the exact same stress and compare an explicitly fixed lower spending rate or modified cash reserve; this produces baseline, stress, and stress-with-policy outcomes. The **Stress diagnostics** results tab reports return changes, payout failures, liquidity buffers, real purchasing power, and detailed cash-flow movements.

See `STRESS_POLICY_UPDATES.md` for the complete definitions, caveats, and tests. The policy experiment does **not** automatically react to liquidity breaches. A reverse-stress threshold search and full net management fees remain outside this release.
