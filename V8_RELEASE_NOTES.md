# Version 8 — Endowment Investment & Payout Sustainability

## Changes implemented

1. Human-readable Streamlit terminology: **Institutional Benchmark Profile**, **Investment Strategy**, **Payout Liquidity Buffer**, **Payout Reliability**, and **Purchasing-Power Sustainability**. Source file paths and internal data identifiers are unchanged so the existing datasets continue working.
2. New **Compare three strategies** mode: Hierarchical Risk Parity, Minimum Variance and Mean-CVaR under the selected Private or Public institutional profile. All use identical explicit historical market-path seed vectors and matching quarterly asset/CPI data.
3. New stressed one-month liquidity-buffer metric (liquidity-weighted payout-eligible assets / planned payout). The *funding capacity / planned payout* ratio is a separate pre-existing diagnostic and is not mislabeled as liquidity buffer.
4. 40% and 20% liquid-share breach probabilities use the **same** minimum-within-path observations, including quarterly and post-payout annual measures. The numerator is stressed one-month liquidity-weighted payout-eligible assets, denominator is total endowment including restricted gifts. The 40% limit is only monitored and remains nonbinding.
5. Median five-year annualized investment return is promoted to headline output; the comparison mode provides distributions and P5/P95 returns.
6. Private/Base and Public/Base comparison modes, return/payout/liquidity/sustainability charts, downloadable comparison table and path-year financial calculations.
7. Fresh result schema to invalidate incompatible dashboard session state. Existing gift treatment, cash-first funding, capital calls, protected reserves and spending policy retained.

## Not changed or not added

- 70% global equity / 30% US bonds is not yet simulated: its matching approved return series are not included in the project package.
- Full portfolio management and administration fees are still absent. Results should not be described as net-of-all-fees returns.
- The model remains annual payout funding with quarterly returns and liquidity observations, not a day-to-day treasury system.
- Restricted gifts remain nonspendable in this illustrative baseline, not based on donor contract data.
- The strategy-comparison app supports 5,000 or 10,000 paths per portfolio. Execution can take several minutes when three portfolios are compared.

## Checks

Run `python test_simple_model.py` and `python test_dashboard_contract.py`. Tests use short *developer-only* simulation counts to check accounting, return paths, asset and gift ledgers, reserves/calls, 20% <= 40% breaches, and liquidity-buffer definitions. Public controls permit only 5,000 or 10,000 paths.

**Environment limitation:** Streamlit was not installed in the local execution environment; an attempted install was blocked by DNS/network access. The Python simulation and validation tests ran successfully, and Python syntax compilation passed; the final deployed browser visuals and complete 5,000-path three-strategy runs have not yet been independently verified.
