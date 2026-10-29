"""Reproduce focused stress-release outputs with the provided assumptions."""
import sys,json
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from endowment_simulation_model import *
from scenario_stress import framework_scenarios,run_stress_suite
out=Path(__file__).resolve().parents[1]/'validation_outputs'
d=load_default_data();c=SimulationConfig(return_method='Single Normal',n_sims=500,annual_inflation=.025)
i=institutional_params_from_data(d);l=liquidity_params_from_data(d)
scenarios=framework_scenarios(i)
table,results=run_stress_suite(d,c,i,l,scenarios)
table.to_csv(out/'main_stress_comparison_500.csv',index=False)
(out/'main_stress_settings.json').write_text(json.dumps({'config':asdict(c),'institution':asdict(i),
    'liquidity':asdict(l),'scenarios':[asdict(s) for s in scenarios]},indent=2))
residual=max(r['annual_results'].accounting_residual.abs().max() for r in results.values())
print('Maximum accounting residual:',residual)
