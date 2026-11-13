# v7 update — Restricted gift investment income and Monte Carlo path limits

## Gift investment accounting

The existing v6 ledger already correctly invested opening restricted gift assets in the R1 portfolio return engine; v7 makes that calculation and its timing more explicit in the dashboard and tests. Newly received gifts are added **after** the current year’s market performance and earn investment returns **starting in the following year**. Their return is automatically reinvested inside the restricted pool. Neither gift principal nor any investment gains on the restricted holdings can fund scheduled payouts in the five-year horizon.

**Formula (millions):**

`RestrictedGiftPool_End(t) = RestrictedGiftPool_Begin(t) + RestrictedGiftInvestmentGain(t) + NewGifts(t)`

`RestrictedGiftInvestmentGain(t) = RestrictedGiftPool_Begin(t) × ActualNetGiftPoolReturn(t)`

The net gift-pool return includes the actual R1 asset-level performance and applicable rebalancing costs, and may not equal the aggregate portfolio return. In the model's 2027→2028 example: a 2027 gift of $10M earns no 2027 investment return; if the following year has four quarters of +2%, the gift earns $10M × (1.02⁴ − 1) = $0.8243216M during 2028. The new 2028 gift is added after the 2028 return, not included in that earnings figure.

The annual breakdown table already included **Gift-pool investment gain ($M)**, and now has a prominent explanation of this rule and a formula in the dashboard.

## Simulation paths

The Streamlit selector and user-facing `validate_options` now allow exactly **5,000** or **10,000** paths; default **5,000**. This is a choice between two permitted counts, not a guarantee that more simulations improve economic calibration. Internal unit/smoke tests temporarily bypass the public path-count check to run small deterministic checks quickly; the production app enforces these bounds.

## Otherwise unchanged

R1 block bootstrap, R2 spending rule, cash-first 3-month funding, R1 capital calls/reserves, restricted gifts, and existing payout risk measures are unchanged. The dashboard contract version was updated to reset incompatible saved simulation results on redeployment. Reboot Streamlit Cloud and rerun after replacing files.
