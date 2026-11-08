# R1 integration — 8 November 2026

This update supersedes earlier static six-portfolio and liquidation-matrix descriptions.

## Included
- Nine R1 strategies and 13 native asset classes; frozen 31 August 2026 targets for Normal, Recession, High Inflation and Overlap.
- Public MeanCVaR uses the Private MeanCVaR targets provisionally, as authorized by Dilmi. Public R2 spending, gifts, revenue and expenses remain Public-specific. The other eight strategies are shared investment candidates, not claimed to be separately optimized for each cohort.
- Starting regime is selectable. High Inflation is the handoff's last observed regime, not a 2027 forecast.
- Joint asset-return/inflation circular bootstrap, four-quarter blocks by default, seed 42. Complete quarters 2001Q1–2026Q2 only; the incomplete 2026Q3 is excluded. All strategies use the same sampled indices. R1's historical strategy returns remain diagnostic reference data; they are NOT added to dynamic asset returns.
- Asset returns compound monthly observations into quarterly buy-and-hold returns. Inflation compounds monthly CPI index changes, then quarterly changes into annual inflation; deflation occurs once.
- Forward quarterly allocation decisions use R1 frozen targets. Public sleeves move to proportional residual targets; PE, VC and hedge funds each move at most five percentage points per quarter. Holdings drift between quarterly decisions. Year-end gifts, withdrawals and calls change holdings carried into the next year. This is a quarterly forward implementation, not a reproduction of the historical monthly event-driven optimizer.
- Resampled quarter-start regime labels come from the previous month-end signal. Future labels are resampled with the asset/CPI blocks, not recomputed from a synthetic unemployment process. Block joins can change regimes abruptly. No reoptimization or newly estimated regime transition matrix drives the main simulation.
- Historical stress replays use the selected starting weights with buy-and-hold drift throughout the replay; target rebalancing resumes afterward. This differs deliberately from R1's historical dynamic strategy replay shown for reference.
- R1 Standard inflation stress: 2022 replay, 16-quarter total window, +1.6 percentage points inflation, −2 percentage points annual return drag for three years after replay. Severe: 24 quarters, +2.4pp, −4pp for five years (R1's permitted common severe value).
- Downturn: 2008Q1–2009Q2 asset replay; −3pp annual drag for two years, or −4pp for three years severe. Drags are additive annual/4 overlays, not multiplicative percentage reductions. They apply after replay. Historical replay is not stacked with an instantaneous shock.
- R2 cohort-specific expense and gift stress values are retained. Additional scenario library equity shocks now use R1's supplied Base/Severe asset-shock columns. Other custom/rate/stagflation scenarios remain exploratory assumptions, not newly calibrated R1 findings.

## Liquidity monitoring
The main app uses the professor's monitoring approach. The old liquidation engine remains only for backwards-compatible tests; its cost matrix and reserve controls are removed from the main interface.

Measure liquid assets (everything outside PE, VC and hedge funds) against both:
1. 40% of total endowment (R1 constraint).
2. Three years of the current planned annual payout (R2 benchmark).

Check at quarter starts/ends and after annual flows. Report any-path breach probability, near-breach probability, minimum coverage, minimum liquid share and years containing breaches. Near breach means below 110% of either limit, including actual breaches; that 10% warning margin is provisional. The displayed dollar deficit is the end-of-year shortfall against the larger requirement.

A breach is NOT automatically a missed payout. Payouts are capped by total available endowment wealth, not by assumed liquidation access. Annual payouts and other cash needs are deducted proportionally from holdings as a wealth-accounting convention; this does not assert illiquid assets can be sold. Therefore funded payout results are conditional on funding availability and are NOT a forecast of operational payout execution. No borrowing, trading costs, forced sales or liquidation losses are modeled in this main mode.

Calls use R1's private-exposure scaling in the app: 2% × (initial PE+VC share / 12.8%), severe 3% × that ratio; three/four years. They are a net-call liquidity-pressure proxy because no separate private-distribution baseline is supplied. Funded calls transfer liquid assets to PE/VC without reducing total NAV. Funding is limited to remaining liquid resources after the modeled annual payout/other needs. Unfunded calls are reported. No commitment schedule or defaults are modeled.

Standard additional restrictions are zero. Severe restriction defaults equal the starting EM+IG+HY share divided by starting liquid share, based on R1's moderate-liquidity freeze suggestion. This fraction is applied to measured liquid resources through the stress window; it is an aggregate proxy, not fund-level gates. Editing the percentage overrides that proxy. No extra endowment reserve is assumed; R2 operating reserves remain outside the endowment.

## Risk measures
Real payout-cut risk: probability of at least one decline greater than 5% between consecutive projected annual actual payouts after inflation adjustment. No year-1 cut is calculated without an observed prior-year payout. Real payout volatility: within-path population standard deviation of annual real payout growth, then median across paths; one-year horizon returns zero because no growth observations exist. Zero-to-zero payout growth is excluded; a positive-to-zero drop counts as −100%.

## Important limitations and confirmations
- R1 returns are gross of management fees and trading costs. No net-return claim is made. An annual return adjustment is available; no fee rate is invented.
- Historical data include R1's flagged early backfills. PE/VC are listed replicating indices, not actual fund cashflows or appraisal NAVs. Forward targets were selected using data through August 2026; retrospective replay of them is not out-of-sample evidence.
- Same-regime quarterly rebalancing is an R3 choice permitted by R1's guide. Private pacing can temporarily prevent other target constraints from being met. Only the liquidity constraints are monitored as breaches here; this is not a full constraint-compliance audit.
- The data-defined starting weights and R2 profile are authoritative; historical strategy diagnostics for MeanCVaR still use the original combined-cohort backtest, not a separate Private/Public backtest.
- R2 outstanding: monitoring interpretation of 3× payout, zero extra endowment-funded debt service, zero other residual endowment changes, FY2022 as common expense reference, and normal non-tuition revenue growth during stress. Existing choices are retained; no new R2 answers are inferred.
- Public MeanCVaR sharing and the 10% warning margin can be replaced when confirmed. Detailed private redemption/distribution schedules are not needed for this monitoring-only scope.
- Long horizons can make a linear tuition-discount path exceed 100%; the model raises an error rather than silently capping it. Revise that assumption before such a run.

## Sources in this delivery
R1: `data/r1/forward_weights_by_regime.csv`, asset and strategy histories, macro/regime series, asset shock recommendations, `R3_Simulation_Inputs.xlsx`, `R1_Responses_Request_Layout.xlsx`; the original R1 guide and responses are in `reference/R1`.
R2: `data/r2_scenarios.csv`, `data/r2_stress.csv`; see `R2_UPDATE.md` for the integration record.
External citations embedded in R1's documents are attributed to R1 and have not been independently revalidated in this software update.

## Running
Python 3.11+ recommended. `pip install -r requirements.txt`, then `streamlit run app.py` from this directory. Deploy the full directory, including data, reference and icon folders. Do not upload app.py alone.
Run regression tests with `python -m unittest test_r1 test_r2 test_liquidity -v`.
