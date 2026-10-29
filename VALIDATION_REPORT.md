# Final-model stress update — validation

All 32 tests passed: 17 existing model tests, 4 Streamlit workflow tests, and 11 new stress/regression tests.

The unchanged baseline is verified against annual outputs and metrics generated directly from the uploaded main_v5 engine: 20 paths, four years, Single Normal, seed 42 and fixed 2.5% inflation. Every original annual column and metric matches within numerical tolerance. The small CSV/JSON fixtures in tests preserve this reference without shipping a second engine.

Stress checks cover both primary scenarios, quarter-exact inflation duration, forced-regime CPI versus fixed CPI, historical replay, capital-call asset transfers, unpaid calls, priority of cash obligations, forced-sale accounting, gift/expense/special-draw timing, every scenario-library preset, reverse stress, sensitivity and invalid inputs. UI tests cover selection, adjustable path counts, hidden advanced controls, custom scenarios, downloads rendering, and stale-result removal.

The actual app was opened in Chromium and visually checked. It retains the existing dashboard style, with two primary checkboxes, separate settings, a path-count selector, focused results, and optional advanced tools.

The two main scenarios and baseline were also run at 500 paths over ten years. Maximum absolute accounting residual: 1.706e-13 $M. Results and exact settings are in validation_outputs/main_stress_comparison_500.csv and main_stress_settings.json. These are execution checks with illustrative assumptions, not evidence of empirical calibration or stable tail estimates.

Run tests: python -m unittest discover -s tests -v
Reproduce scenario outputs: python scripts/validate_stress_update.py

No GitHub branch or live Streamlit deployment was changed.
