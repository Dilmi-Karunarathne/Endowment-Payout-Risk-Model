# Start here — Endowment Planning & Risk

This is the final simplified model with stress testing and what-if comparisons.
All calculations use the simplified model's investment, spending and cash-funding framework.

## Open the model

Use Python 3.12. Extract the ZIP first; do not run files inside the ZIP viewer.

**Windows:** open the extracted `Endowment_Final_Model` folder and double-click `run_model.bat`.
The first run installs the packages and opens the dashboard in your browser.

**Any computer, from a terminal in the extracted folder:**

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Choose your analysis

| View | Use it to |
|---|---|
| Baseline & strategies | Run one portfolio or compare the three main portfolios. |
| Stress testing | Test high inflation, a prolonged downturn, recession, weak returns, gift reductions, liquidity pressure or historical replays. |
| What-if scenarios | Change spending, gifts, cash reserves or institutional profiles; build a custom scenario. |
| Model guide | Read the assumptions and definitions in plain language. |

Start with **Private / Base / $150M / 5,000 paths**. Run the baseline, then the two
main stress tests. Select **Public** to repeat the analysis for that institution.
Use **Compare the three main strategies** for side-by-side portfolio results.
All nine supplied strategies are available for individual analysis.

Open **Review assumptions before running** to see the exact inputs. The baseline
is automatically included in every stress and what-if comparison. A run can take
several minutes; the progress indicator shows each case as it completes.

Results appear in **Comparison**, **Charts**, and **Details & downloads**. Exports
include the comparison, annual summaries, path-year calculations and run settings.
If you change a setting, run the analysis again to refresh the results.

## Update an existing Streamlit application

Replace the old application files with the **contents** of this folder, including
its data folder and requirements. The entry point remains `app.py`. Commit the
complete update and reboot the app. Run a fresh analysis after deployment.

The final package uses descriptive module names and data paths. Do not combine
individual old and new modules. The original financial framework is preserved,
but old imports and saved result schemas are intentionally incompatible.

See `MODEL_GUIDE.md` for formulas and assumptions, `CHANGES.md` for the changes,
and `VALIDATION.md` for what was tested.
