# v12 — Executive dashboard redesign (light + dark)

Updated 15 November 2026 from the user's uploaded `Endowment_Planning_Risk_v11_Improved_UI_Light_Dark_Bugfix(1).zip`.

## Purpose

Redesign the **Streamlit interface** to resemble the user-supplied light and dark executive-dashboard reference images while **retaining the actual November 2026 Research 1 investment handoff and every model calculation**. The reference screenshots contain illustrative portfolio selections and outcomes: **no illustrated performance numbers were copied into the application**.

## Updated layout

- Left sidebar: product branding, clear navigation, Light/Dark selector, and an accessible model description. Separate pages: **Overview**, **Portfolio analysis**, **Payout risk measures**, **Stress testing**, **Policy responses under stress**, **Scenario comparison**, **Model guide**.
- Main content: clear page title and subtitle, then a compact horizontal **simulation settings** panel with **institution type, institutional profile, investment strategy, starting endowment, simulation count, and Run analysis**. Comparison checkbox and fixed-horizon details appear below the controls.
- **Spending policy is displayed read-only**, because the underlying v11 engine implements a fixed three-year average and the base institutional spending rate comes from the benchmark profile. The horizon is fixed at five years. A screenshot-only dropdown or an unimplemented Yale/Stanford hybrid would mislead viewers and was not added.
- **Four top headline metric cards**: median terminal real total endowment, probability of any unpaid planned distribution, median of each path's minimum one-month liquidity buffer, and purchasing-power Expected Shortfall (95%). Values come directly from `suite` and `annual_detail`.
- Main **real-endowment chart** with median of each selected portfolio. When comparing portfolios, the chart draws three matching baseline strategy summaries. When running just one portfolio, it displays the median and the 10th–90th percentile range. All charts are built from actual simulations; the initial endowment is the common Year 0 point.
- Next to the chart, the **How to read these results** panel explains each financial metric precisely.
- Additional payout, liquidity, operating support and downside charts are behind a disclosure in Overview; detailed risk, stress and scenario views remain easy to navigate.
- Light palette: soft near-white, navy text, muted blue and teal. Dark palette: deep navy, slate cards, blue, teal, amber and purple accents. Switching theme **does not rerun the model or invalidate saved results**.
- Before the first run, prominent headline cards show `—` with a **Run analysis to calculate** explanation instead of invented demonstration values.

## Essential model definitions retained

- Liquidity buffer = **stressed one-month accessible payout-eligible liquid assets / planned annual payout**. It is **not** divided by payout + capital calls + cash needs, as some images suggested.
- The probability of an unpaid annual payout is different from a portfolio return below spending, a 20%/40% one-month liquidity-share warning, and a required institutional support gap.
- Purchasing-power Expected Shortfall (95%) is a **terminal real endowment** downside measure, *not* a dollar amount of unpaid payouts.
- Main dashboard compares the updated Research 1 handoff's **HRP Dynamic, Mean-CVaR Dynamic, and Equal-Weight Dynamic** by default *when comparison is checked*. An older screenshot showed Minimum Variance, which is not one of the current ten investment methods. The underlying `STRATEGIES` list remains unchanged.
- The input portfolio data, stochastic bootstrap, restricted-gift accounting, quarterly trading constraints, cash-first payout methodology, liquidity policy and stress scenarios are **unchanged**.

## Deployment

1. Unzip `Endowment_Planning_Risk_v12_Executive_Dashboard.zip`.
2. Open the **`Endowment_Final_Model`** folder. Upload **all files and subfolders inside it** to the root of the existing GitHub project. Do not upload the enclosing folder as an extra directory unless your Streamlit main file path is also updated. Overwrite `app.py`, `dashboard_contract.py`, all code modules and `.streamlit/config.toml` together. Preserve `data/investment/`.
3. Commit the files and reboot the Streamlit Cloud app. Streamlit's main file must still be `app.py`.
4. Open **Overview**, select institution and portfolio, optionally tick **Compare three representative dynamic portfolios**, and click **Run analysis**.
5. Switch Light/Dark in the sidebar; visit Portfolio analysis, Payout risk measures, Stress testing, Policy responses, and Scenario comparison. Note that changing the underlying model controls requires selecting Run analysis again.

## Validation performed

- Python compilation succeeds for all application modules.
- **35 automated tests passed** covering the output schema, new investment-handoff loading, stress/policy calculations, and rebalancing cash constraints.
- The native interface branches were exercised without Streamlit with **real short developer-only simulations** using `python tools/check_interface_without_streamlit.py`: Overview, Portfolio, Payout Risk, Stress, Policy, Scenario and Guide; Light and Dark, three-portfolio chart, and the no-results first-visit view all passed.

**Not claimed:** Pixel-perfect screenshot matching or live browser verification. Streamlit 1.67.0 could not be installed in this container because outbound package installation is blocked by DNS. Users should visually inspect the live deployment and verify the controls on their screen sizes. No fresh full-resolution Monte Carlo results were generated for this interface-only release.

## Open limitations

Full investment-management fees and the approved 70/30 passive benchmark are still incomplete in the underlying research model. Some expensive portfolio comparisons may take several minutes at 5,000 or 10,000 paths. This visual update does not address those research extensions.
