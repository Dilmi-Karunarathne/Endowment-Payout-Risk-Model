# Start here — Endowment Planning & Risk

This is the updated model combining the November 2026 final portfolio handoff with stress testing and payout-risk analysis.
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
| Policy responses under stress | Compare a severe downturn with the same downturn under an alternative spending or reserve policy. |
| What-if scenarios | Change spending, gifts, cash reserves or institutional profiles; build a custom scenario. |
| Model guide | Read the assumptions and definitions in plain language. |

Start with **Private / Base / $150M / 5,000 paths**. Run the baseline, then the two
main stress tests. Select **Public** to repeat the analysis for that institution.
Use **Compare the three representative dynamic portfolios** for side-by-side portfolio results.
All ten updated portfolios (five dynamic and five static) are available for individual analysis.

The sidebar **Appearance** setting lets you choose Light or Dark without changing the calculations or clearing results. The main **Overview** provides six risk and sustainability cards and four charts. Open **Review assumptions before running** to see the exact inputs. The baseline
is automatically included in every stress and what-if comparison. A run can take
several minutes; the progress indicator shows each case as it completes.

Results appear in **Overview**, **Payout risk measures**, **Portfolio charts**, **Stress impact**, and **Details & downloads**. Exports
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

## If you previously saw a missing-column error

The original `KeyError` in the Downside and liquidity table has been fixed in
v11. Upload the **whole project folder**, not only `app.py`, so
`scenario_analysis.py` and `dashboard_contract.py` match. Commit, reboot the
Streamlit app and click **Run analysis** again; previously cached results are
not compatible with the v11 display schema. See `INTERFACE_V11_RELEASE_NOTES.md`.
