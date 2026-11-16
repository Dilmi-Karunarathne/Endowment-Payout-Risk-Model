**SUPERSEDED INPUT UNIVERSE:** The results below were produced before the 2026-11-15 Research 1 handoff replaced all portfolios. They are retained for engineering history only and must not be cited as outputs from the new ten portfolios. Current tests are in `validation_updated_r1/` and `UPDATED_R1_HANDOFF_AND_PAYOUT_RISKS.md`.

# Validation of stress-policy comparison release — 15 November 2026

## Executed tests

- Python syntax compilation: `python -m py_compile` on all application modules.
- 32 focused automated tests passed, spanning portfolio cash restrictions, scenario definitions, market-draw matching, previous liquidity calculation checks and the new policy comparison/duration calculations.
- Six additional investment-strategy stress tests passed: Private/Public × HRP/Minimum Variance/Mean-CVaR, severe inflation and downturn conditions (short developer-only path counts).
- Private/Base: **5,000 paths each** for baseline, severe 2008-style downturn with liquidity restrictions, and that exact downturn with a fixed 4% spending rate. **All 75,000 annual path results** (three cases × 5,000 paths × five years) passed wealth-accounting and liquidity hierarchy checks. Duration: approximately 238 seconds in the model-testing runtime.
- Public/Base: a **100-path developer-only** baseline, severe downturn and fixed 3.5% spending counterfactual ran successfully, including asset, payout and liquidity reconciliation. This is a smoke test, **not** a validated 5,000-path Public result.
- Separate small Private and Public high-inflation scenarios with 1.5× cash reserve also completed successfully.

## Fully run Private/Base outputs (HRP, $150M, 2027–2031, fixed seed)

| Statistic | Unchanged baseline | Severe downturn with original spending | Same downturn with 4% spending |
|---|---:|---:|---:|
| Median annualized investment return | 9.40% | 0.68% | 0.63% |
| Probability of any unpaid planned payout | 0.00% | 0.00% | 0.00% |
| Median minimum liquidity buffer | 8.84× | 5.77× | 7.04× |
| Median terminal real total endowment | $181.12M | $115.25M | $119.40M |
| Mean cumulative five-year real payouts | $36.43M | $27.40M | $23.89M |

The 4% policy **does not eliminate** the modeled market shock or create extra returns. Compared with the **unchanged downturn**, it increases the typical minimum liquidity buffer by **1.27×** and median ending real wealth by approximately **$4.15M**, at the cost of approximately **$3.51M less mean cumulative real institutional payouts**. The extra return difference may reflect changed fund weights, costs and payout effects in the simulation; the underlying sampled asset/CPI shock is shared.

These conditional simulations do **not** estimate the chance that a severe crisis occurs. The 0% unpaid payout result in all three HRP cases is not a proof that every real institution will meet its payments; the model still permits liquidation of eligible holdings and does not enforce the 40% liquid-asset policy threshold as a hard spending constraint.

Detailed reproducible inputs: `validation_output_stress_v9/private_hrp_5000_policy_stress_settings.json` and its three scenario-specific assumption CSV files. Detailed full comparison: `validation_output_stress_v9/private_hrp_5000_policy_stress_comparison.csv`. Verification: `validation_output_stress_v9/private_hrp_5000_policy_stress_validation.json`.

## Current limitations / checks still outstanding

- Not all **Public** strategies and stresses have been rerun at 5,000 paths in this release.
- The complete Pytest suite's longer batch-stress tests were not run to completion; targeted and institution/strategy main-stress tests above passed.
- Live Streamlit interface was not rendered in a browser in this environment because Streamlit is not installed locally. Python syntax, engine outputs and core regression tests were checked.
- Reverse-stress breakpoint optimization, automatic threshold-triggered spending policies, private-capital-call arrears and a verified passive 70/30 benchmark remain future extensions, not newly implemented features.
- Full investment-management fees are not deducted. Endowment gifts are held in a separate restricted pool under a conservative *model* assumption. Expense stresses change required university support, not scheduled endowment payouts automatically.
- Any old `validation_output/` files are from before the corrected rebalancing release; use the clearly labeled `validation_output_fixed/` or `validation_output_stress_v9/` where appropriate.
