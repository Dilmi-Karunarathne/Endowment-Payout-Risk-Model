# v5 — Endowment Asset Pool Breakdown and Reconciliation

## Research question
Can the endowment support distributions from its pre-existing, payout-eligible assets without depending on newly restricted donations, and can it preserve real purchasing power?

## Changes from v4
- Added beginning and ending asset accounts for the existing spendable ledger and restricted gifts ledger.
- Added per-pool investment gain, measured after modeled rebalancing costs; gifts are added after annual investment returns, never treated as gains.
- Added real (inflation-adjusted) existing and restricted balances using the same cumulative inflation divisor as the total endowment.
- Added a separately computed existing-pool earnings coverage gap and real existing-pool erosion probability. Original total-wealth risk measures remain unchanged.
- Added UI cards, an additive three-line **mean real values** chart, five-year nominal/real pool table, and asset-flow drill-down.
- Added balance checks for each simulated path-year and all annual aggregate means.

## Definitions

**Total year-end assets:** asset market value of the original endowment plus restricted gift subaccount.

**Existing / payout-eligible asset pool:** remaining assets from original endowment and related investment results after payouts, applicable costs and other flows. Some holdings may still be locked or subject to a 3-month sale deadline. This is NOT the same as cash immediately available.

**Restricted gift pool:** gifts received after simulation start, plus associated gains/losses. The model assumes **the full pool, including earnings, is restricted for all five years**. That is a conservative analyst assumption, NOT an empirical restriction percentage supplied by R2.

**Economic coverage gap of total returns:** max(0, planned payout - total investment gain). Returns on gift pool are included; not automatically spendable.

**Existing-pool earnings gap:** max(0, planned payout - existing-pool investment gain). The closer match to current eligible resources, but even these gains may be unrealized and require asset sales to access.

**Funding shortfall:** max(0, planned payout - actual funded payout), using R1 asset liquidity and cost rules.

**Existing-pool real erosion risk:** path probability of existing pool falling below original endowment's purchasing power at least once (starting-year-dollar convention).

## Identity for each simulated path-year

    begin_total = begin_existing + begin_restricted
    investment_gain_total = investment_gain_existing + investment_gain_restricted
    end_restricted = begin_restricted + restricted_investment_gain + newly_received_gifts
    end_existing = begin_existing + existing_investment_gain + other_changes
                   - actual_payout - other_cash_paid - asset_sale_cost
    end_total = end_existing + end_restricted
    real_end_total = real_end_existing + real_end_restricted

Asset sales convert investments to cash and **must not be deducted again** from endowment wealth; the separately charged transaction costs are included above. Capital calls transfer assets within the existing pool rather than reducing total assets.

## Numerical example (illustrative; $M)

Starting total/endowment eligible: $100; starting restricted gifts: $0; investment gains: $0; new gifts $10; actual payout $5; no transaction cost.

Existing pool ends at **$95**, restricted gifts at **$10**, total assets at **$105**. A graph of total only would misleadingly suggest that the assets supporting distributions had grown.

## Validation status

Run `python test_simple_model.py`; tests cover all six R2 profiles with 100 paths each, accounting reconciliation, gift pooling, and deterministic examples demonstrating total endowment growth despite existing-pool contraction. For UI smoke testing only, a structural Streamlit stub runs the main app; a browser visual check remains necessary.

## Limitation

The legal spendability of the original endowment is assumed, and donor terms and eligible investment income from restricted gifts are not established. Returns and gifts are not cash without further realization/appropriation. Any result is conditional on these simplifying assumptions.
