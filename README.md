# Endowment Payout Risk — Simple Baseline Model

This is a **single-run Streamlit app** built from the supplied v11 cash-first payout model. It keeps the same underlying R1/R2 data and simulation engine, but removes the stress-testing tabs, return-method comparisons, sensitivity grids, batch exports, and advanced controls.

## How to run

Extract the ZIP into a folder, then in that folder:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The application opens in your browser. Select five inputs and click **Run one simulation**.

## Five inputs you can change

1. Institution: Private or Public
2. R2 benchmark profile: Low, Base or High
3. R1 investment portfolio: any of nine strategies, default HRP
4. Starting endowment in $ millions, default $150M
5. Monte Carlo simulation paths: 100, 500, 1,000 or 5,000, default 1,000

## Fixed baseline assumptions

- Project five years, 2027–2031.
- Initial portfolio regime: R1 High Inflation allocation (historical handoff state).
- Historical market simulation: R1 13-asset **joint 4-quarter block bootstrap** with sampled inflation.
- Random seed 42. No stress overlays, no return shifts or volatility multipliers.
- Quarterly R1 rebalancing and transaction costs, subject to the original v11 implementation limitations.
- R2 three-year-average spending rule, with 3% payout floor and 5% ceiling.
- R2 baseline gift-rate for the chosen institution/profile; gifts credited to cash and assumed liquid and unrestricted.
- Cash-first payout execution at an **annual** payment point. If cash is insufficient, R1-eligible assets can be sold within **3 months**, after applicable asset-specific costs.
- No added capital calls, protected reserves, other cash needs, extraordinary spending or borrowing facility.
- Historical past endowment values initialized to the starting endowment, unless actual prior values are supplied in a future extended version.
- R1 40%-liquidity and R2 three-times-payout indicators are monitored; **they do not cap actual payout**.
- Management fees are not completely modeled. No monthly cash calendar or separate private-fund distribution schedule.

## Main calculations — all dollar amounts in $ millions

**Planned payout**

```text
Three-year average = mean(beginning endowment this year and prior two years)
Raw payout          = R2 spending rate × three-year average
Planned payout      = min(5% × beginning assets, max(3% × beginning assets, raw payout))
```

**Cash funding:**

```text
Maximum payout funding capacity
  = max(0, cash already held at annual payout date
           + additional endowment gifts credited to cash ONCE
           + net value of eligible asset sales (gross minus liquidation costs)
           - protected reserve - higher-priority obligations)

Actual payout       = min(planned payout, capacity)
Unpaid payout       = max(0, planned payout - actual payout)
Earnings+gifts gap  = max(0, planned payout - investment gain - endowment gifts)
```

The v11 implementation records `cash_before_sales` **after gifts have already been credited**. Do not add gifts again. R1 asset total returns are not assumed to be separate cash income. Investment gains on securities can only fund payouts through actual eligible sales.

**Ending endowment**

```text
Beginning assets + net modeled investment gain + new gifts
    - actual payout - actual asset liquidation costs - any additional paid obligations
```

**Headline measures:** Median five-year annualized investment return; probability of at least one payout-funding shortfall; probability of at least one real principal erosion event; probability of at least one institutional support gap; expected terminal real purchasing-power loss among the worst 5% of paths.

## Files

- `app.py` — simplified user interface
- `simple_analysis.py` — single baseline runner and summaries
- `endowment_simulation_model.py`, `r1_model.py`, `payout_funding.py`, `liquidity_model.py`, `portfolio_return_simulation.py` — **unchanged v11 calculation engine**
- `data/` — unchanged R1 historical inputs and R2 benchmarks
- `test_simple_model.py` — reproducibility and accounting tests

## Limitations

- An **annual** cash funding approximation is used, not an actual monthly payment schedule.
- Earnings + gifts coverage gaps do **not** automatically imply unavailable cash or unpaid distributions.
- R2 Low/High parameter bundles are separate percentile estimates rather than one observed institution.
- A zero payout-shortfall event rate with a finite number of paths is not a proof of zero real-world risk.
- The underlying baseline remains a research simulation and is **not** yet out-of-sample validated.

For a fuller stress/scenario analysis, use the separate original v11 research package; this simple edition does not run those analyses.
