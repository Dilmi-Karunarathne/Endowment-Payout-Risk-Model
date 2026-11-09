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

## Interface update verification
Streamlit AppTest: baseline and primary stress runs at 100 paths passed; all seven navigation views rendered without app exceptions, and changing institution/strategy cleared stale results. The R1 dynamic, endowment, scenario and strategy engine source files were byte-compared against the preceding release and were unchanged. Chart bands use computed simulation quantiles, not illustrative values. The reference was visually inspected; the redesigned app was verified through AppTest, not a browser screenshot (the remote browser could not connect to the local app).
