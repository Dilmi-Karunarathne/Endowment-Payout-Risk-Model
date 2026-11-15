# Updated portfolio handoff + accessible payout risk measures — Version 10

This release integrates **R3HandoffPackage.zip**, provided by Research Team 1 on **15 November 2026**. It updates the portfolio universe from the earlier nine research strategies to **five final strategies × dynamic/static = 10**, retaining the same R3 cash-first endowment distribution and segregated-gifts framework. No numbers from the older validation outputs are reused as results of the new portfolios.

## What was reviewed and integrated

- **10 portfolios**: Peer-Tail-Risk Mean-CVaR, Peer-Risk Maximum Return, Mean-CVaR, Equal-Weight (1/N), and Hierarchical Risk Parity; every strategy has a Dynamic and Static variant.
- **13 approved asset classes**. The November handoff's asset returns, quarterly historical portfolio reference returns, August 2026 forward target weights, and monthly economic/market regimes are now inputs to the simulation.
- **Historical horizon**: quarterly reference histories have 102 complete quarters from 2001Q1–2026Q2, from the handoff's 308 monthly returns through 2026-08. The last two available months initialize August-2026 forward allocations but are not treated as a complete quarter.
- **Regime signals**: the economic condition (Normal/Recession/High Inflation) controls economic stress sampling and reporting; a *separate lagged* market regime (Calm/Turbulent) controls Dynamic portfolio weights. Static portfolios have the same target in both regimes.
- **Portfolio-specific base capital-call proxies**: taken from the Research Team 1 `Liquidity_Profile_by_Portfolio` file (1.75%–7.81% of beginning total assets, depending on private exposure) for three years. A severe 1.5× overlay acts on the applicable portfolio-specific call rate over four years, under the existing scenario scheme. These rates are **not verified actual cash commitments**.
- **Portfolio-specific protected payout reserves**: 1.0× planned annual payout for eight portfolios; 0.25× for the two Static CVaR versions, per Research Team 1's stress-test guidance. This remains an illustrative R3 funding policy, not an independently documented rule at a specific university.
- **Liquidity and execution**: asset-specific time-to-cash and normal/stressed selling costs from Research Team 1's supplied Data Team matrix. Rebalancing remains limited by private-asset lockups, five-percentage-point quarterly pacing, and actual available cash; infeasible target trades are reduced or deferred.
- **Stress sources**: new recommended asset-class crash-shock magnitudes, 2022 replay + inflation/return drags, 2008–09 downturn + calls/restrictions, all using the new asset universe and data. Five-year projection truncates any six-year recommended severe inflation shock; this limitation must be disclosed.

## Read the dashboard payout risk measures

Select **Baseline & strategies** or a **Stress testing** / **What-if scenarios** analysis → click **Run analysis** → open the **Payout risk measures** tab (second tab). Choose a portfolio and scenario. The tab displays:

1. **Any unpaid scheduled payout (%)**: chance an actual paid distribution is below planned spending in at least one of five projected years.
2. **Real payout-eligible principal erosion risk (%)**: chance the inflation-adjusted asset pool eligible to support payouts falls below the initial endowment at least once. The total-endowment erosion percentage is also displayed separately.
3. **Institutional support-gap probability (%)**: chance the annual actual payout is smaller than the separate required operating-support target in at least one year. This does **not** prove an unpaid scheduled distribution.
4. **Purchasing-power Expected Shortfall (95%)**: mean nonnegative loss in terminal inflation-adjusted **total** endowment value in the worst 5% of simulated paths, expressed as a percent of the initial fund. It is **not** an annual payout shortfall.

Also displayed: a planned-versus-actual **shortfall deviation chart** (negative = unpaid), a year-by-year funding and earnings-coverage gap table, average unpaid payout when an event occurs ($M), and average institutional support gap when positive ($M). The app still exports all path-year calculations.

### Three different liquidity definitions (do not conflate)

| Output | Numerator | Denominator | Interpretation |
|---|---|---|---|
| Portfolio crisis-value 20% test | Payout-eligible asset values × Research 1's **crisis-sale-value factor `g`**, which reflects a historical worst fall and stressed selling cost | Total endowment market value | Research 1 optimizer targets >=20% at its allocation decisions (4 × 5% annual payouts). Future simulated holdings may breach this constraint. |
| 40% and 20% liquid-share monitoring | Payout-eligible assets × Data Team's **stressed one-month accessibility weight `h`** | Total endowment market value | Comparable thresholds for Professor Joe's requested reference analysis; checks include quarterly and post-distribution observations. The 40% threshold is a monitoring comparator, not the Research 1 optimization rule. |
| Annual payout liquidity buffer (×) | Payout-eligible assets × `h` | Annual planned payout | Number of planned annual payouts covered by stressed one-month liquidation weights. Different from three-month actual payout-funding capacity. |

The **20% crisis-value (`g`)** breach probability is not required to be less than the **40% access-weight (`h`)** breach probability, because they use different numerators. However, within the comparable `h` definition, breaches below 20% must never be more frequent than those below 40%.

## Return conventions and research limitations

1. The handoff's **Net_Return** already contains its historical rebalancing costs. The forward R3 Monte Carlo engine instead samples the **asset-level gross returns** and calculates its **own constrained asset trades and transaction costs**. It uses R1's historical Net_Return only to check reference performance. **Do not deduct historical Net_Return trading costs a second time.**
2. Research 1's portfolio backtests and optimized weights should not be presented as the realized outcome of the simulation. R3's forward path-specific trading and restricted gift/funding rules can produce different distributions.
3. Private-market indices can be backfilled or use listed-security replicators. These are imperfect liquidity and return proxies. Management/administrative fees remain incompletely modeled.
4. Research 1 explicitly did not provide normal private-asset distribution rates, fund-level unfunded commitments, or observed university donor restrictions. The current model still uses the prior conservative restriction on all new gifts and their subsequent returns, and no explicit private distribution inflows. These are **limitations, not evidence that all real gifts are restricted**.
5. The passive 70/30 benchmark is still not present in the handoff; it is not synthesized or invented.
6. The R1 handoff declares its material **internal research use only**, including peer risk constraints derived from a confidential survey. Do not publish the complete research source, derived weights or scenario results in a public repository without permission; use a private GitHub repository and review app access before public deployment.

## What requires a further decision before final submission

- Does the team want all ten strategies in a single comparison? They are individually selectable. The default three representative **Dynamic** strategies are HRP, Mean-CVaR and Equal-Weight; this prevents unintentionally running 10 × 5,000 simulations on a hosted free service.
- Should R3's gift restriction remain for both Private and Public cases? This is unchanged but policy-dependent.
- Should payouts for the static CVaR portfolios be tested under a one-year reserve too, in addition to the R1-proposed 0.25-year baseline?
- New source results should be rerun at 5,000+ paths; the **old** scenario comparison CSV files in the previous package are NOT valid results for the new 10 portfolios.

## Deployment

Install dependencies from `requirements.txt`, run `streamlit run app.py`. Replace the entire old repository directory with this model's files and data before rebooting the app. Do **not** mix previous 9-strategy inputs with this updated version. The dashboard schema key has been changed to invalidate cached earlier model results.
