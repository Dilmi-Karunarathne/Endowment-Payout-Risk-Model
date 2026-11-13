"""Result-schema contract between the simulation and Streamlit dashboard.

This catches old session_state results and mixed GitHub deployments before charts
try to access fields introduced by the asset-pool breakdown release.
"""

from collections.abc import Mapping
import pandas as pd

RESULT_SCHEMA_VERSION = "v5.1-asset-pools"

# Keep these in sync with the yearly fields consumed by app.py.
REQUIRED_YEARLY_COLUMNS = frozenset({
    'year', 'mean_shortfall_deviation_m', 'worst_shortfall_deviation_m',
    'real_endowment_p10_m', 'real_endowment_p90_m', 'median_real_endowment_m',
    'mean_total_assets_m', 'mean_spendable_assets_m',
    'mean_restricted_gift_assets_m', 'mean_real_total_assets_m',
    'mean_real_spendable_assets_m', 'mean_real_restricted_gift_assets_m',
    'mean_spendable_investment_gain_m', 'mean_restricted_gift_investment_gain_m',
    'mean_gifts_m', 'mean_actual_payout_m', 'mean_net_asset_sales_m',
    'mean_asset_sale_cost_m', 'mean_spendable_earnings_gap_m',
    'mean_spendable_earnings_gap_when_positive_m', 'mean_earnings_only_gap_m',
    'mean_earnings_gifts_gap_m', 'mean_support_gap_when_positive_m',
    'mean_investment_return', 'mean_planned_payout_m',
    'mean_unpaid_payout_m',
})

REQUIRED_DETAIL_COLUMNS = frozenset({
    'year', 'earnings_gifts_coverage_gap', 'return_coverage_shortfall_amount',
    'spendable_earnings_coverage_gap', 'payout_support_gap',
    'restricted_gift_assets_end',
})


def validate_result_schema(result):
    """Return (is_valid, actionable_message) without raising a KeyError."""
    if not isinstance(result, Mapping):
        return False, 'The saved simulation result is not a valid model output.'
    if result.get('result_schema_version') != RESULT_SCHEMA_VERSION:
        return False, (
            'An older simulation result is still in this browser session. '
            'Click **Run simulation** again after the latest app files are deployed.'
        )
    yearly = result.get('yearly')
    if not isinstance(yearly, pd.DataFrame) or yearly.empty:
        return False, 'The yearly results are missing. Please run the simulation again.'
    missing_y = sorted(REQUIRED_YEARLY_COLUMNS.difference(yearly.columns))
    if missing_y:
        return False, (
            'The deployed simulation code and dashboard are from different versions. '
            f'Missing yearly columns: {", ".join(missing_y)}. '
            'Update **app.py**, **simple_analysis.py**, and **dashboard_contract.py** '
            'together from the corrected package, redeploy, and rerun the simulation.'
        )
    detail = result.get('annual_detail')
    if not isinstance(detail, pd.DataFrame):
        return False, 'Path-year detail is missing. Please run the simulation again.'
    missing_d = sorted(REQUIRED_DETAIL_COLUMNS.difference(detail.columns))
    if missing_d:
        return False, (
            'Path-year data are from an incompatible model version. '
            f'Missing columns: {", ".join(missing_d)}. '
            'Redeploy the corrected project and rerun.'
        )
    return True, ''
