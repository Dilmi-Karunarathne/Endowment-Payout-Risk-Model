"""Stress and what-if analysis on the simplified five-year investment engine.

Scenarios alter asset-level market paths or explicit institutional inputs. Every
case retains the same spending collar, gift ledger and cash-first executor.
"""
from dataclasses import dataclass, field, replace, asdict
from pathlib import Path
from typing import Optional
import json
import numpy as np
import pandas as pd

from investment_model import ASSETS, REGIMES
from endowment_simulation_model import run_monte_carlo, validate_year_overrides
from simple_analysis import (BaselineOptions, HORIZON, START_YEAR, prepare_inputs,
    summarize_results, shared_market_seeds)

DATA = Path(__file__).parent / 'data'
GFC = ('2008Q1', '2008Q2', '2008Q3', '2008Q4', '2009Q1', '2009Q2')
RATES = ('2022Q1', '2022Q2', '2022Q3', '2022Q4')
STRATEGY_LABELS = {
    'PeerCVaR_Dynamic': 'Peer-Tail-Risk Mean-CVaR (dynamic)',
    'PeerCVaR_Static': 'Peer-Tail-Risk Mean-CVaR (static)',
    'PeerVB_Dynamic': 'Peer-Risk Maximum Return (dynamic)',
    'PeerVB_Static': 'Peer-Risk Maximum Return (static)',
    'MeanCVaR_Dynamic': 'Mean-CVaR (dynamic)',
    'MeanCVaR_Static': 'Mean-CVaR (static)',
    'EqualWeight_Dynamic': 'Equal-Weight (1/N) (dynamic)',
    'EqualWeight_Static': 'Equal-Weight (1/N) (static)',
    'HRP_Dynamic': 'Hierarchical Risk Parity (dynamic)',
    'HRP_Static': 'Hierarchical Risk Parity (static)',
}



@dataclass(frozen=True)
class Scenario:
    name: str = 'Baseline'
    category: str = 'Baseline'
    description: str = 'Current institutional and investment assumptions; no added shocks.'
    source: str = 'Simplified model inputs'
    replay_quarters: tuple = ()
    regime: Optional[str] = None
    regime_quarters: int = 0
    asset_shocks: dict = field(default_factory=dict)
    annual_return_shift: float = 0.0
    return_shift_years: int = 0
    inflation_add: float = 0.0
    inflation_years: int = 0
    gift_multiplier: float = 1.0
    gift_years: int = 0
    expense_growth: Optional[float] = None
    expense_years: int = 0
    spending_rate: Optional[float] = None
    spending_years: int = 0
    capital_call_multiplier: float = 1.0
    capital_call_years: Optional[int] = None
    reserve_years: Optional[float] = None
    liquidity_stress_years: int = 0
    freeze_public_years: int = 0
    profile_override: Optional[str] = None
    policy_reference: Optional[str] = None  # Original stressed case used for matched policy comparisons


def validate_scenario(s):
    if not isinstance(s, Scenario) or not s.name.strip():
        raise ValueError('Provide a named scenario.')
    if s.name == 'Baseline' and s != Scenario():
        raise ValueError('Use a different name for a changed scenario.')
    for name, value in asdict(s).items():
        if isinstance(value, (float, int)) and not np.isfinite(value):
            raise ValueError('Scenario numbers must be finite.')
        if name.endswith('_years') and value is not None:
            if name == 'reserve_years':
                if not 0 <= value <= 3:
                    raise ValueError('Cash reserve must be between zero and three annual payouts.')
            elif isinstance(value, bool) or int(value) != value or not 0 <= value <= HORIZON:
                raise ValueError('Scenario durations must be whole years from zero to five.')
    if isinstance(s.regime_quarters, bool) or int(s.regime_quarters) != s.regime_quarters or not 0 <= s.regime_quarters <= HORIZON*4:
        raise ValueError('Regime duration must be 0–20 whole quarters.')
    if s.regime not in (None, 'Normal', 'Recession', 'High Inflation', 'Overlap') or bool(s.regime) != bool(s.regime_quarters):
        raise ValueError('Choose a known market regime and its duration together.')
    if s.replay_quarters and (s.regime or s.asset_shocks):
        raise ValueError('Choose a historical replay, regime stress or asset shock separately.')
    if len(s.replay_quarters) > HORIZON*4:
        raise ValueError('Historical replay exceeds the five-year projection.')
    for a, value in s.asset_shocks.items():
        if a not in ASSETS or not np.isfinite(value) or not -1 < value <= 1:
            raise ValueError('Asset shocks must use known assets and lie above −100% and at most +100%.')
    if not -.2 <= s.annual_return_shift <= .2 or not -.1 <= s.inflation_add <= .2:
        raise ValueError('Return or inflation adjustment is outside the supported range.')
    if not 0 <= s.gift_multiplier <= 3 or not 0 <= s.capital_call_multiplier <= 3:
        raise ValueError('Gift and capital-call multipliers must lie between zero and three.')
    if s.expense_growth is not None and not -.5 <= s.expense_growth <= .5:
        raise ValueError('Expense growth must be between −50% and +50%.')
    if s.spending_rate is not None and not .03 <= s.spending_rate <= .05:
        raise ValueError('Spending rate must stay within the existing 3%–5% policy limits.')
    if s.profile_override not in (None, 'Low', 'Base', 'High'):
        raise ValueError('Unknown institutional profile.')
    if s.policy_reference is not None and (not s.policy_reference.strip() or s.policy_reference == s.name):
        raise ValueError('A policy response needs the name of a distinct reference stress.')
    for value, duration, neutral in [
        (s.annual_return_shift,s.return_shift_years,0),
        (s.inflation_add,s.inflation_years,0),
        (s.gift_multiplier,s.gift_years,1),
        (s.spending_rate,s.spending_years,None),
        (s.expense_growth,s.expense_years,None),
    ]:
        if value != neutral and duration == 0:
            raise ValueError('A changed assumption needs a positive duration.')


def stress_library(institution='Private', severity='Standard'):
    if institution not in ('Private', 'Public') or severity not in ('Standard', 'Severe'):
        raise ValueError('Choose a valid institution and stress severity.')
    table = pd.read_csv(DATA/'institutional_stress.csv')
    row = table.loc[(table.institution_type == institution) & (table.severity == severity)].iloc[0]
    severe = severity == 'Severe'
    growth = float(row.expense_growth)
    gifts = float(row.gift_multiplier)
    gift_years = int(row.gift_years)
    source = '2026-11-15 Research 1 updated stress guidance + existing institutional scenario profile'
    shocks = pd.read_csv(DATA/'investment/market_shocks.csv')
    shock_map = dict(zip(shocks.asset, shocks['severe_shock' if severe else 'standard_shock']))
    scenarios = [
        Scenario('High inflation & elevated rates', 'Main stress',
            'Replay 2022, then apply higher inflation and weaker returns; raise operating-expense growth in year one.',
            source, replay_quarters=RATES, annual_return_shift=-.05 if severe else -.02,
            return_shift_years=5 if severe else 3, inflation_add=.024 if severe else .016,
            inflation_years=5 if severe else 4, expense_growth=growth, expense_years=int(row.expense_years)),
        Scenario('Prolonged downturn & liquidity pressure', 'Main stress',
            'Replay 2008–09, weaken the recovery, reduce gifts and apply stressed sale access. Severe calls are 1.5 times baseline for four years; the protected reserve is retained.',
            source, replay_quarters=GFC, annual_return_shift=-.04 if severe else -.03,
            return_shift_years=3 if severe else 2, gift_multiplier=gifts, gift_years=gift_years,
            capital_call_multiplier=1.5 if severe else 1., capital_call_years=4 if severe else 3,
            liquidity_stress_years=2 if severe else 1, freeze_public_years=2 if severe else 0),
        Scenario('Recession at the start', 'Additional stress',
            'Sample joint asset and inflation observations from recession quarters for the first six quarters; then resume the matched bootstrap.',
            'Existing joint asset/inflation history; supplied recession test design',
            regime='Recession', regime_quarters=6, liquidity_stress_years=2),
        Scenario('Five years of weak returns', 'Additional stress',
            'Reduce each asset’s quarterly return by 1.25 percentage points throughout the five-year projection.',
            'Older-model weak-return assumption, limited to the five-year horizon',
            annual_return_shift=-.05, return_shift_years=5),
        Scenario('Stagflation', 'Additional stress',
            'Five years of weaker returns and higher inflation, with higher expense growth in year one.',
            'Illustrative combination of supplied return, inflation and expense assumptions',
            annual_return_shift=-.04 if severe else -.03, return_shift_years=5,
            inflation_add=.03 if severe else .02, inflation_years=5,
            expense_growth=growth, expense_years=1),
        Scenario('Lower gifts', 'Institutional stress',
            'Apply the supplied institution-specific gift reduction; the original gift rate resumes afterwards.',
            'Supplied institutional stress table', gift_multiplier=gifts, gift_years=gift_years),
        Scenario('Liquidity pressure only', 'Liquidity stress',
            'Isolate stressed sale timing and costs, with strategy-specific calls. Severe cases also freeze emerging-market equity and high-yield sales.',
            source, capital_call_multiplier=1.5 if severe else 1., capital_call_years=4 if severe else 3,
            liquidity_stress_years=2 if severe else 1, freeze_public_years=2 if severe else 0),
        Scenario('Sudden market shock', 'Market stress',
            'Apply the supplied asset-class shock vector once, on top of the first sampled quarter. This compresses a historical drawdown into a hypothetical instant shock.',
            'Supplied joint-window shock table; severe column uses the supplied loss scaling',
            asset_shocks=shock_map, liquidity_stress_years=1),
        Scenario('2008–09 crisis replay', 'Historical replay',
            'Replace the first six quarters with joint asset returns and inflation from 2008Q1–2009Q2.',
            'Existing asset and inflation history', replay_quarters=GFC),
        Scenario('2020 crash & rebound replay', 'Historical replay',
            'Replace the first two quarters with 2020Q1–Q2; retain the subsequent sampled quarters.',
            'Existing asset and inflation history', replay_quarters=('2020Q1','2020Q2')),
        Scenario('2022 inflation & rates replay', 'Historical replay',
            'Replace the first four quarters with the joint asset returns and inflation from 2022.',
            'Existing asset and inflation history', replay_quarters=RATES),
    ]
    return {s.name:s for s in scenarios}


def what_if_library():
    cases = [
        Scenario('Spending rate: 4%', 'What if', 'Use a 4% trailing-average spending rate; retain the 3%–5% collar.', spending_rate=.04, spending_years=5),
        Scenario('Spending rate: 5%', 'What if', 'Use a 5% trailing-average spending rate; retain the 3%–5% collar.', spending_rate=.05, spending_years=5),
        Scenario('No new gifts', 'What if', 'Set new gifts to zero for all five years.', gift_multiplier=0., gift_years=5),
        Scenario('Gifts increase by 25%', 'What if', 'Multiply the institutional gift rate by 1.25; gifts and their returns remain restricted.', gift_multiplier=1.25, gift_years=5),
        Scenario('Half-year cash reserve', 'What if', 'Protect cash equal to half of the current annual planned payout.', reserve_years=.5),
        Scenario('One-and-a-half-year cash reserve', 'What if', 'Protect cash equal to 1.5 times the current annual planned payout.', reserve_years=1.5),
        Scenario('Low institutional profile', 'What if', 'Use the supplied Low profile. This is a bundle of assumptions, not a worst-case forecast.', profile_override='Low'),
        Scenario('High institutional profile', 'What if', 'Use the supplied High profile. This is a bundle of assumptions, not a best-case forecast.', profile_override='High'),
    ]
    return {s.name:replace(s,source='User-selectable sensitivity assumption; existing model policies retained') for s in cases}


def policy_response_library(institution='Private', severity='Severe', stress_name='Prolonged downturn & liquidity pressure'):
    """Compare the SAME adverse investment environment with and without policy.

    Responses are fixed, illustrative governance decisions—NOT automatically
    triggered by the engine. No new historical market or institutional data are
    inferred. Private spending changes from ~4.90% to 4%; Public from ~4.03%
    to 3.5%, preserving the model's existing 3%-5% spending bounds.
    """
    stresses = stress_library(institution, severity)
    if stress_name not in ('High inflation & elevated rates',
                           'Prolonged downturn & liquidity pressure', 'Stagflation'):
        raise ValueError('Choose one of the three supported adverse market conditions.')
    stress = stresses[stress_name]
    rate = 0.04 if institution == 'Private' else 0.035
    experiments = {
        'Lower spending during stress': (
            dict(spending_rate=rate, spending_years=5),
            f'Fix the spending-policy rate at {rate:.1%} for all five years, '
            'while keeping the identical stressed markets, liquidity constraints '
            'and gift assumptions; the 3%-5% annual collar remains active.'),
        'Protect a half-year payout reserve': (
            dict(reserve_years=0.5),
            'Protect half of the planned annual payout as cash, instead of the '
            'portfolio baseline reserve, with every stress assumption unchanged.'),
        'Protect a 1.5-year payout reserve': (
            dict(reserve_years=1.5),
            'Protect 1.5 times the planned annual payout as cash, with every '
            'market stress, capital call and gift assumption unchanged.'),
    }
    return {name: replace(stress,
                          name=f'{stress.name} + {name}',
                          category='Policy response under stress',
                          description=stress.description+' POLICY RESPONSE: '+description,
                          source=stress.source+'; additional illustrative policy sensitivity',
                          policy_reference=stress.name,
                          **overrides)
            for name,(overrides,description) in experiments.items()}


def _longest_true_streak(matrix):
    """Longest consecutive True years for each simulation path."""
    matrix = np.asarray(matrix,dtype=bool)
    if matrix.ndim != 2:
        raise ValueError('Expected paths × years Boolean observations')
    current=np.zeros(matrix.shape[0],dtype=int)
    longest=current.copy()
    for year in range(matrix.shape[1]):
        current=np.where(matrix[:,year],current+1,0)
        longest=np.maximum(longest,current)
    return longest


def funding_duration_diagnostics(annual):
    """Distinguish earnings insufficiency from an actual unpaid distribution."""
    years=sorted(annual.year.unique())
    if len(years) != HORIZON:
        raise ValueError('Duration analysis requires all five projection years.')
    def pivot(name):
        return annual.pivot(index='path_id',columns='year',values=name)[years]
    payout=pivot('payout_shortfall_amount').to_numpy()>1e-10
    earnings=pivot('spendable_earnings_coverage_gap').to_numpy()>1e-10
    unpaid_amount=pivot('payout_shortfall_amount').to_numpy()
    any_payout=payout.any(axis=1)
    first=np.where(any_payout,np.array(years)[payout.argmax(axis=1)],np.nan)
    payout_streak=_longest_true_streak(payout)
    earnings_streak=_longest_true_streak(earnings)
    per_path_total=unpaid_amount.sum(axis=1)
    return {
        'Median first unpaid-payout year, when any':float(np.nanmedian(first)) if any_payout.any() else float('nan'),
        'Probability of 2+ consecutive unpaid-payout years (%)':float(100*np.mean(payout_streak>=2)),
        'Probability of 2+ consecutive earnings gaps (%)':float(100*np.mean(earnings_streak>=2)),
        'Mean total unpaid payout per path ($M)':float(per_path_total.mean()),
        'Mean total unpaid payout when at least one occurs ($M)':float(per_path_total[any_payout].mean()) if any_payout.any() else 0.,
        'Probability of any eligible-earnings gap (%)':float(100*np.mean(earnings.any(axis=1))),
    }


def build_overrides(base, institution, policy, s):
    ov = validate_year_overrides(base, HORIZON)
    def put(column, value, years):
        if years:
            ov.loc[:years-1,column] = value
    put('gift_multiplier',s.gift_multiplier,s.gift_years)
    if s.expense_growth is not None:
        put('expense_growth_add',s.expense_growth-institution.annual_expense_growth,s.expense_years)
    if s.spending_rate is not None:
        put('spending_rate_add',s.spending_rate-institution.effective_spending_rate,s.spending_years)
    if s.capital_call_years is not None:
        ov['capital_call_rate'] = 0.
        put('capital_call_rate',policy['annual_capital_call_rate']*s.capital_call_multiplier,s.capital_call_years)
    else:
        ov['capital_call_rate'] *= s.capital_call_multiplier
    put('liquidity_regime',1.,s.liquidity_stress_years)
    put('restrict_em_hy',1.,s.freeze_public_years)
    return ov


def make_path_transform(data, s):
    """Change asset returns/CPI themselves, never an already-aggregated portfolio twice."""
    replay = None
    if s.replay_quarters:
        joint = data.investment_joint.set_index('quarter')
        missing = set(s.replay_quarters)-set(joint.index)
        if missing:
            raise ValueError('Historical replay quarters unavailable: '+', '.join(sorted(missing)))
        replay = joint.loc[list(s.replay_quarters)]
    n_replay = len(s.replay_quarters)
    if replay is None and not s.asset_shocks and s.annual_return_shift == 0 and s.inflation_add == 0:
        return None
    shock = np.array([s.asset_shocks.get(a,0.) for a in ASSETS])
    weights = data.portfolio_weights.weight.to_numpy()
    def transform(rng, path):
        q = path.copy(deep=True).reset_index(drop=True)
        values = np.stack(q.asset_returns).copy()
        cpi = q.cpi_quarter.to_numpy(copy=True)
        additions = q.return_add.to_numpy(copy=True)
        if replay is not None:
            values[:n_replay] = replay[ASSETS].to_numpy()
            cpi[:n_replay] = replay.cpi_quarter.to_numpy()
            q.loc[:n_replay-1,'quarter'] = list(s.replay_quarters)
            q.loc[:n_replay-1,'condition'] = replay.condition.to_numpy()
            # Preserve the simplified model's fixed initial allocation; subsequent
            # decisions use the historically available regime signals.
            if n_replay > 1:
                q.loc[1:n_replay-1,'investment_condition'] = 'Turbulent' 
            q.loc[:n_replay-1,'investment_condition'] = 'Turbulent'
            additions[:n_replay] = 0.
        if s.asset_shocks:
            q.loc[0,'investment_condition'] = 'Turbulent'
            values[0] = (1+values[0])*(1+shock)-1
        end = min(len(q),n_replay+4*s.return_shift_years)
        additions[n_replay:end] += s.annual_return_shift/4
        end_cpi = min(len(q),n_replay+4*s.inflation_years)
        if end_cpi > n_replay:
            annualized = (1+cpi[n_replay:end_cpi])**4-1+s.inflation_add
            if np.any(annualized <= -1):
                raise ValueError('Inflation adjustment would make the price index nonpositive.')
            cpi[n_replay:end_cpi] = (1+annualized)**.25-1
        if np.any(values+additions[:,None] <= -1) or not np.isfinite(values).all():
            raise ValueError('This return shock exceeds the supported loss range; reduce its severity.')
        q['asset_returns'] = [r.copy() for r in values]
        q['return_add'] = additions
        q['cpi_quarter'] = cpi
        q['cpi_yoy'] = (1+cpi)**4-1
        q['portfolio_return'] = values@weights+additions
        return q
    return transform


def run_scenario(options, scenario, seeds=None, progress=None):
    validate_scenario(scenario)
    o = replace(options,profile=scenario.profile_override) if scenario.profile_override else options
    data, config, institution, liquidity, base, policy = prepare_inputs(o)
    if scenario.regime:
        config = replace(config,stress_state=scenario.regime,stress_quarters=scenario.regime_quarters)
    if scenario.reserve_years is not None:
        liquidity = replace(liquidity,liquidity_buffer_years=scenario.reserve_years)
    overrides = build_overrides(base,institution,policy,scenario)
    results = run_monte_carlo(data,config,institution,liquidity,
        year_overrides=overrides,path_transform=make_path_transform(data,scenario),
        market_path_seeds=shared_market_seeds(o.paths) if seeds is None else seeds,
        progress_callback=progress)
    result = summarize_results(o,results,institution,policy,overrides,liquidity)
    result.update(scenario=scenario,applied_assumptions=assumption_table(o,scenario,overrides,liquidity))
    return result


def assumption_table(o, s, overrides=None, liquidity=None):
    data, config, inst, liq, base, policy = prepare_inputs(o)
    if overrides is None:
        overrides = build_overrides(base,inst,policy,s)
    reserve = s.reserve_years if s.reserve_years is not None else liq.liquidity_buffer_years
    rows = overrides.copy()
    rows.insert(0,'Year',range(START_YEAR,START_YEAR+HORIZON))
    rows['Spending rate (%)'] = (inst.effective_spending_rate+rows.spending_rate_add)*100
    rows['Gift rate (%)'] = inst.gift_rate*rows.gift_multiplier*100
    rows['Expense growth assumption (%)'] = (inst.annual_expense_growth+rows.expense_growth_add)*100
    rows['Capital calls / opening total assets (%)'] = rows.capital_call_rate*100
    rows['Protected reserve (annual payouts)'] = reserve
    rows['Stressed sale conditions'] = rows.liquidity_regime.eq(1)
    rows['Emerging-market & high-yield sales frozen'] = rows.restrict_em_hy.eq(1)
    return rows[['Year','Spending rate (%)','Gift rate (%)','Expense growth assumption (%)',
        'Capital calls / opening total assets (%)','Protected reserve (annual payouts)',
        'Stressed sale conditions','Emerging-market & high-yield sales frozen']]


def comparison_row(r):
    m, a, stats = r['metrics'],r['annual_detail'],r['return_stats']
    terminal = a[a.year == START_YEAR+HORIZON-1]
    return {
        'Median annualized return (%)':100*stats['median_cagr'],
        'Unpaid payout probability (%)':100*m['probability_at_least_one_shortfall'],
        'Average unpaid payout when positive ($M)':m['average_shortfall_amount'],
        'Below 40% liquid-share probability (%)':100*m['probability_investment_liquidity_breach'],
        'Below 20% liquid-share probability (%)':100*m['probability_liquid_share_below_20pct'],
        'Portfolio crisis-value 20% breach probability (%)':100*m['probability_r1_crisis_liquidity_breach_20pct'],
        'Median minimum liquidity buffer (×)':m['median_minimum_liquidity_buffer_x'],
        'Median ending real endowment ($M)':float(terminal.real_ending_assets.median()),
        'Median ending real payout-eligible assets ($M)':float(terminal.real_spendable_assets_end.median()),
        'Purchasing-power expected shortfall 95% (%)':100*m['purchasing_power_expected_shortfall_pct_initial'],
        'Mean cumulative real payouts ($M)':float(a.groupby('path_id').real_actual_payout.sum().mean()),
        'Unpaid capital-call probability (%)':100*float(a.unpaid_capital_call.gt(1e-10).groupby(a.path_id).any().mean()),
        'Institutional support-gap probability (%)':100*m['probability_any_support_gap'],
        **funding_duration_diagnostics(a),
    }


def run_suite(options, scenarios=(), strategies=None, progress=None):
    """Baseline + stress + optional policy responses, paired by path/market shock.

    Policy counterfactuals must follow their underlying stress scenario and
    are compared BOTH with baseline and with that unchanged stress. Different
    strategies and overlays share the same sampled asset/inflation histories.
    """
    scenarios = [Scenario()]+[s for s in scenarios if s.name != 'Baseline']
    if len({s.name for s in scenarios}) != len(scenarios):
        raise ValueError('Scenario names must be unique.')
    for case in scenarios:
        validate_scenario(case)
        if case.policy_reference is not None and case.policy_reference not in {s.name for s in scenarios}:
            raise ValueError('Include the unchanged stress case when testing a policy response.')
    strategies = tuple(strategies or (options.strategy,))
    if not strategies or len(set(strategies)) != len(strategies):
        raise ValueError('Choose distinct investment strategies.')
    seeds = shared_market_seeds(options.paths)
    cases,rows,completed={},[],0
    total=len(strategies)*len(scenarios)
    # Distinct measures with clear units; probability and return differences
    # use percentage points, buffer differences use annual-payout multiples.
    comparison_changes={
        'Change in annualized return (pp)':'Median annualized return (%)',
        'Change in unpaid payout risk (pp)':'Unpaid payout probability (%)',
        'Change in 40% liquid-share breach risk (pp)':'Below 40% liquid-share probability (%)',
        'Change in 20% liquid-share breach risk (pp)':'Below 20% liquid-share probability (%)',
        'Change in minimum liquidity buffer (×)':'Median minimum liquidity buffer (×)',
        'Change in purchasing-power ES 95% (pp)':'Purchasing-power expected shortfall 95% (%)',
        'Change in median real payout-eligible assets ($M)':'Median ending real payout-eligible assets ($M)',
        'Change in median real endowment ($M)':'Median ending real endowment ($M)',
        'Change in mean cumulative real payouts ($M)':'Mean cumulative real payouts ($M)',
        'Change in average unpaid payout when positive ($M)':'Average unpaid payout when positive ($M)',
    }
    for strategy in strategies:
        for scenario in scenarios:
            label=STRATEGY_LABELS[strategy]+' · '+scenario.name
            callback=(lambda done,count:progress((completed+done/count)/total,label)) if progress else None
            r=run_scenario(replace(options,strategy=strategy),scenario,seeds,callback)
            cases[(strategy,scenario.name)]=r
            current=comparison_row(r)
            row={'Strategy':STRATEGY_LABELS[strategy],'Scenario':scenario.name,
                 'Scenario category':scenario.category,'Policy reference':scenario.policy_reference or '',
                 **current}
            baseline=cases[(strategy,'Baseline')]
            bm=comparison_row(baseline)
            for display,field in comparison_changes.items():
                row[display]=current[field]-bm[field]
            baseline_terminal=baseline['annual_detail'].query('year == @START_YEAR + @HORIZON - 1').set_index('path_id').real_ending_assets
            current_terminal=r['annual_detail'].query('year == @START_YEAR + @HORIZON - 1').set_index('path_id').real_ending_assets
            row['Mean paired change in real endowment ($M)']=float((current_terminal-baseline_terminal).mean())
            if scenario.policy_reference:
                reference=cases.get((strategy,scenario.policy_reference))
                if reference is None:
                    raise ValueError('The unchanged reference stress must be evaluated before its policy response.')
                raw=comparison_row(reference)
                for display,field in comparison_changes.items():
                    row['Policy vs same stress: '+display]=current[field]-raw[field]
                ref_terminal=reference['annual_detail'].query('year == @START_YEAR + @HORIZON - 1').set_index('path_id').real_ending_assets
                row['Policy vs same stress: mean paired change in real endowment ($M)']=float((current_terminal-ref_terminal).mean())
            rows.append(row)
            completed+=1
            if progress:progress(completed/total,label)
    return {'options':options,'cases':cases,'comparison':pd.DataFrame(rows),
            'scenarios':scenarios,'strategies':strategies,'seed':42,
            'result_schema_version':next(iter(cases.values()))['result_schema_version']}


def settings_json(suite):
    return json.dumps({'options':asdict(suite['options']), 'seed':suite['seed'],
        'strategies':suite['strategies'],'scenarios':[asdict(s) for s in suite['scenarios']],
        'schema':suite['result_schema_version']},indent=2)
