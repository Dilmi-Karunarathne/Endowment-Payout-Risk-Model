# Source and usage restrictions

Research Team 1, 15 Nov 2026 R3 Handoff Package (user-supplied internal research handoff).
CSV inputs are copied from the user-supplied CSV snapshots without altering the source rows.

- Data are **internal research use only**, and the optimized peer constraints are derived from a confidential NCSE study. Do not make the GitHub repository or raw inputs public without permission.
- Only ten final portfolios (five strategies x dynamic/static) are supported; the older nine-strategy files have been removed from this release.
- Asset returns are gross of management fees. R3 simulates new path-specific rebalancing costs from the raw asset data; original portfolio Net_Return is a historical reference and not applied as an additional fee deduction.
- Portfolio-level crisis-value weights (g) and stressed one-month access weights (h) serve different risk definitions; see UPDATED_R1_HANDOFF_AND_PAYOUT_RISKS.md.
- Underlying source guide/validation documentation remains in the **original R3HandoffPackage.zip provided by the user**, not in this deployable ZIP.
