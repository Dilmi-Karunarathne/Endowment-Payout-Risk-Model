# v14 — Section-specific portfolio selectors

- **Portfolio analysis** compares exactly three user-selected portfolios;
  HRP Dynamic, Mean-CVaR Dynamic and Equal-Weight Dynamic are the defaults.
- **Overview, Payout risk measures, Stress testing, Policy responses,
  Scenario comparison** analyze one selected portfolio only.
- Keep all seven navigation sections and Light/Dark appearance modes.
- Matching single- and three-strategy results can be reused when switching
  sections without recalculating the unchanged simulation inputs.
- All financial calculation files and Research 1 handoff data unchanged.
- Details: `INTERFACE_V14_SELECTION_RULES.md`.

---

# v11 — User-facing layout and comparison bug

- Fix missing comparison column causing a Pandas KeyError at app.py (Downside and liquidity).
- Add explicit result comparison schema contract, and prevent display of stale/incompatible results.
- Redesigned Light/Dark dashboard, six readable KPI cards, risk insights, 10th–90th real endowment bands, balanced charts, streamlined navigation and expandable details.
- Existing market assumptions, research data, strategy definitions, cash funding and Monte Carlo formulas remain unchanged.
- Tests and release details: `INTERFACE_V11_RELEASE_NOTES.md`.

---

# 15 November 2026 Research 1 handoff integration

- Replaced older nine-strategy data inputs with the Research 1 handoff of 10 final portfolios (5 methods × Static/Dynamic).
- Integrated new November asset returns, forward Calm/Turbulent weights, historical portfolio reference returns, liquidity and R1 stress recommendations.
- Preserved 13-asset simulator, restricted gift ledger, cash-first payout calculations, constrained rebalance cash-feasibility fix and institutional benchmark cases.
- Added **Payout risk measures** tab with four headline measures, payout deviation graph and annual gap table, for every strategy and scenario.
- Added Research 1's 20% crisis-sale-value (g) test separately from 40% and 20% one-month access-share (h) monitors.
- All user-facing strategy names updated; cached v9 results are invalidated.
- See `UPDATED_R1_HANDOFF_AND_PAYOUT_RISKS.md` for assumptions, missing information and confidential-data caveats.

---

# Latest release: stress impact and matched policy experiments

- Added **Policy responses under stress** to the sidebar: unchanged baseline, adverse environment, then the **identical** shock with one fixed alternative spending/reserve policy (Private: 4%; Public: 3.5%; reserve 0.5× or 1.5× planned payout).
- Added explicit stress-to-baseline and policy-to-unchanged-stress differences for returns, unpaid distributions, both liquidity thresholds, minimum buffer, real payout-eligible wealth, cumulative real payouts and purchasing-power Expected Shortfall.
- Added first-year payout-failure timing, two-year consecutive unpaid payout and eligible-earnings-gap frequencies, and path-level total unpaid distributions.
- Added **Stress diagnostics** tab: scheduled versus actual payout charts, conditional unpaid-payout probabilities, return/wealth/liquidity charts, and cash-flow reconciliation by year.
- Preserved the original sample-path investment engine, restricted-gift behavior, cash-first funding and the quarterly-rebalancing liquidity fix.
- Dashboard now invalidates stale saved results using a new schema token.
- New dedicated documentation and regression tests: `STRESS_POLICY_UPDATES.md` and `test_stress_policy_improvements.py`.

---

# Latest correction: fundable quarterly rebalancing

- Fixed simulation-stopping failures when illiquid minimum holdings and desired quarterly purchases exceed available trading cash.
- Locked holdings are never redeemed to fund routine rebalancing, and frozen assets remain unchanged.
- Unaffordable target trades are reduced or deferred; only executed transactions incur their actual trading costs.
- Updated validation tests and documentation: `REBALANCING_FIX.md` and `test_rebalancing_cash_constraints.py`.
- No changes to institutional profiles, gifts, payout policy, liquidity thresholds, or investment return history.

---

# Final release changes

## Added

- Stress testing with standard/severe institution-specific assumptions, two main
  tests and nine supporting stress/replay cases.
- What-if comparisons for spending, gifts, reserve policies and institutional
  profiles, plus a custom scenario editor.
- Explicit shared market seeds for baseline, strategy, stress and what-if runs.
- Baseline differences, paired wealth changes, unpaid capital-call reporting,
  assumptions previews and complete calculation/settings exports.
- A simple four-view dashboard and embedded model guide.

## Framework preserved

The simplified model controls the quarterly asset engine, cash-first funding,
spending collar, restricted gift accounting, capital-call transfers and liquidity
measures. The original baseline matches exactly when evaluated on identical
path seeds. Both institution types, all six profiles and all nine portfolios
remain available.

## Corrections

- Frozen emerging-market/high-yield positions cannot be sold through routine
  rebalancing or to pay rebalancing costs during the specified freeze.
- Scenario call schedules replace or scale the baseline schedule explicitly;
  there is no double charging of calls.
- The average unpaid payout is zero when no unpaid-payout events occur, rather
  than showing a floating-point residual.
- Settings changes hide stale results until rerun, and the result schema is updated.

## Terminology

Descriptive labels are used throughout the interface, data paths, exports,
source modules and documentation. Old research-team codes are removed. Deploy
the package together because the module and dataset names have changed.

## Deliberately deferred

A comparable 70/30 benchmark, a complete management-fee schedule and a separately
calibrated large-public-foundation example remain outside this release.
