# Stress tests & policy-response upgrades (15 November 2026)

## Purpose

The endowment model now helps nontechnical audiences answer three distinct questions:

1. **Investment performance:** How much does a crisis change the investment return distribution?
2. **Payout reliability and liquidity:** Does the institution still receive its scheduled distribution, and how much liquidity remains?
3. **Sustainability:** What happens to the institution's real (inflation-adjusted) endowment value and to the pool that can support future payouts?

All scenarios use the established five-year cash-first model and **matched sampled market paths** within each strategy. They do not forecast the likelihood that a crisis occurs. All dollar amounts are USD millions.

## Updated user workflow

Run the model with `streamlit run app.py`.

- **Baseline & strategies:** Existing portfolio comparisons under current assumptions.
- **Stress testing:** Two main shocks are shown first: *High inflation & elevated rates* (2022 market replay and inflation/return overlays) and *Prolonged downturn & liquidity pressure* (2008–09 replay plus weaker recovery and liquidity restrictions). The existing optional scenarios—stagflation, recession-only, weak returns, liquidity-only, 2020 replay, one-off asset shocks—remain available.
- **Policy responses under stress (NEW):** Choose a base stress, then **one** fixed alternative policy. Every run includes three cases: **Unchanged baseline → Stress with existing policy → Identical stress plus alternative policy**. Select one portfolio for a compact, quick test; optionally compare HRP, Minimum Variance and Mean-CVaR using the same market draws.
- **What-if scenarios:** Existing non-stress spending, gift, reserve and institutional-profile sensitivities remain available.
- **Stress diagnostics (NEW results tab):** Side-by-side baseline-versus-stress charts for investment returns, unpaid annual distributions, liquidity buffers and real endowment value; an annual cash-flow reconciliation for the selected case; a first-failure timing and duration summary.

### Policy response options

| Fixed policy change | Institution | Spending policy assumption |
|---|---|---|
| Lower spending throughout the five-year stress | Private | 4.0% trailing-average spending rate instead of the Private/Base rate (~4.9%) |
| Lower spending throughout the five-year stress | Public | 3.5% trailing-average spending rate instead of the Public/Base rate (~4.03%) |
| Smaller cash reserve | Both | Protected reserve = 0.5 × annual planned payout instead of the portfolio baseline |
| Larger cash reserve | Both | Protected reserve = 1.5 × annual planned payout instead of the portfolio baseline |

All spending changes continue to obey the original **3%–5% collar**. The spending change is a fixed hypothetical policy for all five years, **not a conditional emergency response triggered by a liquidity breach**. A larger protected reserve can reduce current-year cash available for payout; the result is not guaranteed to be better.

The Public/Private illustrations retain the supplied $101M–$250M institution cohort assumptions. They do not represent any named university.

## Baseline-versus-stress measurement (NEW)

The scenario comparison table now includes, for the same strategy and institution:

| New comparison | Unit |
|---|---|
| Change in median five-year annualized investment return | percentage points (pp) |
| Change in probability of any unpaid payout | pp |
| Change in probability of breaching 40% / 20% stressed liquid-asset share | pp |
| Change in median minimum liquidity buffer | annual planned payouts (×) |
| Change in terminal purchasing-power Expected Shortfall (95%) | pp |
| Change in median real payout-eligible assets | $M |
| Change in median real total endowment | $M |
| Change in mean cumulative real university payouts | $M |
| Change in mean unpaid payout amount, conditional on an unpaid payout | $M |
| **Mean paired terminal real wealth change** | $M, calculated path-by-path using the same IDs |

Policy cases additionally show each measure's **incremental change relative to the *same stress* without the policy response**. For instance, a spending cut should be judged against the spending support that the university gives up as well as the retained liquidity and purchasing power; this is not an unconditional free improvement.

### Timing and duration (NEW)

The simulation also reports:

- First year of a truly unpaid planned payout (median among paths with at least one failure; blank if no failure occurs).
- Fraction of paths with at least two **consecutive unpaid payout** years.
- Fraction of paths with at least two **consecutive eligible investment earnings coverage gaps**.
- Mean cumulative five-year unpaid payout per path, and the mean conditional on at least one unpaid year.
- Chance of any eligible-earnings coverage gap. This is distinct from the chance of an unpaid payout: market gains can be insufficient, yet liquid principal can be used to fund spending.

These events are based on individual path-year simulations, not the averages of year-by-year percentages.

### Enhanced stress diagnostics

Select a portfolio and scenario in **Stress diagnostics**. The tab shows:

- Difference in investment return, unpaid payout risk, minimum liquidity buffer and purchasing-power expected shortfall.
- Actual and planned payouts, annual unpaid distribution amounts, and annual probability of payout failure.
- Real eligible asset value, annual investment returns and post-payout liquidity buffer (including a visual 3× reference line).
- Year-by-year net eligible asset sales, transaction costs, paid/unpaid capital calls, cash reserve target, institutional support gap and real endowment value.

The full-calculation ZIP still includes path-year calculations, scenario parameters and sources. An additional `stress_diagnostics.csv` mirrors the enhanced comparison table.

## What is intentionally unchanged

The Monte Carlo asset/CPI bootstrap, the historical crisis replay series, the cash-first funding waterfall, the policy spending collar, the restricted gift ledger (gifts added at year-end, invested from the following year, not payout-eligible), the 3-month sale deadline, the one-month liquidity monitor, and the corrected **liquidity-constrained quarterly rebalancing** logic all remain intact.

The 40% and 20% liquid-share breaches are **monitoring measures**, not forced payout failures. Long-term capital-call arrears are not carried forward. Operating-expense shocks affect **required university support** but do not automatically increase planned distributions. Restricted gifts raise total endowment value and therefore can affect future spending calculations despite being unavailable for payouts. Investment returns are not fully net of management and administrative fees.

## Validation plan and limitations

1. Run `python -m pytest -q test_stress_policy_improvements.py test_rebalancing_cash_constraints.py test_dashboard_contract.py test_scenarios.py` to check ledger consistency, scenario definitions, risk calculations, matched paths and the new policy comparisons.
2. Run Private/Base and Public/Base with **5,000 paths** using the corrected model for the selected final scenarios. Older pre-fix outputs are **not** valid proof of current results.
3. Compare 5,000 with 10,000 paths if necessary to assess Monte Carlo numerical stability.
4. In the final slides, label all risk probabilities as **conditional on the selected stress** and keep actual university cash payments separate from asset return shortfalls.

**Not implemented:** automatic governance-triggered spending changes, reverse stress-search threshold optimization, private-capital-call arrears, complete management-fee schedules, and a verified 70/30 benchmark. These are future research extensions, not hidden functions of the model.
