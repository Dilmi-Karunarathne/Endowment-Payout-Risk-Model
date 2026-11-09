"""R1 frozen forward targets; joint asset/CPI quarterly block simulation.

R3 implementation: quarterly decisions, 5pp per private sleeve per quarter,
annual institutional flows. No forward reoptimization or trading-cost forecast.
"""
from pathlib import Path
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

def invest_year(holdings,records):
    holdings=np.asarray(holdings,float).copy()
    returns=[]; liquid=[]; shares=[]
    for record in records:
        targets=record['targets'][regime_name(record['r1_condition'])]
        if not record.get("freeze_rebalance",False):
            holdings=rebalance(holdings,[targets[a] for a in ASSETS])
        total=holdings.sum()
        liquid.append(float(holdings[LIQUID].sum()))
        shares.append(float(holdings[LIQUID].sum()/holdings.sum()) if holdings.sum()>0 else 0.)
        r=np.array(record['asset_returns'])+record.get('return_add',0.)
        if not np.isfinite(r).all() or (r < -1).any():raise ValueError('Asset return below -100%; reduce stress.')
        holdings*=1+r
        returns.append(holdings.sum()/total-1 if total>0 else 0.)
        liquid.append(float(holdings[LIQUID].sum()))
        shares.append(float(holdings[LIQUID].sum()/holdings.sum()) if holdings.sum()>0 else 0.)
    return holdings,returns,liquid,shares

def groups(h):
    return np.array([h[11],h[LIQUID].sum()-h[11],h[9],h[8]+h[10]])
