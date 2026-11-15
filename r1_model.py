"""R1 frozen forward targets; joint asset/CPI quarterly block simulation.

R3 implementation: quarterly decisions, 5pp per private sleeve per quarter,
annual institutional flows and rebalancing costs from the R1 handoff.
"""
from pathlib import Path
from functools import lru_cache
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent / 'data' / 'r1'
ASSETS = ['us_large_cap','us_small_cap','developed_ex_us','emerging_markets',
          'inflation_linked_bonds','investment_grade_corporate_bonds',
          'high_yield_fixed_income','treasuries','private_equity','hedge_funds',
          'venture_capital','cash_tbill','commodities']
PRIVATE = np.array([8,9,10])
LIQUID = np.array([i for i in range(13) if i not in PRIVATE])
STRATEGIES = ['EqualBucket','MinVar','MaxSharpe','MaxDiv','ERC','HRP','MeanCVaR','MinCDaR','BlackLitterman']
REGIMES = ['Normal','Recession','High Inflation','Overlap']

# R2 counts public equity, fixed income and cash in its payout coverage ratio.
PAYOUT_LIQUID = (np.isin(ASSETS, [ASSETS[i] for i in LIQUID]) &
                 (np.array(ASSETS) != 'commodities')).astype(float)
RESTRICTED_IN_SEVERE = np.isin(ASSETS, ['emerging_markets', 'high_yield_fixed_income'])

@lru_cache(maxsize=1)
def liquidity_inputs():
    table = pd.read_csv(ROOT / 'liquidity_data_datateam.csv').set_index('asset_id').loc[ASSETS]
    weights = table.Stressed_1m_Liquidity_Weight_h.to_numpy(float)
    normal = table.cost_normal_mid.to_numpy(float, copy=True)
    stressed = table.cost_stressed_mid.to_numpy(float, copy=True)
    for rates in (normal, stressed):
        rates[[ASSETS.index('private_equity'), ASSETS.index('venture_capital')]] = 0.
    if not all(np.isfinite(a).all() and ((a >= 0) & (a <= 1)).all()
               for a in (weights, normal, stressed)):
        raise ValueError('Invalid R1 liquidity weights or costs.')
    return weights, normal, stressed


def regime_name(x):
    return {'Elevated inflation':'High Inflation','Elevated Inflation':'High Inflation'}.get(x,x)

def inputs(strategy='HRP', regime='High Inflation'):
    if strategy not in STRATEGIES:
        raise ValueError('Unknown R1 strategy: '+strategy)
    forward = pd.read_csv(ROOT/'forward_weights_by_regime.csv')
    # User-authorized provisional sharing: Private MeanCVaR targets for both cohorts.
    target_id = 'MeanCVaR@Private' if strategy == 'MeanCVaR' else strategy
    targets = forward[forward.Strategy_ID == target_id].set_index('Regime')[ASSETS]
    if set(targets.index) != set(REGIMES) or not np.allclose(targets.sum(axis=1),1):
        raise ValueError('R1 forward targets must contain four normalized regimes.')
    assets = pd.read_csv(ROOT/'asset_monthly_returns_long.csv')
    wide = assets.pivot(index='Month',columns='Asset_ID',values='Return')[ASSETS].sort_index()
    macro = pd.read_csv(ROOT/'macro_and_regimes_monthly.csv').set_index('Month')
    # End-month signal is available for the NEXT month only.
    macro['start_regime'] = macro.Regime_Known_At_Month_End.shift(1)
    wide = wide.loc['2001-01':]
    quarter = pd.PeriodIndex(wide.index,freq='M').asfreq('Q')
    rows=[]
    for q in quarter.unique():
        block=wide.loc[quarter==q]
        if len(block)!=3: continue
        m=macro.loc[block.index]
        ret=(1+block).prod()-1
        rows.append(dict(quarter=str(q),condition=m.start_regime.iloc[0],
            cpi_quarter=float((1+m.CPI_Inflation_MoM).prod()-1),**ret.to_dict()))
    joint=pd.DataFrame(rows)
    if not np.isfinite(joint[ASSETS+['cpi_quarter']]).all().all() or not joint.condition.isin(REGIMES).all():
        raise ValueError('Incomplete R1 asset/macro history.')
    h=pd.read_csv(ROOT/'strategy_quarterly_returns_long.csv')
    h=h[h.Strategy_ID==strategy].rename(columns={'Quarter':'quarter','Gross_Return':'portfolio_return'})
    h=h.merge(joint[['quarter','condition']],on='quarter',validate='one_to_one')
    monthly = pd.read_csv(ROOT/'strategy_monthly_returns_long.csv')
    monthly = monthly[monthly.Strategy_ID == strategy].copy()
    monthly['quarter'] = pd.PeriodIndex(monthly.Month, freq='M').asfreq('Q').astype(str)
    net = (1 + monthly.Net_Return).groupby(monthly.quarter).prod() - 1
    h['gross_portfolio_return'] = h.portfolio_return
    h['portfolio_return'] = h.quarter.map(net)
    h['cpi_quarter']=h.CPI_Inflation
    h['cpi_yoy']=(1+h.cpi_quarter)**4-1  # annualized quarterly index change, not reported CPI YoY
    w=targets.loc[regime_name(regime)].to_numpy(float)
    names=assets.drop_duplicates('Asset_ID').set_index('Asset_ID')
    weights=pd.DataFrame({'asset':ASSETS,'asset_name':names.loc[ASSETS,'Asset_Name'].values,
        'bucket':names.loc[ASSETS,'Category'].values,'weight':w,
        'liquidity_class':['Low' if i in PRIVATE else 'High' for i in range(13)]})
    weights.loc[weights.asset=='cash_tbill','liquidity_class']='Very High'
    return h.reset_index(drop=True),weights,targets,joint

def draw_path(rng,data,cfg):
    history=data.r1_joint
    n=cfg.horizon_years*4
    starts=rng.integers(0,len(history),size=int(np.ceil(n/cfg.block_size_quarters)))
    indexes=np.concatenate([(s+np.arange(cfg.block_size_quarters))%len(history) for s in starts])[:n]
    q=history.iloc[indexes].copy().reset_index(drop=True)
    # Paired draw for stress replacements; no strategy-dependent random consumption.
    uniforms=rng.random(n)
    if cfg.stress_state:
        state=regime_name(cfg.stress_state)
        eligible=history[history.condition==state]
        if eligible.empty: raise ValueError('No R1 observations for '+state)
        for t in range(min(n,cfg.stress_quarters)):
            q.iloc[t]=eligible.iloc[min(int(uniforms[t]*len(eligible)),len(eligible)-1)]
    q['asset_returns']=[v.copy() for v in q[ASSETS].to_numpy(float)]
    q['r1_condition']=q.condition
    q.loc[0,'r1_condition']=regime_name(cfg.stress_state) if cfg.stress_state and cfg.stress_quarters>0 else data.portfolio_metadata['allocation']
    q['freeze_rebalance']=False
    q.loc[0,'freeze_rebalance']=not (cfg.stress_state and cfg.stress_quarters>0)
    q['cpi_yoy']=(1+q.cpi_quarter)**4-1
    if cfg.annual_inflation is not None:
        q['cpi_quarter']=(1+cfg.annual_inflation)**.25-1
        q['cpi_yoy']=cfg.annual_inflation
    q['return_add']=cfg.annual_return_shift/4
    if cfg.volatility_multiplier != 1:
        center=history[ASSETS].mean().to_numpy()
        q['asset_returns']=[center+cfg.volatility_multiplier*(r-center) for r in q.asset_returns]
    q['targets']=[data.r1_targets.to_dict('index')]*n
    q['portfolio_return']=[float(data.portfolio_weights.weight.to_numpy()@r)+cfg.annual_return_shift/4 for r in q.asset_returns]
    return q

def rebalance(holdings,target):
    total=holdings.sum()
    if total<=0:return holdings.copy()
    w=holdings/total
    new=np.asarray(target,float).copy()
    new[PRIVATE]=np.clip(new[PRIVATE],np.maximum(0,w[PRIVATE]-.05),w[PRIVATE]+.05)
    remaining=1-new[PRIVATE].sum()
    new[LIQUID]*=remaining/new[LIQUID].sum()
    return new*total

def invest_year(holdings, records, share_weights, coverage_weights, stress_costs=False, return_total_snapshots=False):
    holdings = np.asarray(holdings, float).copy()
    _, normal_rates, stressed_rates = liquidity_inputs()
    returns, coverage_assets, shares, total_snapshots = [], [], [], []
    costs = 0.

    def observe():
        total = holdings.sum()
        coverage_assets.append(float(holdings @ coverage_weights))
        shares.append(float(holdings @ share_weights / total) if total > 0 else 0.)
        total_snapshots.append(float(total))

    for record in records:
        state = regime_name(record['r1_condition'])
        total = holdings.sum()
        if not record.get('freeze_rebalance', False):
            targets = record['targets'][state]
            target = rebalance(holdings, [targets[a] for a in ASSETS])
            # R1 sale-time constraints must also apply to *routine rebalancing*.
            # PE takes 12 months and VC is unavailable: a quarterly rebalance
            # cannot silently redeem either to manufacture payout cash.
            # HF is a 3-month redemption normally, but 12 months under stress.
            locked = [ASSETS.index('private_equity'), ASSETS.index('venture_capital')]
            if stress_costs or state in ('Recession', 'Overlap'):
                locked.append(ASSETS.index('hedge_funds'))
            target[locked] = np.maximum(target[locked], holdings[locked])
            # Reallocate the remaining value across unlocked sleeves.  No
            # creation/destruction of wealth from changing target weights.
            movable = np.array([i for i in range(len(ASSETS)) if i not in locked])
            remaining = max(0., total-target[locked].sum())
            if target[movable].sum() > 0:
                target[movable] *= remaining / target[movable].sum()
            elif remaining > 1e-8:
                target[ASSETS.index('cash_tbill')] += remaining
            rates = stressed_rates if stress_costs or state in ('Recession', 'Overlap') else normal_rates
            cost = float(np.abs(target - holdings) @ rates)
            # Trading costs are paid from the movable/liquid sleeve; scaling
            # the entire target pro rata would silently redeem locked PE/VC.
            holdings = target.copy()
            remaining_cost = cost
            fee_payers = [ASSETS.index('cash_tbill'), ASSETS.index('treasuries')] + [
                i for i in LIQUID if i not in (ASSETS.index('cash_tbill'), ASSETS.index('treasuries'))]
            for i in fee_payers:
                paid = min(holdings[i], remaining_cost)
                holdings[i] -= paid
                remaining_cost -= paid
                if remaining_cost <= 1e-12:
                    break
            if remaining_cost > 1e-9:
                raise ValueError('Insufficient liquid holdings to fund quarterly rebalancing costs.')
            costs += cost
        observe()
        r = np.array(record['asset_returns']) + record.get('return_add', 0.)
        if not np.isfinite(r).all() or (r < -1).any():
            raise ValueError('Asset return below -100%; reduce stress.')
        holdings *= 1 + r
        returns.append(holdings.sum() / total - 1 if total > 0 else 0.)
        observe()
    result = (holdings, returns, coverage_assets, shares, costs)
    return (*result, total_snapshots) if return_total_snapshots else result


def groups(h):
    return np.array([h[11],h[LIQUID].sum()-h[11],h[9],h[8]+h[10]])
