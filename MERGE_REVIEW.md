# Consolidation review — 8 November 2026

Compared original main_v7 with original Dilmi_v6_update, then retained the final R2 integration. No unique non-liquidity v7 implementation was found missing from Dilmi. Conflicting legacy liquidity behavior is intentionally replaced, not duplicated.

| File | Original versions | Resolution |
|---|---|---|
| ASSUMPTIONS_AND_CONFIRMATIONS.md | Dilmi addition | Retained revised liquidity implementation/documentation |
| README.md | Differs | Retained revised liquidity implementation/documentation; final R2 integration applied |
| VALIDATION.md | Dilmi addition | Retained revised liquidity implementation/documentation |
| app.py | Differs | Retained revised liquidity implementation/documentation; final R2 integration applied |
| dashboard_home.py | Differs | Retained revised liquidity implementation/documentation |
| dashboard_ui.py | Identical | Retained common file |
| data/asset_monthly_returns.csv | Identical | Retained common file |
| data/calibration.csv | Identical | Retained common file |
| data/condition_history.csv | Identical | Retained common file |
| data/liquidity_matrix.csv | Dilmi addition | Retained revised liquidity implementation/documentation |
| data/r2_scenarios.csv | Identical | Retained common file; final R2 integration applied |
| data/six_portfolio_weights.csv | Identical | Retained common file |
| data/transition_matrix.csv | Identical | Retained common file |
| endowment_simulation_model.py | Differs | Retained revised liquidity implementation/documentation; final R2 integration applied |
| icon/GSU-logo.jpg | Identical | Retained common file |
| liquidity_model.py | Dilmi addition | Retained revised liquidity implementation/documentation |
| portfolio_return_simulation.py | Identical | Retained common file |
| requirements.txt | Identical | Retained common file |
| scenario_stress.py | Differs | Retained revised liquidity implementation/documentation; final R2 integration applied |
| strategy_analysis.py | Identical | Retained common file |
| stress_tab.py | Differs | Retained revised liquidity implementation/documentation; final R2 integration applied |
| test_liquidity.py | Dilmi addition | Retained revised liquidity implementation/documentation; final R2 integration applied |
| validation.py | Identical | Retained common file |

## Validation and limits
17 calculation tests passed after consolidation review. Startup, stress panel and severe selector smoke checks passed during R2 integration; executable code is unchanged since those checks.
No live deployment. No automatic regime-driven portfolio switching. Professor’s monitoring-only liquidity replacement remains pending; this package retains the supplied matrix funding engine.
See R2_UPDATE.md for all interim assumptions and R2 integration details.
