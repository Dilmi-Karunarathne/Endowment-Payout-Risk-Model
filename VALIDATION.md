**SUPERSEDED INPUT UNIVERSE:** The results below were produced before the 2026-11-15 Research 1 handoff replaced all portfolios. They are retained for engineering history only and must not be cited as outputs from the new ten portfolios. Current tests are in `validation_updated_r1/` and `UPDATED_R1_HANDOFF_AND_PAYOUT_RISKS.md`.

**Current 15 Nov correction:** Read `VALIDATION_FIX_2026-11-15.md` first.
The report below is from the user-provided archive **before the quarterly
rebalancing fix**, and its numerical outputs are superseded where the corrected
code was rerun.

---

# Validation report — final simplified model

Validated on 15 November 2026 with Python 3.12 and the exact dependency versions
listed in `requirements.txt`.

## Completed

| Check | Coverage | Outcome |
|---|---|---|
| Financial and dashboard tests | 46 automated cases | Passed |
| Existing result-schema check | Current schema and stale-result rejection | Passed |
| Baseline parity | Private and Public, three main strategies, five identical seeded paths per case | Exact equality for balances, returns, gifts, payouts, calls and reserves |
| Institutional profiles | All six Private/Public × Low/Base/High profiles | Passed |
| Strategy stress tests | All nine strategies, both institution types, baseline and two main severe tests, eight paths per case | Passed |
| Preset coverage | Every standard/severe stress preset and every what-if preset, smaller runs | Passed |
| Production Monte Carlo | Private/Base/HRP; baseline, severe inflation and severe downturn; 5,000 paths each | Passed |
| Dashboard interaction | Navigation, comparison, custom case, charts, table rendering, downloads and stale-settings handling | Passed using Streamlit's application test runner |
| Terminology audit | Application, source modules, datasets, exports and documentation | No internal research-team codes remain |

The financial checks cover asset-pool roll-forwards, gift timing and restrictions,
capital-call wealth conservation, payout funding, nested liquidity thresholds,
exact historical replay data, overlay durations, shared paths, neutral scenarios,
expense-stress timing, and restrictions on selling frozen assets through
quarterly rebalancing. Invalid scenario inputs are rejected.

The production check produced a maximum absolute accounting residual below
0.000000001 million dollars, well within floating-point tolerance. Exact
production parameters, summary results and one path per case are supplied in
`validation_output/`.

The small matched-seed baseline comparison confirms preservation of the original
financial engine. The default standalone sampling now uses the same per-path
seeds as comparison runs, so it need not reproduce a previous standalone run
that used a different sequence of random draws.

## Limits of verification

Full 5,000-path validation was run for the three production cases listed above,
not every strategy, profile and custom combination. A 10,000-path convergence
study was not run. Small automated runs test all available strategies and presets.

Live server startup succeeded. Visual browser review could not be completed:
the available browser could not reach the local development server, and local
browser launch was restricted. Dashboard interaction and result-rendering tests
passed, but a final visual check after deployment is still appropriate.

No hosted application or external repository was modified. This ZIP is the
complete replacement application package.

## Reproduce

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q test_scenarios.py test_app.py
python test_dashboard_contract.py
python validate_production.py
```

Scenario probabilities are conditional on the supplied shocks and model
assumptions. These tests validate implementation consistency, not the empirical
accuracy of future-return, gift or liquidity assumptions.
