# R2 integration — 8 November 2026

This update uses the final R2 benchmark workbook and R2_Stress_Benchmarks.xlsx. It supersedes older R2 assumptions in README and ASSUMPTIONS_AND_CONFIRMATIONS.

## Implemented
- Exact Low/Base/High institutional values in data/r2_scenarios.csv.
- Three-year payout calculation with a 3%–5% collar of beginning endowment. Optional annual growth limits apply before this collar. Extraordinary draws remain separately identified.
- Tuition, other revenue, operating balance and deficit outputs. Deficits do not trigger automatic endowment withdrawals.
- Enrollment and discount-change controls use R2's multiplicative tuition adjustment relative to each selected profile. Baseline embeds normal enrollment/discount trends. Invalid long-run discount paths raise a clear error instead of clipping silently.
- Cohort-specific Standard/Severe expense and gift stresses; available in the main stress panel and relevant additional scenarios. Standard means standard adverse stress, not the unstressed baseline.
- Expense stress applies in the named year. Starting expenses are the normal Year 1 projection; the stress-to-normal growth ratio adjusts that level. Normal growth resumes from the higher expense level afterward.
- Special appropriation removed from the cohort-aware scenario menu because R2 supplies no calibration.

## Pending decisions and interim treatment
- Other endowment changes: zero, following final R2 roll-forward, pending confirmation.
- Additional endowment-funded obligations: zero, editable; not a claim that the university has no debt. The 5% debt-service ceiling is not treated as a payment.
- Other revenue retains normal growth during expense stress, pending confirmation of linkage.
- 90-day operating reserve stays outside the endowment and is not funded or deducted here.
- FY2022 selected as the supplied inflation reference, not labeled the worst public expense-growth year.
- R1 allocation, switching, market stress and liquidation parameters are unchanged and provisional.
- The supplied revised liquidity engine is retained. Professor's proposed monitoring-only replacement is NOT implemented in this data integration. 3× coverage is not imposed as an additional cash reserve. Final eligible assets, threshold and rebalancing rules need agreement.
- Gifts are assumed cash-available before annual payouts. Restrictions/timing remain a simplification.

## Model boundaries
Portfolio returns remain an aggregate proxy applied to funding groups, not an asset-level dynamic trading engine. The operating budget uses cohort statistics, not a reconciled individual university. Enrollment/discount sensitivities affect tuition from Year 2 onward. No automatic deficit rescue or borrowing.

## Validation
17 unit tests pass: funding conservation, liquidity limits, calls, all six portfolios, scenario smoke checks, final R2 values, payout collar, stress timing/recovery, budget identity, tuition baseline and enrollment effect, and both severe cohort settings.
