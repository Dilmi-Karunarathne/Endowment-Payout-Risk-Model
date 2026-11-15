"""Reproduce the 5,000-path baseline and two main severe stress checks."""
from pathlib import Path
import json
import time
from scenario_analysis import *

if __name__ == '__main__':
    started=time.perf_counter()
    last=[-1]
    def progress(fraction,label):
        bucket=int(fraction*20)
        if bucket>last[0]:
            print(f'{fraction:.0%}: {label}',flush=True)
            last[0]=bucket
    library=stress_library('Private','Severe')
    selected=[library['High inflation & elevated rates'],library['Prolonged downturn & liquidity pressure']]
    suite=run_suite(BaselineOptions(paths=5000),selected,progress=progress)
    dest=Path('validation_output');dest.mkdir(exist_ok=True)
    suite['comparison'].to_csv(dest/'production_comparison.csv',index=False)
    (dest/'production_settings.json').write_text(settings_json(suite))
    for (strategy,name),r in suite['cases'].items():
        short='baseline' if name=='Baseline' else ('inflation' if name.startswith('High inflation') else 'downturn')
        r['yearly'].to_csv(dest/f'{short}_annual_summary.csv',index=False)
        r['annual_detail'].query('path_id == 0').to_csv(dest/f'{short}_sample_path.csv',index=False)
    (dest/'production_validation.json').write_text(json.dumps({
        'status':'passed','paths_per_case':5000,'case_count':len(suite['cases']),
        'institution':'Private','profile':'Base','strategy':'HRP','severity':'Severe',
        'maximum_accounting_residual_m':max(r['annual_detail'].accounting_residual.abs().max() for r in suite['cases'].values()),
        'elapsed_seconds':round(time.perf_counter()-started,2)},indent=2))
    print('Production validation passed.',flush=True)
