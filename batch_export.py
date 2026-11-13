"""Run all bundled R2 profiles against all R1 strategies and export results."""
from dataclasses import asdict, replace
from io import BytesIO
from math import isfinite

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from endowment_simulation_model import institutional_params_from_data, liquidity_params_from_data, run_monte_carlo
from r1_model import STRATEGIES


METRICS = {
    'Ending real endowment ($M)': ('median_terminal_real_assets', '#,##0.00'),
    'Ending real endowment, P5 ($M)': ('p05_terminal_real_assets', '#,##0.00'),
    'Cumulative real payout ($M)': ('median_cumulative_real_payout', '#,##0.00'),
    'Any institutional support gap': ('probability_any_support_gap', '0.0%'),
    'Earnings-only gap: share of simulated years': ('annual_coverage_shortfall_probability', '0.0%'),
    'Earnings-only gap: conditional mean ($M)': ('conditional_coverage_shortfall_amount', '#,##0.000'),
    'Earnings + gifts gap: mean per year ($M)': ('annual_earnings_gifts_coverage_gap_m', '#,##0.000'),
    'Earnings + gifts gap: share of years': ('probability_annual_earnings_gifts_gap', '0.0%'),
    'Payout liquidity coverage, median worst year (x)': ('median_minimum_payout_liquidity_coverage_ratio', '0.00'),
    'Institutional support gap, conditional ($M)': ('conditional_average_support_gap_m', '#,##0.000'),
    'Mean cumulative asset-sale costs per path ($M)': ('mean_liquidation_cost_m_per_path', '#,##0.000'),
    'Any payout funding shortfall': ('probability_at_least_one_shortfall', '0.0%'),
    'Any real payout cut >5%': ('probability_real_payout_cut', '0.0%'),
    'Median payout volatility': ('median_payout_volatility', '0.0%'),
    'Any real principal erosion': ('probability_real_corpus_erosion', '0.0%'),
    'R1 one-month liquidity breach': ('probability_r1_liquidity_breach', '0.0%'),
    'R2 payout coverage warning': ('probability_r2_coverage_warning', '0.0%'),
    'Median minimum liquid share': ('median_minimum_liquid_share', '0.0%'),
    'Median minimum payout coverage (years)': ('median_minimum_liquidity_coverage', '0.00'),
    'Terminal real loss VaR': ('var_terminal_real_corpus_loss', '0.0%'),
    'Purchasing power ES: loss of initial value': ('purchasing_power_expected_shortfall_pct_initial', '0.0%'),
}


def _format_sheet(sheet, number_formats=()):
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    sheet.row_dimensions[1].height = 35
    for column in sheet.columns:
        head = column[0]
        head.fill = PatternFill('solid', fgColor='1F4169')
        head.font = Font(color='FFFFFF', bold=True)
        head.alignment = Alignment(wrap_text=True, vertical='center')
        width = max(14, min(55, max(len(str(c.value)) for c in column if c.value is not None) + 2))
        sheet.column_dimensions[get_column_letter(head.column)].width = width
    for index, fmt in number_formats:
        for row in range(2, sheet.max_row + 1):
            sheet.cell(row, index).number_format = fmt


def export_profile_grid(config, regime, load_data, progress=None):
    """Use complete R2 profiles and the same market settings for every baseline."""
    config = replace(config, starting_regime=regime, stress_state=None, stress_quarters=0)
    workbook = Workbook()
    results = workbook.active
    results.title = 'Results'
    results.append(['Institution', 'R2 profile', 'R1 strategy', 'Starting regime', *METRICS])
    profiles = workbook.create_sheet('R2 profiles')
    weights = workbook.create_sheet('Starting weights')
    weights.append(['Institution', 'Strategy', 'Starting regime', 'Asset', 'Weight'])
    settings = workbook.create_sheet('Run settings')
    settings.append(['Setting', 'Value'])
    for name, value in asdict(config).items():
        settings.append([name, value])
    settings.append(['Scenario', 'Baseline'])
    settings.append(['Spending rule', 'Three-year moving average with 3%–5% collar'])
    settings.append(['Source', 'Bundled R2 profile rows and November 9 R1 handoff'])
    settings.append(['Money units', 'Millions of starting-year dollars for real outputs'])
    institutions = ('Public', 'Private')
    levels = ('Base', 'Low', 'High')
    profile_inputs = {}
    for institution in institutions:
        data = load_data(institution, regime, STRATEGIES[0])
        for profile in levels:
            inputs = institutional_params_from_data(data, institution, profile)
            if inputs.tuition_discount_rate + config.horizon_years * inputs.tuition_discount_change >= 1:
                raise ValueError(
                    f'{institution} {profile} exceeds a 100% tuition discount at this horizon. '
                    'Shorten the projection horizon and rerun the batch.'
                )
            profile_inputs[institution, profile] = inputs
    for index, inputs in enumerate(profile_inputs.values()):
        values = asdict(inputs)
        if index == 0:
            profiles.append(list(values))
        profiles.append(list(values.values()))

    done = 0
    for institution in institutions:
        for strategy in STRATEGIES:
            data = load_data(institution, regime, strategy)
            liquidity = liquidity_params_from_data(data)
            for asset in data.portfolio_weights.itertuples():
                weights.append([institution, strategy, regime, asset.asset_name, asset.weight])
            for profile in levels:
                inputs = profile_inputs[institution, profile]
                outcome = run_monte_carlo(data, config, inputs, liquidity, keep_paths=False)['metrics']
                results.append([institution, profile, strategy, regime, *[
                    outcome[key] if isfinite(outcome[key]) else None for key, _ in METRICS.values()
                ]])
                done += 1
                if progress:
                    progress(done, 54)
    _format_sheet(results, [(i, fmt) for i, (_, fmt) in enumerate(METRICS.values(), 5)])
    _format_sheet(profiles)
    _format_sheet(weights, [(5, '0.00%')])
    _format_sheet(settings)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
