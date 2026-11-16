# Version 11 — Dashboard interface + missing risk-column fix

## What caused the Streamlit Cloud exception?

The dashboard was selecting a comparison column named
`Portfolio crisis-value 20% breach probability (%)`, while the previous
`scenario_analysis.comparison_row()` produced
`R1 crisis-value 20% breach probability (%)`.

The resulting `KeyError` stopped the page when the user reached the comparison's
**Downside and liquidity** section. The Pandas traceback began on `app.py` line
312 because the entire table selection is one expression; the failing field was
a label mismatch, not a numerical or Monte Carlo error.

**Fix:** Align the displayed name and generated column. Add
`dashboard_contract.validate_comparison_schema` before caching or rendering
results. If the GitHub deployment contains mixed versions, the app now gives an
actionable schema warning instead of a raw DataFrame error. Bump the results
schema version to force recalculation after deployment.

## Redesigned interface

- Modern, softer **light** palette (white cards, mist-gray background, soft
  navy accents), and **dark** palette (slate/navy cards, blue/teal accents).
- **Color theme** control in the sidebar. Toggling colors does not change
  endowment assumptions, invalidate saved model results or sample new paths.
- Compact sidebar for navigation, institution, benchmark profile, strategy,
  initial endowment and simulation counts.
- Clear dashboard title and plain-language subtitle.
- **At a glance:** six live, calculation-backed KPI cards: unpaid payout risk,
  payout-eligible real erosion, minimum liquidity buffer, median final real
  endowment, institutional support-gap risk and purchasing-power ES95.
- **What this run tells us:** automatic explanatory takeaways derived from the
  active simulation (not manually typed results from a prototype).
- **Overview:** four two-column charts. The real-wealth chart includes the
  genuine 10th–90th percentile band from the model's sampled paths.
- **Payout risk measures:** retained all four core measures, detailed annual
  funding-gap chart and separate 40%, 20%, crisis-sale liquidity definitions.
- **Portfolio charts / Stress impact / Details & downloads:** organized into
  self-explanatory tabs with consistent labels and chart styling.
- Detailed downside/duration tables are in expanders rather than dominating
  the primary overview.

## Calculations and sources

**Unchanged:** v10 November 2026 Research 1 investment data (10 Dynamic/Static
portfolios), Private/Public institutional profiles, historical bootstrap,
spending rule, gifts, restrictions, capital calls, payout funding, updated
quarterly rebalancing, scenario overlay calculations and risk measures.

No numbers or risk formulas were copied from the professor's separate
reference prototype. All dashboard figures are computed by this application's
existing model. No extra benchmark series or management fees are invented.

## Reproduce tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q test_dashboard_v11_regression.py test_updated_handoff.py \
    test_dashboard_contract.py test_rebalancing_cash_constraints.py \
    test_stress_policy_improvements.py
# With Streamlit installed, also run:
python -m pytest -q test_app.py
```

Validation in this local workspace:
- 35 backend/schema/accounting/scenario tests passed.
- Additional baseline comparisons checked Private/Public and three Dynamic
  strategies.
- Offline *headless* dashboard-code checks executed all five navigation views
  in both appearance modes with shortened developer-only simulations. This
  exercises Python rendering paths and Plotly configuration, not browser CSS.
- The actual Streamlit browser could **not** be tested in this environment,
  because `streamlit` is not installed and the package server was unreachable.
  Run the included Streamlit AppTest in GitHub/Streamlit Cloud or locally, and
  visually inspect both themes after deployment.

## Deploying

Replace **all** files inside the existing GitHub repository with the contents
of this `Endowment_Final_Model` folder, retaining the data subdirectories.
Do not upload the outer ZIP as a single repository file. Commit, reboot the
Streamlit Cloud app, then click **Run analysis** to produce a new v11 result.
Switch between Light and Dark via the sidebar **Appearance** setting.

The final endowment analysis remains a five-year research simulation. Results
are not policy recommendations or historical forecasts for any named university.
