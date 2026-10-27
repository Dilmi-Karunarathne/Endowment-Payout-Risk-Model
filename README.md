# Endowment Payout-Risk Simulation App

This package implements the Research 3 integrated endowment model using:

- R1 P4 quarterly historical returns and liquidity classification
- R1 full-history Normal / Recession / Elevated Inflation transition matrix
- R2 Private/Public $101M-$250M Low/Base/High institutional parameters
- D1/R1 CPI inflation history
- Provisional R3-derived D2 Other Endowment Changes benchmark

## Files

- `endowment_simulation_model.py` — model engine, historical validation, Monte Carlo, stress tests and risk measures.
- `app.py` — Streamlit user interface.
- `data/` — model-ready calibration CSVs derived from the project files.
- `requirements.txt` — Python packages.

## Run locally

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Recommended workflow

1. Open **Historical validation** and verify the 2013-2022 mechanics backtest.
2. Use **Monte Carlo simulation** with `Regime-switching bootstrap` as the main forward-looking method, or `Quarterly block bootstrap` as a simpler empirical baseline.
3. Keep **liquidity constraints OFF** for the validated core model. When turned on, buffer, cash need and forced-sale assumptions are scenario assumptions because R2/D2 have not finalized institution-level liquidity-policy benchmarks.
4. Use **Stress comparison** to compare baseline, recession-start and elevated-inflation-start paths.

## Stress testing

R3 stress-scenario framework (default view of the Stress testing tab)

Goal: evaluate payout sustainability under two major adverse economic regimes. Tick one or both scenarios and click "Run R3 stress scenarios"; the baseline is always included.

Scenario 1: High inflation & elevated rates. Conditions: high inflation, rising cost of capital, elevated operating expenses. Focus: maintaining real payout value and meeting institutional funding needs.
- Severity: replay of actual 2022 P4 returns and CPI (P4 -14.2%, CPI 8.0% average; stocks and bonds fell together as rates rose).
- Duration: 16 quarters in the Elevated-inflation regime (the 2021Q2-2025Q1 spell in the CPI history), with a CPI add-on so post-replay inflation matches that spell (5.0%) rather than the all-history elevated average (3.6%).
- Operating expenses: growth of 4.7% for 2 years (Commonfund HEPI FY2022 5.2%, FY2023 4.1%) vs the R2 base growth.
- Recovery path: R1 transition matrix after the stress window.
- Focus outputs: cumulative and annual real payout, change vs baseline, Pr(any support gap), total support gap, payout adequacy.

Scenario 2: Prolonged downturn & liquidity squeeze. Conditions: market losses, delayed private distributions, illiquid asset sales. Focus: meeting required payouts while minimising forced-sale asset losses.
- Severity: replay of the actual GFC P4 path, 2008Q1-2009Q2 (-22.0%; NACUBO FY2009 average endowment return -18.7%).
- Recovery path: -3% per year return drag for 2 years after the replay (assumption: slower than the actual 2009 rebound), then the R1 transition matrix.
- Gifts: -11.9% for 2 years (CAE Voluntary Support of Education, FY2009).
- Liquidity (constraints switched on): net private cash drain 2% of corpus per year for 3 years (calls continue while distributions are delayed), 50% of liquid assets unavailable for 2 years, 1-year payout reserve, 30% forced-sale discount on illiquid assets.
- Focus outputs: payout shortfall probability and depth, forced-sale probability and loss, liquidity coverage (cash available for the payout / planned payout), and a liquidity breaking point (the haircut or cash drain at which forced sales begin).

All shock parameters can be changed in the tab. The tab also shows a year-by-year variable-impact table (returns, inflation, expenses, gifts, real payout, support gap, liquidity, forced sales) and a calibration table that labels each parameter as historical data, external evidence or an assumption to be confirmed by R2/D2.

Additional exploratory scenarios

The earlier scenario library, custom builder, reverse stress test and sensitivity grid remain available behind the "Show additional exploratory scenarios and tools" toggle. They overlay shocks on the same model and the same random seed, so differences between scenarios come from the stress rather than sampling noise. The validated core is unchanged when no stress is applied (historical validation and baseline Monte Carlo results are identical).

Market scenarios
- Regime: forced Recession start (6q) and Elevated-inflation start (8q), as before.
- Historical replay: actual P4 returns and CPI for the GFC (2008Q1-2009Q2, -22.0% cumulative), COVID (2020Q1-Q2) and 2022 inflation/rates, followed by the regime-switching model from the replay's last regime.
- Hypothetical: equity crash (asset-class shocks x R1 P4 weights = -21.4% portfolio), rate shock with stocks and bonds falling together, stagflation (Elevated-inflation regime, -3% return drag and +2pp CPI for 5 years) and lost decade (-5% return drag for 10 years).

Endowment scenarios
- Donor retreat (gifts -60% for 3 years), spending and expense pressure, special appropriation (extra 5% draw in years 1-2).
- Liquidity squeeze and severe liquidity freeze: switch liquidity constraints on with haircuts on accessible liquid assets and capital calls; the freeze disallows forced sales so funding gaps become payout cuts.
- Combined: GFC + donor retreat + liquidity squeeze + special draw; stagflation + spending pressure.

Custom scenarios can be built in the app (replay window, portfolio or asset-class shock, return drag, CPI add-on, forced regime, gifts, spending, expenses, special draws, liquidity settings).

Outputs per scenario: median and 5th-percentile terminal real corpus, change vs baseline, Pr(real corpus below initial), VaR and Expected Shortfall of terminal real-corpus loss, median max real drawdown, cumulative payout and change vs baseline, Pr(support gap), payout shortfall probability and depth, forced-sale probability and loss, and a deterministic stress path with years to recover the real corpus.

Reverse stress test: the instantaneous market shock that leaves the deterministic terminal real corpus at a chosen % of today's endowment, optionally on top of an endowment scenario.

Sensitivity grid: instantaneous market shock x effective spending rate (optionally with lower gifts) on the deterministic path.

Hypothetical shock sizes are illustrative scenario assumptions, not calibrated forecasts.

Run the stress suite from the command line with: python stress_testing.py

Selected payout-risk measures

- Payout Shortfall Probability / Frequency
- Payout Shortfall Depth
- Expected Shortfall of terminal real-corpus loss

Expected Shortfall is calculated across Monte Carlo terminal real-corpus loss outcomes. In the deterministic validation path, only terminal real-corpus loss is reported.

## Important limitations

- P4 Medium | Normal is the current interim R1 portfolio; R1 is rebuilding portfolios around the seven NACUBO cohorts.
- R1 return observations cover 2007Q1-2023Q2. Regime transitions use the longer 1992Q2-2026Q2 history.
- Recession observations are limited, so recession-tail estimates should be interpreted cautiously.
- Other Endowment Changes for the private benchmark is provisional and R3-derived from raw D2 data.
- Operating revenue / budget-surplus mechanics remain outside the core model until revenue excluding investment income is available.
