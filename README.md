# Endowment Payout Risk Lab

Run with Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

For Streamlit Community Cloud, upload the extracted project contents including
`data/`, and use `app.py` as the entry point. No workbook import is required.
The card dashboard, expanded details, back navigation and active-theme graph
styling are retained. No theme is forced.

## Portfolio selection

Choose Institution (Private/Public), then Portfolio allocation (Normal/Elevated
Inflation/Recession). All six supplied portfolios are connected to simulations.
Private / Normal is the default. The institution selection also sets the R2
median institutional assumptions. P25/P75 inputs are retained only for one-input
sensitivity analysis under Strategies; they are not institution cohorts.

An allocation label describes the candidate investment policy, not the future
market scenario. A Recession allocation can be tested under baseline or stress.
Weights stay fixed during each run. This does not implement R1's monthly
signal-driven switching, dated monthly targets, or a holdings/trading engine.
The regime-switching bootstrap changes the simulated economic state and return
sampling; it does not change portfolio weights.

### Return construction and sources

- `data/asset_monthly_returns.csv`: supplied Asset_Data.csv, unchanged; includes
  18 assets, of which exactly 13 IDs are selected to match the portfolio file.
- `data/six_portfolio_weights.csv`: supplied six_portfolio_weights(1).csv,
  unchanged. All weight vectors are checked for nonnegative finite weights
  summing to one. Missing required assets cause an error, not substitution.
- Monthly calibration starts January 2007, consistent with the common sample
  described in R1's methodology. It uses the supplied file; its equivalence to
  R1's final native-data input is not independently verified. The source has
  backfilled observations, and source dates alone cannot identify every proxy.
- Monthly portfolio return = sum(weight * asset return). This is a cost-free,
  fixed-weight monthly-rebalanced return benchmark, including private sleeves;
  it does not claim actual monthly tradability of private assets.
- Quarterly return = product(1 + monthly portfolio return) - 1, using exactly
  three consecutive months. Calibration is 78 quarters, 2007Q1–2026Q2.
  July–August 2026 is excluded because 2026Q3 is incomplete. Pre-2007 data is
  retained in the supplied source but excluded from all calibration.
- Current weights applied to past returns are retrospective candidate
  benchmarks with look-ahead limitations, not independent historical strategy
  validation or observed university performance.
- The existing quarterly condition history, CPI observations and transition
  matrix are retained. They are not replaced by R1's monthly actionable signal
  timeline. Conditional return sampling uses the newly constructed series.
- Legacy P4 weights, return history and unused P4 validation CSV are removed.
  Selected portfolio history drives baseline, return-method comparison,
  policy comparison, stress replay, historical reconstruction and diagnostics.

## Liquidity and asset shocks

Liquidity constraints apply to every run, including baseline, historical checks,
comparisons and stress tests. There is no enable/disable checkbox. Liquidity
parameters and forced-sale permission remain adjustable under Advanced options.

Selected portfolio weights also determine liquidity shares and weighted market
shocks. Liquidity classes are provisional: Cash is Very High; PE and VC are
Very Low; Hedge Funds are Low; other selected public sleeves are High. These
are simplifying modeling assumptions, not confirmed redemption terms, gates or
notice periods. User overrides remain available. The persistent bucket engine
applies one aggregate portfolio return to all liquidity buckets, so it does not
track individual asset holdings, differential bucket returns or actual trades.

Additional scenario-library asset shocks are hypothetical and now cover all 13
canonical asset IDs. New sleeve assumptions for the equity crash are Small Cap
-40%, Treasuries +5%, TIPS +2%, Commodities -20%; for the rate shock they are
-25%, -15%, -10%, +10%, respectively. These are illustrative assumptions, not
R1 estimates. The main downturn/inflation scenarios replay the selected
portfolio's 2008Q1–2009Q2 / 2022 returns, with existing CPI observations and
editable institutional/liquidity overlays. No scenario occurrence probability
is estimated.

## Simulation and payout conventions

Quarterly block bootstrap, two-component Normal mixture, regime-switching
bootstrap and a Single Normal benchmark remain available. Distribution models
fit the selected aggregate quarterly history, not 13 separate distributions.
The comparison runs three main methods with common portfolio, horizon,
institutional inputs and fixed inflation. Common seeds support reproducibility
but do not guarantee the same random-number consumption between methods.

Quarterly returns are geometrically compounded to annual returns. The annual
engine applies gains, gifts and other changes, then year-end distributions.
Three-year smoothing uses beginning valuation points; optional prior balances
initialize them. Spending collars, reserve settings and liquidity overrides
are unchanged. Payouts respect asset capacity. Other cash needs precede capital
calls, then planned distributions; funded capital calls move assets to the
illiquid bucket rather than subtracting total NAV. Forced-sale losses reduce
NAV. Ending assets equal pre-payout assets less payouts, paid other obligations
and liquidation losses.

## Risk definitions

| Measure | Interpretation |
|---|---|
| Return coverage | Investment gains below planned payout; gifts/sales may still fund it |
| Payout funding shortfall | Actual payout below planned payout |
| Conditional funding depth | Unpaid share averaged over funding-shortfall events |
| Support gap | Required support (expenses × support ratio) less actual payout, floored at zero |
| Shortfall duration | Consecutive annual events; coverage and funding are separate |
| Real principal erosion | Real year-end assets below the chosen fraction of initial assets |
| Terminal real loss | max(1 − terminal real assets / initial assets, 0) |
| Expected Shortfall | Mean of the worst ceil((1-alpha) × simulations) terminal losses |
| Cumulative real payout | Sum of annual payouts in initial purchasing-power dollars |

Annual frequencies use simulated years; any-event probabilities use paths.
Coverage depth can exceed planned payout when investment gains are negative.
Pointwise 10th–90th percentile chart bands are not simultaneous confidence bands.
Recovery times exclude right-censored unrecovered paths; read alongside the
non-recovery probability. Lower spending is not automatically a better policy:
assess payouts and principal together.

## Checks and limitations

Historical reconstruction uses the selected fixed allocation over 2013–2022
and current institutional assumptions; it is an accounting/mechanics check.
Chronological holdout scores Normal/mixture densities using the first 70% for
training; it does not validate a whole institution model or bootstrap strategy.
Full-sample AIC/BIC are calibration diagnostics. Stability checks vary seed and
path count; zero observed shortfalls do not prove zero underlying probability.

R1 signal-driven allocation switching, transaction costs, fund-specific private
cash flows, gates, inflation/return dependence, policy parameter uncertainty and
independent forward validation remain outside this integration. R2 revenue data
and actual institutional restrictions still require confirmation. This is an
endowment payout model with an expense-support indicator, not a full university
budget forecast.
