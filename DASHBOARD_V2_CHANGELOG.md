# Simple Model v2 — dashboard redesign

## What changed
- Replaced Simple v1's long, light-colored dashboard with a dark navy, condensed single-page layout matching the user's reference.
- Four headline funding/sustainability cards, four major charts, and expandable risk details.
- Added real sample-path selection for the planned-vs-actual-payout chart: largest observed total payout shortfall, or a representative median-return path when none fails.
- Added a year-zero start to the real endowment chart.
- Improved explanation of the funding-capacity ratio (1x immediate payout coverage) versus R2's separate 3x liquidity guideline.
- Added contextual explanations, data-driven calculated values, and kept CSV downloads.
- Keeps exactly five user-configurable inputs and one baseline simulation.
- All underlying model code (`simple_analysis.py`, `endowment_simulation_model.py`, `r1_model.py`, `payout_funding.py`, `liquidity_model.py`) and R1/R2 datasets unchanged.

## Tested
- Python syntax compilation for app.py.
- Full 100-path Private/Base and Public/Base runs, 500 annual records each; accounting and coverage checks passed.
- Full Streamlit browser launch not verified in this container because `streamlit` is unavailable and package installation is blocked by network restrictions; run locally with `pip install -r requirements.txt`.

## Running
```
cd Endowment_Payout_Risk_Simple_v2
pip install -r requirements.txt
streamlit run app.py
```
