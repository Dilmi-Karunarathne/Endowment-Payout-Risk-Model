# Validation record — 8 November 2026

Automated regression suite: 26 tests covering R1 integration, R2 institutional assumptions and the retained legacy liquidity functions.

Checks include all nine strategies under both institutional cohorts, weight normalization, Private-to-Public MeanCVaR mapping, common random asset/CPI draws, private-sleeve pacing, first-quarter forced regime switching, current-weight buy-and-hold historical replay, inflation compounding, additive return-drag timing, capital-call/withdrawal accounting, and liquidity breaches remaining separate from payout cuts.

Streamlit AppTest completed with 100 paths per analysis:
- Baseline, policy comparisons and both primary stresses.
- Payout/overview page.
- Severe primary stresses.
- All-nine-strategy comparison.
- Data page and Public MeanCVaR full main analysis.

These are implementation and UI checks. They do not establish forecast accuracy, independently validate R1's optimizer, verify external literature claims, or constitute real-institution calibration. No live deployment was performed.

Run locally: `python -m unittest test_r1 test_r2 test_liquidity -v`.
UI exercise: `python ui_smoke.py` (requires Streamlit; takes several minutes).
