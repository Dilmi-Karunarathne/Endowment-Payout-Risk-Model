"""Generate a reproducible smoke/stability report, not final research conclusions."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace,asdict
import json
import pandas as pd
from endowment_simulation_model import *
from portfolio_return_simulation import compare_return_methods
from strategy_analysis import compare_cases,policy_cases
from stress_testing import stress_cases,mixture_sensitivity
from validation import calibration_diagnostics,holdout_diagnostics,stability_check

root=Path(__file__).resolve().parents[1]
out=root/'validation_outputs';out.mkdir(exist_ok=True)
d=load_default_data();c=SimulationConfig(return_method='Single Normal',n_sims=1000,annual_inflation=.025)
i=institutional_params_from_data(d);l=liquidity_params_from_data(d)
baseline=run_monte_carlo(d,c,i,l)
pd.DataFrame([baseline['metrics']]).to_csv(out/'baseline_metrics_1000.csv',index=False)
baseline['path_summary'].to_csv(out/'baseline_path_summary_1000.csv',index=False)
small=replace(c,n_sims=100)
methods,_,_,_=compare_return_methods(d,replace(c,n_sims=250),i,l)
methods.to_csv(out/'method_comparison_250.csv')
compare_cases(d,policy_cases(small,i,l)).to_csv(out/'policy_smoke_100.csv',index=False)
compare_cases(d,stress_cases(small,i,l)).to_csv(out/'stress_smoke_100.csv',index=False)
mixture_sensitivity(d,small,i,l).to_csv(out/'mixture_sensitivity_smoke_100.csv',index=False)
calibration_diagnostics(d.p4_quarterly)[0].to_csv(out/'fit_diagnostics.csv',index=False)
holdout_diagnostics(d.p4_quarterly).to_csv(out/'holdout_diagnostics.csv',index=False)
stability_check(d,c,i,l,counts=(200,500)).to_csv(out/'stability_200_500.csv',index=False)
h=historical_validation(d,replace(c,horizon_years=10,start_year=2013),i,l)
h.to_csv(out/'historical_mechanics.csv',index=False)
(out/'run_settings.json').write_text(json.dumps({'config':asdict(c),'institution':asdict(i),'liquidity':asdict(l)},indent=2))
residual=baseline['annual_results'].accounting_residual.abs().max()
(out/'README.md').write_text(f'''# Validation run outputs

These are reproducible execution checks, not final strategy recommendations.

- Baseline: Single Normal, 1,000 paths, 10 years, seed 42, fixed inflation 2.5%, P4/R2 Private Base, liquidity restrictions off.
- Maximum absolute baseline roll-forward residual: {residual:.3g} $M.
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
''')
print('Release validation complete; maximum accounting residual',residual)
