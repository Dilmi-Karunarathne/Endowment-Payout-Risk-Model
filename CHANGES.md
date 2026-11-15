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
