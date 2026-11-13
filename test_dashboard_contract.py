"""Quick compatibility tests; run python test_dashboard_contract.py."""
import pandas as pd
from dashboard_contract import RESULT_SCHEMA_VERSION, REQUIRED_YEARLY_COLUMNS, REQUIRED_DETAIL_COLUMNS, validate_result_schema
from simple_analysis import BaselineOptions, run_baseline

# Simulate saved v4 result still held in Streamlit session state.
v4_like = {'result_schema_version':'v4', 'yearly':pd.DataFrame({'year':[2027]})}
ok, why=validate_result_schema(v4_like)
assert not ok and 'older simulation' in why

# Simulate partial GitHub update: new stamp, old simulation summary.
partial = {'result_schema_version':RESULT_SCHEMA_VERSION,'yearly':pd.DataFrame({'year':[2027]}), 'annual_detail':pd.DataFrame()}
ok, why=validate_result_schema(partial)
assert not ok and 'mean_total_assets_m' in why

r=run_baseline(BaselineOptions(paths=100))
ok, why=validate_result_schema(r)
assert ok, why
assert REQUIRED_YEARLY_COLUMNS <= set(r['yearly'].columns)
assert REQUIRED_DETAIL_COLUMNS <= set(r['annual_detail'].columns)
assert ((r['yearly']['mean_total_assets_m'] -
         (r['yearly']['mean_spendable_assets_m'] + r['yearly']['mean_restricted_gift_assets_m'])).abs() < 1e-6).all()
print('Dashboard schema compatibility, fresh simulation, and asset-pool reconciliation: PASSED')
