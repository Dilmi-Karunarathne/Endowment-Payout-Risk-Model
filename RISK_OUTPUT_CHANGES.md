# v4 Payout Risk Outputs — Gift-Restriction Policy

| Metric | Display | Interpretation |
|---|---|---|
| Payout funding shortfall | Negative annual **actual − planned** deviation chart ($M), mean and worst simulated path | How much of the scheduled payout was not funded from **spendable cash + eligible asset sales**. |
| Earnings-only coverage gap (primary) | Year table ($M): mean and conditional mean where gap > 0 | `max(0, planned − investment gain)`; this directly addresses the research question about investment returns below spending needs. Not a cash measure. |
| Earnings + gifts gap (supplementary) | Year table ($M): mean | `max(0, planned − investment gain − total gifts)`; economic diagnostic, **not** eligible liquidity. New gifts are restricted. |
| Frequency of payout shortfall | Headline card (%) | Share of five-year paths with at least one unpaid planned distribution. |
| Real principal erosion | Headline card (%) and real wealth chart ($M) | Share of paths where real total endowment assets, including gift assets, fall below initial real principal at least once. |
| Institutional support gap | Headline probability (%) and conditional gap table ($M) | Share of paths with at least one actual payout below R2's independent support benchmark, and mean size when a gap occurs. |
| Purchasing-power ES (95%) | Headline card, % of initial endowment | Average positive terminal real endowment loss in the worst 5% of simulations; not payout ES. |
| Restricted new-gift asset account | Annual table ($M) and path-year exports | Value of new gift assets and associated investment results prohibited from funding payout. |

No new user inputs or stress-testing features were added. Gift restriction is a fixed, explicitly documented baseline policy in the simplified model. It is **not** inferred from R2.
