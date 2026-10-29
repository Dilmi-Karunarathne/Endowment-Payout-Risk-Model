# Methodology and interpretation

## Anchor and scope

The anchor is the R2 Private/Base $101M–$250M cohort, paired with the interim R1 P4 Medium/Normal portfolio. R1 weights are not verified as private-institution-specific or finalized for the seven size cohorts. Bundled CSVs are retained from the supplied package; this update does not independently verify their underlying institutional sources. Source attribution refers to the R1/R2 supplied files, not newly acquired data.

Quarterly arithmetic portfolio returns feed an annual institutional cash-flow engine. The launch asks for asset-class analysis; the allocation-upload workflow supports this when complete asset-return histories are supplied. It does not fabricate final allocations or infer individual asset returns from aggregate P4 history.

## Annual timing and accounting

1. Apply compounded quarterly return to beginning endowment assets. Apply the same aggregate return to all three liquidity buckets; asset-specific bucket returns are not available in bundled data.
2. Add gifts and other changes, measured against beginning assets. Positive flows enter highly liquid assets and are assumed unrestricted and spendable. Negative other changes reduce holdings proportionately. Inputs producing negative pre-payout assets are rejected.
3. Compute planned spending from the trailing 1–3 valuation points or current beginning assets. The three-year baseline uses the two prior year-end values and current beginning value. Spending occurs at year end. Optional growth floor/cap applies to the previous planned payout, not the previous actual payment; the first payment is unconstrained.
4. Retain the reserve target (years of planned payout plus minimum cash reserve). Pay endowment-funded other cash obligations before the endowment distribution. No borrowing or external bailout is assumed. Other needs still apply when liquidity restrictions are disabled.
5. Use available liquid holdings; optionally access the moderate bucket and sell illiquid assets at the chosen discount. Required reserve, other obligations and payout determine sale demand. Moderately liquid access is at carrying value; haircut restricts access to highly liquid holdings without writing them off. Illiquid sale amount is gross carrying value, net cash equals gross times (1-discount), and loss equals gross times discount. Sale losses are deducted once.
6. Record unpaid other obligations and unfunded planned distributions separately. No debt balance is accumulated for missed payments; both are reported but not automatically carried to the following year.
7. Ending assets equal pre-payout assets minus actual payout, paid other needs, and forced-sale losses. Every path checks this identity. There are no unfunded distributions after depletion.
8. Deflate year-end assets and payments by the cumulative annual inflation index. Gifts, other changes and payouts are annual approximations; intra-year liquidity crises are outside this model.

When liquidity restrictions are off, every asset can fund payments at carrying value. This removes access limits but does not remove the asset-budget constraint.

## Persistent liquidity buckets and reserves

Initial weights form highly liquid (Very High/High), moderately liquid (Moderate) and illiquid (Low/Very Low) buckets. They persist between years; sales deplete the appropriate pool and proceeds enter liquid assets. Available moderate access is a user-defined fraction of current holdings. The reserve is a retained cash target, not an extra expense or a separate endowment. Subsequent gains and inflows replenish it; moderate transfers and permitted forced sales can also fill it. A deficit against that target is reported.

This is a capacity approximation. Applying the aggregate portfolio return to every bucket does not represent asset-level valuation, capital-call schedules, multi-year lockups, redemption gates, actual rebalancing trades or policy-specific cash yields. In allocation comparisons the return benchmark assumes quarterly fixed-weight rebalancing, while cash-flow capacity tracks cumulative sales; these are separate approximations rather than a full holdings engine. Final findings should acknowledge this limitation, especially for sustained liquidity stress.

## Return models

- **Single Normal:** independent quarterly Normal returns fitted to portfolio historical mean and sample standard deviation.
- **Two-component Normal mixture:** sklearn GaussianMixture, two components, full component variances, 20 initializations, fixed calibration seed. Lower mean is labelled adverse. Each quarter independently chooses a component. These are statistical components, not estimated regime transitions. Probability, mean and volatility overrides affect the adverse component only.
- **Historical block bootstrap:** samples contiguous blocks of portfolio returns and CPI observations with replacement. Finite history limits observed tail severity.
- **Regime bootstrap:** optional legacy alternative using the supplied economic transition matrix and conditional empirical samples. It is distinct from the mixture and from a copula.

Parametric draws at or below -100% are rejected and resampled. Thus extreme parameter settings imply truncated distributions. Normal-model inflation defaults to historical mean CPI YoY if no fixed rate is selected. Block bootstrap pairs quarterly returns with matching CPI. Regime sampling conditions on state but does not estimate a joint continuous return/inflation distribution.

All generators receive the same optional quarterly transformation: sample mean + volatility multiplier × (draw − sample mean) + annual mean shift / 4. The shift is an arithmetic quarterly scenario adjustment, not a targeted annual compounded return. Invalid transformed returns are rejected with an error, not silently clipped.

The three-way method comparison fixes inflation (chosen rate or historical mean) and clears initial economic stress overrides. Other assumptions and user mixture overrides are retained. Equal seeds improve reproducibility but do not guarantee identical random-number consumption across methods. The comparison isolates model specification, not an optimized investment strategy.

## Risk definitions and denominators

| Measure | Definition |
|---|---|
| Annual return-coverage shortfall frequency | Fraction of simulated years with investment gain below planned payout. Gifts and asset sales can fund payments despite this event. |
| Coverage depth ($M) | max(planned payout − investment gain, 0), averaged over coverage events. Includes negative investment gains; it can exceed planned payout. |
| Relative coverage depth | Coverage depth / planned payout, averaged over events. May exceed 100%. |
| Annual funding shortfall frequency | Fraction of simulated years with actual payout below planned payout. |
| Probability of any funding shortfall | Fraction of paths with one or more funding shortfall years across the selected horizon. |
| Conditional funding depth | (planned − actual) / planned averaged over funding shortfall events, not all years. |
| Longest shortfall spell | Longest consecutive annual shortfall run on each path. Coverage and funding spells are separate. App reports their path medians; path CSV retains individual values. |
| Real corpus erosion | Real year-end corpus below selected fraction of initial real endowment. App reports probability of any breach, median years below and median longest spell. |
| Recovery time | First threshold breach to first subsequent annual recovery. Unrecovered paths are right censored, not assigned zero. Median completed recovery time excludes censored paths and must be read beside the conditional non-recovery probability. Later breaches are not included in first-event recovery. |
| Terminal real-corpus loss | max(1 − terminal real assets / initial assets, 0); gains produce zero loss. |
| VaR / ES | Empirical loss quantile / mean of worst ceil((1-alpha)×N) losses. ES may be unstable when the number of tail paths is small. |
| Real corpus drawdown | Annual year-end decline from running real peak including initial corpus; includes distributions and cash-flow effects. |
| Investment drawdown | Quarterly return-only wealth decline from running peak, excluding all gifts/payouts/other flows. |
| Cumulative real payout | Sum of annual actual distributions deflated to initial purchasing power. |
| Support gap | max(required support − actual payout, 0), with required support = expenses × support ratio. This is not a complete operating deficit. |

## Strategy and stress interpretation

The policy comparison changes one policy at a time: current-assets spending, alternative rate, or reserve requirement. These are explicit scenarios, not claimed final R2 policies. The reliability-growth scatter should be interpreted alongside cumulative real payouts, coverage shortfalls and corpus erosion. Lower spending is not necessarily a superior policy merely because terminal corpus is higher.

Allocation comparisons require asset returns for both the anchor and alternative on common consecutive quarters. Both aggregate return histories and both liquidity shares are rebuilt from the uploaded data. Missing asset returns are rejected rather than imputed. Dependence is preserved in historical aggregation; alternative portfolio-level distributions are recalibrated to the resulting series. No copula is implemented.

Stress scenarios apply lower mean returns, higher inflation, increased spending, reduced accessible liquidity, forced-sale discounts and a combined case. Mixture sensitivities vary adverse probability and quarterly adverse mean one factor at a time, with fixed inflation. None of these settings is an estimated forecast.

## Validation and limits

- Unit/integration checks verify depletion, obligations, reserve priorities, roll-forward, bucket depletion, timing, duration and model connections.
- Historical reconstruction uses bundled 2013–2022 P4 history and selected institutional assumptions; it is not an independent institution-level backtest. Uploaded histories are not substituted for this explicitly labelled bundled historical exercise.
- Full-sample AIC/BIC evaluate calibration fit, not predictive success. Likelihood diagnostics ignore negligible truncation effects at ordinary parameters.
- Chronological holdout fits Normal/mixture only on the first 70% of observations, scores the remaining quarters, and reports dates/counts. No claim of holdout validation is made for bootstrap or the full institutional model. The endowment simulation itself still uses the full selected calibration.
- Stability checks vary seed and path count; report conditional interpretation of the selected inputs. Binomial standard errors apply to path-event probability, not correlated annual observations or ES. Zero observed events are not proof of zero true risk.
- Current history has only 66 quarters. Statistical parameter uncertainty, forward return changes, illiquid valuation smoothing and regime calibration uncertainty remain material.
- Clean operating revenue is still unavailable. This is an endowment payout model with an expense-support indicator, not a complete university budget/treasury forecast.

## Dashboard presentation

Overview charts show pointwise 10th–90th percentile ranges across simulation paths. The shaded bands are not 80% simultaneous confidence bands for an entire trajectory. Year zero anchors are the starting endowment and the initial planned payout; the payout anchor is a reference amount, not an observed historical payment. All displayed payout and corpus paths are inflation adjusted. Headline principal erosion means a breach in any projected year, not just at the terminal date. The detailed assumptions and pending-data status remain in the documentation even though the main dashboard omits research-status banners.


## Final-model scenario stress update

The uploaded main_v5 engine is the base. Quarterly-path transforms and annual institutional overrides were added; neutral/no-stress runs preserve the uploaded baseline. The reference main_v3 stress definitions are adapted through scenario_stress.py; its older accounting engine and verbose UI are not substituted for this model.

**Inflation and rates.** The first four quarters replay supplied 2022 P4 returns and CPI. The elevated-inflation window includes those quarters, defaults to 16 quarters, and can be adjusted quarter by quarter. During the forced window the selected generator draws conditional historical returns and CPI from the elevated-inflation state. Fixed future CPI does not overwrite the forced window; it resumes afterward when enabled. The post-replay inflation addition defaults to 1.4 percentage points and ends exactly at the chosen regime-window boundary. Expense growth is set to 4.6% for the first two year-to-year transitions by default. Optional multiplicative return drag starts after the replay. Expense growth changes subsequent years; a two-year growth window affects the year-2 and year-3 expense levels. After stress ends, expense levels retain prior accumulated changes.

**Downturn and liquidity.** The first six quarters replay supplied 2008Q1–2009Q2 P4 returns and CPI. A -3% multiplicative annual recovery drag then applies for two years. Defaults are gifts at 88% of normal for two years, capital calls at 2% of beginning assets for three years, and a 50-point added liquid-access restriction for two years. The one-year payout reserve, 30% forced-sale discount and permission to sell illiquid assets apply throughout the horizon. Every parameter has an explicit control. These values reproduce the reference setup as editable assumptions; they are not newly calibrated estimates.

**Timing and interpretation.** Replays override future fixed CPI and sampled returns only for their quarters, including under Normal or mixture generators. Historical P4 is a benchmark series, not an institution's observed experience. Post-replay drag multiplies each quarterly wealth factor by (1+annual_drag)^(1/4). Inflation additions apply to annualized CPI observations. Regime-switching returns resume the transition matrix after a forced regime; other generators resume their selected sampling method. Shared seeds support reproducibility but forcing a regime may consume different random draws, so identical seeds do not eliminate all paired sampling differences. No scenario probability is estimated.

**Capital calls and payouts.** Existing other cash obligations receive priority, then capital calls, then planned payouts; reserves are protected. Paid capital calls transfer accessible assets to the illiquid bucket at par and do not themselves reduce total NAV. Any funding shortage is reported as unpaid_capital_call. All holdings receive the same aggregate portfolio return. Forced-sale discounts reduce NAV and are recorded separately. Emergency appropriations are included in planned/actual payout after regular spending collars, so they enter payout metrics. The identity remains ending_assets=pre_payout_assets-actual_payout-other_cash_paid-forced_sale_loss. No unfunded calls are deducted from NAV, and distributions cannot exceed capacity.

**Reported results.** Payout shortfall is actual versus planned payout. University funding-gap risk is the chance of any positive required-support minus actual-payout gap. Higher expense growth changes this support target; it does not automatically authorize larger payouts. Real payout and real endowment charts show annual medians across simulations; forced-sale losses are mean cumulative nominal losses. Annual detail tables show columnwise medians, which need not add across paths. CSV downloads retain full path detail.

**Additional tools.** Scenario-library shocks are illustrative weighted asset exposures or historical replays. Reverse stress uses a deterministic path based on selected-history mean quarterly returns and current return/CPI settings. It scans extra initial losses from 0% to 95%, brackets the first observed terminal-target breach, and refines it. Non-monotone scans are flagged; narrow between-grid breaches may be missed. The spending grid is deterministic ending real assets divided by initial assets. Neither tool estimates probability. The separate deterministic comparison and duplicate mixture-sensitivity UI are omitted for clarity, while existing engine APIs remain usable.

**Limits.** Private-distribution delays are represented through capital-call/access pressure, not explicit private-fund cash-flow schedules. Rate effects use the 2022 replay and optional return drag, not a borrowing-cost or duration engine. Empirical calibration and institution-specific restrictions remain to be supplied. This stress-only revision does not add unrelated features absent from the uploaded final ZIP.
