# Simplified Endowment Payout Risk Model v5 — Separate Asset Pools

This is the **single-baseline, five-year** Streamlit application. It uses R1's quarterly joint historical bootstrap and asset-level rebalancing, R2's Public/Private Low/Base/High institutional assumptions, and R1 asset-sale timing and cost data for **cash-first payout execution**. There are **no stress-test controls, batch jobs or alternative return-model sliders**.

## How to launch

```bash
pip install -r requirements.txt
streamlit run app.py
```

Choose only: institution (Public/Private), R2 profile (Low/Base/High), R1 strategy, starting endowment ($M), and paths (100/500/1000/5000). Five years (2027–2031), HRP/High Inflation starting allocation, four-quarter blocks, seed 42, and three-month asset-sale deadline are fixed baseline assumptions.

## Gift policy — carried forward from v4

**New gifts are modeled as nonspendable endowment assets, not cash available for the current payout.** This is a **conservative research assumption**, not a donor-classification statistic supplied by R2. The simulator uses *two separate invested holdings ledgers*:

1. **Spendable opening endowment:** The starting $150M (or user's starting value) is assumed eligible for general payout, subject to the R1 13-asset sale timetable, liquidation costs and existing cash balance. Some opening assets cannot be sold within the 3-month deadline.
2. **Restricted new-gift account:** Each year's new gifts follow the applicable R2 gift rate and are credited only to this separate account. Future investment gains or losses on those gifts are also retained there and **cannot fund general payouts anywhere in the five-year projection**. Both accounts are invested through R1's quarterly asset-return and rebalancing engine; new gifts enter at the annual payout calculation stage, *after* that year's market returns.

The funding executor **never sees restricted holdings** and therefore cannot use them through cash, security liquidation or rebalancing to cover payouts. No gift money is double-counted. The two asset pools add up to total endowment wealth, and both receive appropriate R1 investment returns. The separate-account policy is more conservative than merely restricting the original donated principal. It should be replaced by donor-specific terms if available.

## What v5 adds — three reconciled endowment balances

The dashboard now reports **total endowment**, **existing (payout-eligible) endowment pool**, and **restricted new-gift pool** separately. The latter includes all new gifts and their subsequent investment performance, and remains inaccessible to payout funding for the entire five-year projection. The existing pool is payout-eligible **subject to R1's asset sale times and costs**: its full value is not necessarily instant cash.

There are three end-of-year amounts for every simulation year and path:

```text
Total endowment assets = Existing / payout-eligible asset pool + Restricted gift pool
Restricted pool end = Restricted pool start + Restricted pool investment gain + New gifts
Existing pool end = Existing pool start + Existing pool investment gain
                    + Other endowment changes - Actual payout - Other cash paid
                    - Liquidation costs
```

The model verifies these identities for every path-year in **nominal and inflation-adjusted values**. Market gains on the restricted pool remain restricted, so the new **existing-pool earnings-only coverage gap** is shown separately: `max(0, planned payout - investment gain on existing/payout-eligible pool)`. The old total-earnings and earnings-plus-gifts gaps remain economic *context*, not payout-cash availability.

### New dashboard section: Where is the endowment wealth?

- Three end-of-horizon cards showing **mean nominal** total / existing / restricted balances. The two components add to total.
- Three-line chart showing **mean inflation-adjusted** total / existing / restricted assets over five years. Their means add exactly on each year. The earlier purchasing-power chart, showing **median total** and 10th–90th percentile range, remains unchanged.
- Five-year table showing all three pool values in **nominal and real** dollars.
- Expandable annual detail of existing-pool investment gain, gift-pool investment gain, new gifts, actual payouts, eligible asset-sale proceeds, and liquidation costs.
- Additional **real existing-pool erosion probability**, defined as the share of five-year paths where inflation-adjusted existing assets fall below the starting endowment at least once.
- All path-year CSVs now include opening balances, individual-pool investment gains, year-end balances and real pool balances, supporting full reconciliation.

**Why use means for the decomposition?** The median of a sum generally differs from the sum of the component medians. Means preserve the accounting identity when aggregated across paths. The headline total-wealth erosion/ES measures are preserved, and the existing-pool measure is reported separately so restricted gifts cannot hide deterioration in payout-eligible resources.

### Core calculations

- **R2 annual gifts:** `gift_rate × beginning_total_endowment`; these gifts increase restricted endowment assets.
- **Planned payout:** R2 3-year average × spending rate, subject to 3%–5% of the beginning total endowment.
- **Existing-pool earnings-only coverage gap (primary research measure):** `max(0, planned payout − investment gain on existing eligible assets)`. The prior `max(0, planned payout − total investment gain)` is retained for comparison (it includes restricted-pool earnings).
- **Earnings + gifts gap (economic context only):** `max(0, planned payout − total investment gain − new gifts)`. **This does not represent resources available to fund payouts**, because all new gifts are restricted.
- **Payout funding capacity:** eligible opening/accumulated spendable cash + net asset-sale proceeds from the *spendable ledger*, after reserves and higher-priority obligations. R1 sale times/costs apply.
- **Actual payout:** `min(planned payout, payout funding capacity)`.
- **Payout shortfall:** `planned payout − actual payout` (nonnegative).
- **Total ending assets:** spendable ending assets + restricted-gift ending assets. Includes all investment returns and gifts; subtracts paid distributions and modeled transaction/liquidation costs once.
- **Institutional support gap:** `max(0, required R2 benchmark support − actual payout)`.

## Headline outputs and charts

- Four headline cards: **frequency of payout shortfall**, **real principal erosion probability**, **institutional support-gap probability**, and **purchasing-power Expected Shortfall (95%, % of initial assets)**.
- Three charts: signed **actual minus planned payout** in USD millions; median/10–90% **real total endowment purchasing power**; and mean **real total/existing/restricted asset pools** in USD millions.
- Annual table: earnings-only gap (primary), earnings + gifts gap (context), conditional institutional support gap, and restricted gift account balance.
- A new pool-balance reconciliation table, an expandable earnings and gift-attribution table, an expandable five-year return table and four downloadable CSVs retain investment returns, path-by-path calculations, and full audit fields such as `restricted_gift_assets_end`, `spendable_assets_end`, `restricted_gifts_received`, and `gifts_available_for_payout` (= 0).

## Key limitations

- R2 reports **gift amounts**, not the shares legally restricted, permitted spending purpose, or restriction-release schedules; **100% restriction of new-gift subaccount, including its earnings, is a hypothetical conservative policy**, not a verified institutional fact.
- The opening endowment is treated as spendable except for financial/market-sale restrictions. Actual legacy donor restrictions and appropriation rules are **not** separately modeled.
- Eligible sales occur at an **annual payout date with a 3-month sale deadline**; intra-year distribution calendars and private-fund cash flows are simplified.
- The R1 return sample contains model proxies and backfilled data; investment-management fees are not fully included.
- Current R1/R2 benchmarks and the real-payout measures use stylized assumptions; interpretation requires validation. Even with restricted gifts, the model may report **0 observed payout shortfalls**, because existing eligible cash and investments can cover the scheduled payouts.

## Test

Run `python test_simple_model.py` for both specific restriction regressions and 100-path smoke tests on all six R2 institution/profile combinations. The tests cover locked-asset funding, two-year no-leakage across rebalancing, annual roll-forward, gift segregation, return coverage, funding shortfalls, the four headline measures and risk tables. A Streamlit browser visual review is still required if Streamlit is not installed in the testing environment.


## v5.1 dashboard compatibility fix

This version prevents `KeyError: mean_total_assets_m` when Streamlit Cloud
retains results calculated with an older dashboard version or when app.py
is updated without simple_analysis.py.  A result-schema guard now detects
incompatible results, clears them from session state, and requests a new run.

**When deploying to GitHub/Streamlit Cloud:** Copy every file from this
version into the repository, especially `app.py`, `simple_analysis.py`,
`dashboard_contract.py`, `endowment_simulation_model.py` and `r1_model.py`.
Commit the files together. Restart the Streamlit app and click **Run simulation**.

The simulation's investments, restricted gifts, spending, and payout rules
have not been changed by this compatibility fix.
