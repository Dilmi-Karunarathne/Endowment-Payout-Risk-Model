# Cash-first payout and risk-measure update (v11 candidate, November 2026)

## Purpose and provenance

This revision implements the requested **R1/R2-driven liquidity-informed endowment payout** in the supplied v10 project. It retains the R1 13-asset historical return/bootstrap architecture and the R2 institution benchmarks. User-provided metric definitions and the uploaded comparison infographic are the basis of the dashboard updates; the external ChatGPT shared-conversation link was not retrievable during implementation, so no unstated requirements were inferred from it.

## Core payout accounting — USD millions

1. Simulate asset-level R1 investment returns, quarterly rebalancing, and rebalancing costs. PE and VC may no longer be silently sold in quarterly rebalancing; stressed hedge-fund redemptions are likewise blocked inside the quarter. The 5-percentage-point pacing on private allocation *increases* remains an approximation, not a fund commitment ledger.
2. At the **annual payout date**, the R1 cash/T-bill holding contains the investable cash after market returns and prior rebalances. R1's source data provide total-return proxies, **not** a separate schedule of dividends, coupons, or private-fund distributions. Therefore no additional `investment income received in cash` is assumed beyond the return already credited to the cash sleeve. Securities gains are **not** cash until sold.
3. Apply R2 new endowment gifts **once** to cash. **Assumption:** 100% are liquid and unrestricted for purposes of the baseline; donor restrictions are not supplied and must be investigated.
4. Compute planned payout from the R2 three-year average with a 3%–5% current-value collar; add special draws if the stress scenario requests them.
5. Determine which of the 13 R1 assets can be sold within the selected **1/3/12-month deadline** using the R1 supplied `ttc_normal_m` / `ttc_stressed_m` and `cost_normal_mid` / `cost_stressed_mid`. Optional restrictions, recession/overlap regime, forced-sale discount, and capital calls apply. PE takes 12 months normally and is unavailable under stress; VC is unavailable. Hedge funds take 3 months normally and 12 months under stress. Ordinary public securities take 1 month.
6. Funding waterfall: **cash first**, then cheapest eligible asset sales until planned payout, other endowment obligation, capital calls and reserve are covered, or no eligible assets remain. Asset-sale costs are deducted once from wealth. Higher priority: other endowment cash need → capital calls → planned payout; protected cash reserve is ring-fenced where possible. Paid capital calls move cash to PE/VC and do not directly reduce endowment wealth.
7. `Actual payout = min(planned payout, cash funding capacity after senior obligations and reserve)`. No proportional or fictitious redemption of locked PE/VC is used to fund a payout. Update endowment assets with simulated investment gain + gifts − actual payout − paid other obligation − **actual** liquidation costs. Capital calls are asset transfers.

### Funding capacity — interpret the user-provided formula without double counting

**Conceptually:** `Cash carried into the payout date + cash investment income received + available new gifts + eligible gross sale proceeds − asset-sale costs − protected reserve − higher-priority obligations`.

**Implemented:** the reported `cash_at_funding_date_before_gifts` **already includes cash/T-bill investment gains** and any rebalancing cash movements. It is *not* augmented with notional equity or PE gains. Gifts are added once, producing `cash_before_sales`. The maximum **net** eligible sale capacity already deducts R1 sale costs; thus costs must **not** be subtracted a second time. The `funding_capacity_for_payout` column also deducts reserve and higher-priority needs.

Potential eligible sale value is not the same as **actual** gross sales; the model only sells enough to satisfy its funding target. The result includes gross sales, actual net proceeds, transaction costs, remaining cash, and separate asset-level sale fields for audits.

## Risk measures and dashboard format

| Requested measure | Updated implementation | Output |
| --- | --- | --- |
| **Payout-funding shortfall** | `max(0, planned_payout − actual_payout)`; by year mean across paths (zeros included) | Annual deviation bar chart, **$M** |
| **Earnings-only coverage gap** | `max(0, planned_payout − investment_gain)` | Annual table in **$M**, diagnostic |
| **Earnings + gifts coverage gap** | `max(0, planned_payout − investment_gain − endowment_gifts)` | Annual table in **$M**, diagnostic |
| **Payout coverage ratio (E+G)** | Not added, per user request | Removed from new display |
| **Liquidity coverage ratio** | `(cash available + potential **net** eligible sales − reserves − higher-priority obligations) / planned payout` | Annual table; **×** |
| **Frequency of payout shortfall** | Fraction of simulated **paths** with ≥1 year below plan | Headline **%** |
| **Principal drawdown from spending** | Optional, not added as headline; tracked indirectly by earnings + gifts gap | None |
| **Real principal erosion risk** | Fraction of paths with real value below starting purchasing-power threshold at least once | Headline **%** |
| **Real endowment asset path** | Inflation-deflated ending wealth, percentile band | Existing purchasing-power chart, **$M** |
| **Institutional support gap** | Fraction of paths with ≥1 year `actual_payout < required_support` | Headline **%** |
| **Conditional institutional support gap** | Sum of positive dollar gaps / number of gap-year events | Detail table, **$M** |
| **Expected Shortfall (purchasing power)** | Mean of the worst `(1−α)` proportion of `max(0, 1 − terminal_real_assets / initial_endowment)` | Headline **% of starting endowment**, default α=95% |

ES is computed *after* all actual payouts and inflation adjustment. It is **not** a market quarterly-return ES and not a payout shortfall ES. The preexisting code already calculated this terminal real-value loss; the revision makes its requested definition explicit and displays it as a primary KPI.

The unchanged **R1 40%-liquid-share** and **R2 3×-annual-payout** tests are shown as supplementary monitors, not substitutes for actual payout execution. All six R2 profile combinations (Public/Private × Low/Base/High) are now selectable on the main dashboard, in addition to the 54-combination batch export.

## What is still not modeled / validation to do

- **Annual-only settlement:** Sales are assumed accessible by the selected annual deadline; no monthly payment schedule, queue, settlement lag within the period, or worst-month cash balance is simulated. For real-world funding, add a monthly cash-flow timeline.
- **Donor restrictions / restricted cash:** Baseline assumes every endowment gift can be spent; R2 has no restriction split or cash-gift timing. Private-fund distributions and dedicated operating gifts are also not separately modeled.
- **R1 liquidity estimates:** Sale windows and liquidation midpoints are conditional on position sizes and may not scale to unusually large trades. The 13-asset assumptions are proxies, not execution guarantees.
- **Forced-sale discount:** An optional extra haircut is additive in economic effect (implemented multiplicatively with normal sale costs) on **eligible** sales; it does not grant the right to sell otherwise locked funds. No borrowing facility is modeled.
- **Private assets in quarterly rebalancing:** Redemptions of PE/VC are blocked; increasing their positions still follows R1's 5pp pacing proxy rather than an actual cash-call/distribution schedule. Under a multi-year horizon, commitments should be added for further validation.
- **Returns and fees:** R1 total-return asset proxies are sampled as before (with improved lockup-consistent quarterly rebalancing); costs include modeled rebalancing and liquidation, but not all institutional asset-management fees. Therefore rerun all v10 baseline statistics after this change.
- **Statistical interpretation:** Earnings + gifts coverage gaps can be positive when investment returns are negative. They are measures of accounting sustainability, **not evidence of unavailable cash**, and are not automatically cash shortfalls. The liquidity funding calculator answers the separate cash question.
- **R2 profiles:** Low and High are *marginal parameter percentiles*, not observed internally consistent best/worst institutions. Use controlled stress experiments for adverse coherent assumptions.
- **Risk tails:** A 0% payout failure in a finite bootstrap sample is not proof of 0% true risk. Stress reduced access, capital calls, gifts and return assumptions; check larger paths and multiple random seeds.

## How to run and verify

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q test_cash_first_update.py test_model_validation.py
python -m streamlit run app.py
```

Dashboard: **Institution** → **R2 benchmark profile** → **Portfolio strategy** → **Run analysis**. Advanced options include the 1/3/12-month deadline, reserve, access restrictions, extra forced-sale discount, and scenario stress tests. For main comparisons, start with the 1,000-path development run and increase to 5,000 for baseline reporting; 10,000 can be used for numerical stability (not an economic validation substitute).

### Illustrative hand-check

`$100M = $2M cash + $58M IG corporate bonds + $40M private equity`, payout `$5M`, normal 3-month window and IG normal sale cost `0.15%`:

- Need to raise `$3M` from bonds; gross sale `$3M / (1−0.0015) = $3.004507M`.
- Sale loss `$0.004507M`; net cash proceeds `$3M`.
- Actual payout `$5M`; ending fund `$94.995493M` with PE unchanged at `$40M`.
- If all `$100M` were locked in PE, normal 3-month funding capacity is zero and the `$5M` payout is **unpaid**, despite sufficient total endowment wealth.
