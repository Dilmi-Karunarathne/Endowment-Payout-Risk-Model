# R1 handoff update

Source: Research Team 1 handoff dated November 9, 2026. The application uses the revised forward targets, asset returns, macro history and asset shocks. The historical strategy return diagnostics compound the supplied monthly Net_Return. The bundled static-policy series and liquidity profiles are reference data.

## Liquidity and payout

- R1 test: sum each holding times its supplied stressed one-month liquidity factor and divide by total endowment assets. The factors incorporate sale eligibility and the upper stressed liquidation cost. The reference threshold is 40%.
- R2 warning: public equities, bonds and cash divided by planned annual payout. A value below 3× is a warning. Commodities, PE, VC and hedge funds are excluded from this numerator.
- Both measures are checked during quarterly investment steps and after annual cash flows. Severe downturn scenarios exclude emerging-market equity and high yield during the specified restriction window. Standard scenarios add no market restriction by default. The optional extra percentage restriction is an additional sensitivity.
- The spending policy uses the existing three-year moving average and 3%–5% collar. The app tracks both indicators separately from the modeled payout. The existing proportional withdrawal convention and total-wealth cap apply. Monitoring does not simulate fund redemptions, execution of payout-related sales or borrowing.
- R1/R3 net capital-call stress uses 2% of beginning assets per 12.8% starting PE+VC exposure for three years in Standard, or 3% per 12.8% for four years in Severe. R2 supplies no benchmark for calls. The data also lack a normal private-distribution schedule, so the model uses net calls as a proxy.
- Sale times and cost estimates are conditional on the position sizes in the supplied Data Team table. The model applies the supplied factors to each position as a monitoring approximation and does not estimate size-dependent execution.

## Returns and inflation

- Dynamic simulations draw gross asset returns and charge the R1 midpoint rebalancing rates on absolute changes in position values. Recession, Overlap and the annual downturn stress windows use stressed rates. PE and VC changes are exempt, as in the R1 methodology.
- Rebalancing costs are deducted once. The 40% liquidity test estimates sale proceeds for monitoring and does not deduct its assumed sale costs from endowment wealth. Historical strategy diagnostics use the supplied net-of-rebalancing-cost returns.
- Returns remain gross of management fees. The R1 historical net series deducts rebalancing costs only.
- The inflation stress starts with the four-quarter 2022 replay, then uses the R1 2.5% reference plus 1.6 or 2.4 percentage points over the remaining Standard or Severe window. The common Severe return drag of −4 percentage points is the R1 single-value option.
- Both institutional profiles use the shared R1 strategies, including the selected MeanCVaR@Private targets for both profiles. R2-specific spending, gifts, expenses and revenues remain tied to the selected institution.

Run the app with `python -m streamlit run app.py`. Run tests with `python -m pip install -r requirements-dev.txt` and `python -m pytest -q` after installing the application requirements.
