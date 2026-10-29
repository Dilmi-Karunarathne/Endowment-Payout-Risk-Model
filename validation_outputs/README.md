# Validation run outputs

These are reproducible execution checks, not final strategy recommendations.

- Baseline: Single Normal, 1,000 paths, 10 years, seed 42, fixed inflation 2.5%, P4/R2 Private Base, liquidity restrictions off.
- Maximum absolute baseline roll-forward residual: 2.27e-13 $M.
- Method comparison: 250 paths per generator, shared institutional settings and inflation.
- Policy, stress and mixture-sensitivity checks: 100 paths per case.
- Stability: 200 and 500 paths, seeds 11, 42 and 93. These counts demonstrate the check, not convergence of tail estimates.
- Chronological holdout: 46 training quarters and 20 test quarters. See reported dates. Applies to Normal/mixture return models, not institutional outcomes.
- Historical file is an accounting reconstruction, not an independent performance backtest.

For final research, rerun approved cases at larger path counts and assess variation across seeds. A zero observed funding shortfall is conditional on these settings and is not proof of zero risk. Inputs and underlying empirical sources remain provisional as described in PENDING_INPUTS.md.

Reproduce from the project folder with:

```bash
python scripts/validate_release.py
```
