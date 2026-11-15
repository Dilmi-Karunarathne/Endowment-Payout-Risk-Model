# Endowment Payout Risk Model v7 — Gift Investment Growth & 5,000–10,000 Paths

This is the **simple, single five-year Monte Carlo** app. It retains v5.1's R1 return simulation, R2 private/public Low/Base/High operating and spending benchmarks, **cash-first payouts**, ring-fenced new gifts, and reconciliation of total vs payout-eligible vs restricted assets. There are no stress or batch controls.

**v6 change:** the previous zero capital calls and zero cash reserve have been replaced with **R1 strategy-specific modeling proxies** drawn from the original R1 November 10 handoff. These estimates are *not observed institution-specific commitments or independently confirmed endowment cash policies*. Use them as a liquidity-aware research baseline, not as statements about a real university's normal-year obligations.

## Launch

```bash
pip install -r requirements.txt
streamlit run app.py
```

Inputs: institution, R2 profile, R1 strategy, starting endowment in $M, and paths (5,000 or 10,000; default 5,000). Fixed five-year projection (2027–2031), seed 42, R1 four-quarter joint block bootstrap, HRP default, High Inflation starting allocation, 3-month R1 asset sale deadline.

## What is new

1. **Annual private-asset capital-call proxy.** Source: R1 `R3_Handoff_Package/05_Simulation_Inputs/CSV/liquidity_profile_by_strategy.csv`, base-case field `R3_Calls_Scaled_to_Private_Exposure`. Derived as `2% × PE+VC weight / 12.8%`; applied to beginning-of-year **total endowment assets** in 2027–2029, then zero in 2030–2031. For HRP the rate is **3.0356%**, or approximately **$4.55M in 2027 on $150M**. The call is funded from the **existing payout-eligible pool** and transferred into PE/VC holdings; it is **not a loss of total endowment wealth**. This R1 rate and 3-year duration were originally proposed for a liquidity scenario, not measured routine annual cash flows. Treat as a conservative proxy until R2/institutional data provide unfunded commitments and distributions.
2. **Protected payout cash buffer.** Source: R1's `R1_Stress_Test_Responses.docx`, Item 12, and the strategy-specific `Cash_Years_of_Payout` field in the same input table. The target is the current planned payout multiplied by the R1 recommended number of years (HRP **1.00× payout**; EqualBucket **0.75×**; BlackLitterman **0.50×**; other seven strategies **1.00×**). This is a **protected reserve** for remaining liquid assets, not an extra payout and not an expense. Actual reserve policy and whether protected under stress remain an R2/institution decision.
3. **Funding priority.** Eligible existing cash + three-month-saleable eligible R1 assets (net of costs) funds higher-priority endowment needs, then capital calls, then payouts while protecting the target reserve. The requested planned payout is capped by available funding. If calls cannot be fully funded, the model records an **unpaid capital-call amount** separately; it is not silently counted as a payout shortfall.
4. **New dashboard expander:** annual requested and funded capital calls, unpaid calls, protected reserve target, reserve shortfall, eligible net sales, liquidation costs, and unpaid payouts. The original four headline cards and main charts are unchanged; path-year CSV has new audit fields.

## Assumptions that remain unchanged

- **New R2 gifts and all investment gains on those gifts remain in a segregated, nonspendable pool for five years.** R2 provides gifts rates, but NOT a 100% donor restriction statistic; this is a conservative R3 convention.
- **R1 asset-class normal/stressed sale times and midpoint costs** remain in effect. No *additional* blanket public-asset haircut is assumed; R1 specifically recommends 0% additional market-side restrictions in base conditions.
- R1's 40% stressed liquid share and R2's 3× annual payout asset-coverage policies are separate monitoring thresholds, not automatic payout guarantees or duplicate cash reserves.
- **No separate other annual endowment cash need** or borrowing, because amounts or facilities are not supplied; no additional flat forced-sale discount to avoid duplicating R1 costs.
- R2's **90 days of university operating expenses** is not deducted from endowment cash; that belongs to the university's operating-budget account, not necessarily the endowment fund.
- Annual funding with a three-month asset sale deadline, not detailed monthly intra-year cash-flow timing. Private-fund distributions, subscription line credit, management fees, and donor restrictions on opening assets remain unmodeled.

## Formula summary (USD millions)

```text
CapitalCall_t = BeginningTotalAssets_t × R1PortfolioCallRate, t = 1,2,3
              = 0,                                          t = 4,5
ReserveTarget_t = PlannedPayout_t × R1ReserveYears
FundingCapacity_t = max(0, eligible cash + net 3-month asset-sale capacity
                        - reserve target - other needs - capital call request)
ActualPayout_t = min(PlannedPayout_t, FundingCapacity_t)
UnpaidPayout_t = PlannedPayout_t - ActualPayout_t
```

Net proceeds use R1 per-asset sale times and liquidation costs. Eligible cash is from the opening endowment and its investment returns, **never restricted gift assets**. Asset sales transfer value from securities to cash, not generate new investment income. Capital calls transfer into private assets; sale costs and payouts reduce total wealth once.

## Data provenance

- R1 `R3 Handoff Package(3).zip` → `R1_Stress_Test_Responses.docx` Items 8–12; `liquidity_profile_by_strategy.csv`; `liquidity_data_datateam.csv`.
- R2 `R2_Benchmark_Guide_for_Research_3(3).pdf` (spending, gifts, 3× liquidity, university operating cash) and `R2_Stress_Benchmarks(2).xlsx` for stress guidance, not imported into this no-stress version.
- The input subset supplied with this package is `data/r1/r1_cash_requirements_by_strategy.csv` (source rates preserved).

## Tests and deployment

Run `python test_simple_model.py` and `python test_dashboard_contract.py`. These check 9 strategy inputs, 6 institutional benchmark combinations, reserve/call funding behavior, donor-gift segregation, the endowment accounting identity and schema compatibility. A Streamlit browser visual check is still needed in the deployment environment.

**GitHub deployment:** replace **all** files from this package in the repository, including `app.py`, `simple_analysis.py`, `dashboard_contract.py` and `data/r1/r1_cash_requirements_by_strategy.csv`. Commit together; reboot Streamlit Cloud and click Run simulation again. Older cached results are invalidated by the new schema version.

## v7 changes — clarified gift investment income and simulation limits

**Gift investment timing (verified in the existing v6 engine and regression-tested in v7):**

```text
RestrictedGiftPool_End(t) = RestrictedGiftPool_Begin(t)
                          + InvestmentGain_on_OpeningRestrictedPool(t)
                          + NewEndowmentGifts(t)
```

- Gifts received in **2027 are credited after 2027's investment period**. Those gift assets start earning R1 portfolio returns in **2028**, with gains retained inside the restricted pool. Future new gifts are treated the same way.
- The gift pool has its own actual asset-level holdings and return calculation (including modeled rebalance costs). Its rate is not necessarily exactly the same as the main payout-eligible pool's return.
- Both gift principal and gift-generated investment income remain unavailable for payout through the five-year projection. The dashboard has a dedicated **Gift-pool investment gain ($M)** column.
- **Monte Carlo paths must now be either 5,000 or 10,000** (default 5,000). Tests use short internal runs solely for speed; the published app and validated public analysis API enforce the choices.
- The result-schema version changed, so re-run the simulation after deploying all updated files.

**Note:** The fundamental gift accumulation calculation was already correct in v6; this release strengthens the explanation, makes growth explicit to reviewers, adds a deterministic regression test, and enforces the requested path limits.
