**SUPERSEDED INPUT UNIVERSE:** The results below were produced before the 2026-11-15 Research 1 handoff replaced all portfolios. They are retained for engineering history only and must not be cited as outputs from the new ten portfolios. Current tests are in `validation_updated_r1/` and `UPDATED_R1_HANDOFF_AND_PAYOUT_RISKS.md`.

# Rebalancing correction: current validation report (15 November 2026)

**Root cause corrected:** Target illiquid purchases could exceed the movable portfolio
value; full rebalancing costs were then charged even when no fee-paying liquid
holdings remained. See `REBALANCING_FIX.md` for the precise code change.

## Passed checks

- 8 targeted rebalancing/locked-asset/accounting regression tests.
- 26 extended tests (21 of the longer stress-suite cases were excluded from
  this particular run). These cover the six institutional benchmark profiles,
  return-path matching, gift accounting, restricted assets and two liquidity thresholds.
- Private / Base, $150M, **5,000 matched paths** per strategy: Hierarchical Risk
  Parity, Minimum Variance, and Mean–Conditional Value at Risk (three strategies
  × five years × 5,000 paths = 75,000 path-years). All three runs completed
  with no quarterly rebalancing liquidity error. Maximum annual accounting
  residual across the 75,000 path-years was below 3e-13 $M.
- Public / Base, $150M, **100 matched paths** per strategy: all three runs
  completed as an additional smoke test, with reconciled annual balances.
- Python modules successfully compiled.

## Updated Private/Base outcomes (current 5,000-path model)

| Strategy | Median 5-year investment return (CAGR) | Probability any payout is unpaid | At least one <40% liquid-share observation | At least one <20% observation |
|---|---:|---:|---:|---:|
| HRP | 9.40% | 0.00% | 53.10% | 0.02% |
| Minimum Variance | 7.22% | 0.00% | 0.50% | 0.00% |
| Mean-CVaR | 11.86% | 1.78% | 100.00% | 81.22% |

Source: `validation_output_fixed/private_comparison_5000.csv` and
`private_validation_5000.json`. Simulation probabilities are specific to the
supplied history, assumptions, and fixed seed; they are not empirically
validated forecasts. New results **supersede** the previous 52.2% HRP
liquidity breach figure when discussing this corrected 5,000-path run.

## Not checked in this turn

- A complete full-resolution Public/Base 5,000-path comparison.
- Full 5,000-path coverage across every severe stress, custom scenario and
  every one of the nine investment strategies.
- Live Streamlit browser rendering, because Streamlit is not installed in the
  model-testing runtime. The existing dashboard's structure is unchanged, apart
  from an explanatory note, and its modules compile.

`validation_output/` contains older, pre-correction reports retained for
provenance only. Re-run those before using them as current stress results.

## Reproduction

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q test_rebalancing_cash_constraints.py
python -m pytest -q test_scenarios.py -k 'not main_stress_cases_each_institution_and_strategy and not every_stress_preset and not every_what_if_preset_and_custom'
```

To reproduce the Private/Base production figures, use the application with
**Baseline & strategies → Private → Base → Compare the three main strategies →
5,000 paths → Run analysis**.
