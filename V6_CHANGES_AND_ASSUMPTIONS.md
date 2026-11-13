# v6 Cash Reserve and Capital Calls — R1-supported Research Proxies

The previous simplified v5.1 baseline set annual capital calls and protected payout cash reserves to zero. The v6 model replaces those with **portfolio-specific estimates supplied by R1**. There is no stress-tab or additional simulation mode; these are fixed inputs for every normal run.

| Item | Previous | v6 input | Provenance / interpretation |
|---|---|---|---|
| Capital calls | Zero | Portfolio-specific R1 `R3_Calls_Scaled_to_Private_Exposure`, 2027–2029 only | R1 Item 8 (private exposure-scaled scenario proxy), Item 9 duration 3y; R2 institutional commitments unknown |
| Cash reserve | Zero | Portfolio-specific years of current planned payout (HRP 1 year) | R1 Item 12 recommendation; reserve requirement requires R2 confirmation |
| Asset sale times/costs | R1 | Unchanged | R1 asset-level data; 3-month payment deadline |
| Additional market restrictions | Zero | Zero | R1 Item 10 specifically recommends 0% *additional* market restriction in base (asset-level lockups still enforced) |
| Forced-sale discount | R1 asset-specific costs only | Unchanged | Avoid counting two discounts on the same sale |
| Other annual cash needs | Zero | Zero | No separate endowment obligation schedule available |
| Borrowing | None | None | No verified institutional credit line / terms |
| New gift principal | Restricted | Restricted | **R3 conservative assumption**, R2 supplies amount but not restrictions |

**How calls are accounted for:** `Cash -> PE/VC`, not an investment loss; requested and paid calls may differ if liquidity is constrained. The R1 proxy rate is multiplied by beginning **total** endowment wealth, while liquidity is raised from the existing spendable pool. This is a modeling choice: real commitments and subaccount attribution would require additional data. The model reports the requested/paid/unpaid calls for transparency.

**Why risk may still show 0% payout failure:** R1 allocations retain substantial public-market securities eligible for 3-month liquidation. A payout reserve and portfolio calls increase eligible asset sales, but do not necessarily exhaust saleable assets. It is not evidence that actual institution-specific funding risk is zero.

**Important limitation:** The R1 3-year 'base' call proxy was initially intended for a prolonged downturn/liquidity scenario, **not established as ordinary year-by-year capital calls**. We put it in the simple baseline because the project requested using available R1 estimates; the professor may prefer presenting it as a scenario proxy and leaving the pure normal-year baseline without commitments until institutional schedules are available.
