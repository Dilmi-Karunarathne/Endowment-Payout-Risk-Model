"""Fast checks for the simple edition; run: python test_simple_model.py"""
import numpy as np
from simple_analysis import BaselineOptions, run_baseline, HORIZON


def assert_one(institution, profile, paths=3):
    # Bypass only the UI's dropdown restriction, using 100 paths for full test coverage.
    r = run_baseline(BaselineOptions(institution=institution, profile=profile, paths=100))
    assert len(r['annual_detail']) == 100 * HORIZON
    assert len(r['return_by_path']) == 100
    assert len(r['yearly']) == HORIZON
    a = r['annual_detail']
    assert a.accounting_residual.abs().max() < 1e-7
    assert np.allclose(a.planned_payout-a.actual_payout,a.payout_shortfall_amount)
    assert (a.actual_payout <= a.planned_payout + 1e-7).all()
    return r


if __name__ == '__main__':
    for t in ('Private','Public'):
        for p in ('Low','Base','High'):
            x = assert_one(t,p)
            print(f'{t}/{p}: median investment CAGR {x["return_stats"]["median_cagr"]:.2%}, payout shortfall probability {x["metrics"]["probability_at_least_one_shortfall"]:.2%}')
    print('All six R2 profile smoke tests passed.')
