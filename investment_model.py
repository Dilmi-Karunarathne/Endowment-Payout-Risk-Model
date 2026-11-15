"""Investment frozen forward targets; joint asset/CPI quarterly block simulation.

Simulation implementation: quarterly decisions, 5pp per private sleeve per quarter,
annual institutional flows and rebalancing costs from the Investment handoff.
"""
from pathlib import Path
from functools import lru_cache
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent / 'data' / 'investment'
ASSETS = ['us_large_cap','us_small_cap','developed_ex_us','emerging_markets',
          'inflation_linked_bonds','investment_grade_corporate_bonds',
          'high_yield_fixed_income','treasuries','private_equity','hedge_funds',
          'venture_capital','cash_tbill','commodities']
PRIVATE = np.array([8,9,10])
LIQUID = np.array([i for i in range(13) if i not in PRIVATE])
STRATEGIES = ['PeerCVaR_Dynamic','PeerCVaR_Static','PeerVB_Dynamic','PeerVB_Static','MeanCVaR_Dynamic','MeanCVaR_Static','EqualWeight_Dynamic','EqualWeight_Static','HRP_Dynamic','HRP_Static']
REGIMES = ['Calm','Turbulent']

# Institutional counts public equity, fixed income and cash in its payout coverage ratio.
PAYOUT_LIQUID = (np.isin(ASSETS, [ASSETS[i] for i in LIQUID]) &
                 (np.array(ASSETS) != 'commodities')).astype(float)
RESTRICTED_IN_SEVERE = np.isin(ASSETS, ['emerging_markets', 'high_yield_fixed_income'])

@lru_cache(maxsize=1)
def liquidity_inputs():
    table = pd.read_csv(ROOT / 'liquidity_data_datateam.csv').set_index('asset_id').loc[ASSETS]
    weights = table.Stressed_1m_Weight_h.to_numpy(float)
    normal = table.cost_normal_mid.to_numpy(float, copy=True)
    stressed = table.cost_stressed_mid.to_numpy(float, copy=True)
    for rates in (normal, stressed):
        rates[[ASSETS.index('private_equity'), ASSETS.index('venture_capital')]] = 0.
    if not all(np.isfinite(a).all() and ((a >= 0) & (a <= 1)).all()
               for a in (weights, normal, stressed)):
        raise ValueError('Invalid Investment liquidity weights or costs.')
    return weights, normal, stressed


@lru_cache(maxsize=1)
def crisis_liquidity_weights():
    """Research 1's *crisis-value* g weights, distinct from one-month h weights.

    Optimized portfolios satisfy g-weighted coverage >= 20% at the R1
    rebalance decisions (equivalent to 4 x 5% planned payout). Our simulator
    measures realized g coverage after path shocks and payouts as a diagnostic.
    """
    t=pd.read_csv(ROOT/'liquidity_data_datateam.csv').set_index('asset_id').loc[ASSETS]
    g=t.Crisis_Value_g_Aug_2026.to_numpy(dtype=float)
    if not np.isfinite(g).all() or (g<0).any() or (g>1).any():
        raise ValueError('Invalid Research 1 crisis-value liquidity weights.')
    return g


def regime_name(x):
    return {'Elevated inflation':'High Inflation','Elevated Inflation':'High Inflation'}.get(x,x)

def inputs(strategy='HRP_Dynamic', regime='Calm'):
    if strategy not in STRATEGIES:
        raise ValueError('Unknown Investment strategy: '+strategy)
    forward = pd.read_csv(ROOT/'forward_weights_by_regime.csv')
    # Handoff Version Main: 10 final portfolios (5 rules × Dynamic/Static).
    rows = forward[(forward.Portfolio_ID == strategy) & (forward.Variant == 'Main')]
    if strategy.endswith('_Static'):
        if len(rows) != 1:
            raise ValueError('A static portfolio must have exactly one weight row.')
        targets = pd.DataFrame([rows.iloc[0][ASSETS].astype(float).to_dict()] * 2,
                               index=REGIMES)
    else:
        targets = rows.set_index('Regime').reindex(REGIMES)[ASSETS].astype(float)
    if targets.isna().any().any() or not np.allclose(targets.sum(axis=1), 1, atol=1e-8):
        raise ValueError('Handoff forward weights must include normalized Calm/Turbulent targets.')
    assets = pd.read_csv(ROOT/'asset_monthly_returns_long.csv')
    wide = assets.pivot(index='Month',columns='Asset_ID',values='Return')[ASSETS].sort_index()
    macro = pd.read_csv(ROOT/'macro_and_regimes_monthly.csv').set_index('Month')
    # Regime signal is only known at prior month-end. Market vs economic
    # regimes are separate in the November Research 1 handoff.
    macro['start_economic_regime'] = macro.Economic_Regime_Known_At_Month_End.shift(1)
    macro['start_market_regime'] = macro.Market_Regime_Known_At_Month_End.shift(1)
    wide = wide.loc['2001-01':'2026-08']
    quarter = pd.PeriodIndex(wide.index,freq='M').asfreq('Q')
    rows=[]
    for q in quarter.unique():
        block = wide.loc[quarter == q]
        if len(block) != 3: continue
        m=macro.loc[block.index]
        ret=(1+block).prod()-1
        rows.append(dict(quarter=str(q),condition=m.start_economic_regime.iloc[0],
                         market_regime=m.start_market_regime.iloc[0],
                         cpi_quarter=float((1+m.CPI_Inflation_MoM).prod()-1),**ret.to_dict()))
    joint=pd.DataFrame(rows)
    if (not np.isfinite(joint[ASSETS+['cpi_quarter']]).all().all() or
        not joint.market_regime.isin(REGIMES).all() or joint.condition.isna().any()):
        raise ValueError('Incomplete 2001–2026 asset/CPI/market-regime handoff history.')
    h=pd.read_csv(ROOT/'strategy_quarterly_returns_long.csv')
    h=h[h.Portfolio_ID==strategy].rename(columns={'Quarter':'quarter',
                                                   'Gross_Return':'portfolio_return'})
    h=h.merge(joint[['quarter','condition']],on='quarter',validate='one_to_one')
    monthly=pd.read_csv(ROOT/'strategy_monthly_returns_long.csv')
    monthly=monthly[monthly.Portfolio_ID==strategy].copy()
    monthly['quarter']=pd.PeriodIndex(monthly.Month, freq='M').asfreq('Q').astype(str)
    net=(1+monthly.Net_Return).groupby(monthly.quarter).prod()-1
    h['gross_portfolio_return']=h.portfolio_return
    h['portfolio_return']=h.quarter.map(net)
    h['cpi_quarter']=h.CPI_Inflation
    h['cpi_yoy']=(1+h.cpi_quarter)**4-1
    w=targets.loc[regime_name(regime)].to_numpy(float)
    names=assets.drop_duplicates('Asset_ID').set_index('Asset_ID')
    weights=pd.DataFrame({'asset':ASSETS,'asset_name':names.loc[ASSETS,'Asset_Name'].values,
        'bucket':names.loc[ASSETS,'Category'].values,'weight':w,
        'liquidity_class':['Low' if i in PRIVATE else 'High' for i in range(13)]})
    weights.loc[weights.asset=='cash_tbill','liquidity_class']='Very High'
    return h.reset_index(drop=True),weights,targets,joint

def draw_path(rng,data,cfg):
    history=data.investment_joint
    n=cfg.horizon_years*4
    starts=rng.integers(0,len(history),size=int(np.ceil(n/cfg.block_size_quarters)))
    indexes=np.concatenate([(s+np.arange(cfg.block_size_quarters))%len(history) for s in starts])[:n]
    q=history.iloc[indexes].copy().reset_index(drop=True)
    # Paired draw for stress replacements; no strategy-dependent random consumption.
    uniforms=rng.random(n)
    if cfg.stress_state:
        state=regime_name(cfg.stress_state)
        eligible=history[history.condition==state]
        if eligible.empty: raise ValueError('No Investment observations for '+state)
        for t in range(min(n,cfg.stress_quarters)):
            q.iloc[t]=eligible.iloc[min(int(uniforms[t]*len(eligible)),len(eligible)-1)]
    q['asset_returns']=[v.copy() for v in q[ASSETS].to_numpy(float)]
    q['investment_condition']=q.market_regime
    # Recession or crisis quarters require the dynamic portfolio's Turbulent
    # target. Static portfolios have identical targets in both regimes.
    if cfg.stress_state and cfg.stress_quarters > 0:
        q.loc[:min(n, cfg.stress_quarters)-1, 'investment_condition']='Turbulent'
    q.loc[0,'investment_condition']='Turbulent' if cfg.stress_state and cfg.stress_quarters>0 else data.portfolio_metadata['allocation']
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
    q['targets']=[data.investment_targets.to_dict('index')]*n
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

def feasible_rebalance(holdings, desired, locked, frozen, rates, fee_payers):
    """Plan a *fundable* quarterly trade without redeeming locked investments.

    The unconstrained desired allocation may want to buy more PE/VC/locked HF
    than the portfolio can finance after a drawdown. First cap those purchases,
    then scale the entire resulting trade back until the liquid sleeves can
    cover the exact proportional trading costs. If no trade is affordable,
    carry current holdings forward without creating cash or paying fictitious
    transaction costs. Returns and annual payout funding still proceed normally.

    Returns (post-trade, pre-fee holdings, actual transaction cost, execution
    fraction). The caller deducts the cost from freely saleable fee-payer sleeves.
    """
    h = np.asarray(holdings, float)
    desired = np.asarray(desired, float)
    rates = np.asarray(rates, float)
    total = float(h.sum())
    if total <= 0:
        return h.copy(), 0.0, 0.0
    locked = np.array(sorted(set(locked)), dtype=int)
    frozen = np.array(sorted(set(frozen)), dtype=int)
    movable = np.array([i for i in range(len(h)) if i not in set(locked)], dtype=int)
    payers = np.array(sorted(set(fee_payers)), dtype=int)
    if not set(payers).issubset(set(movable)):
        raise ValueError('Trading fees may only be funded from unlocked liquid holdings.')

    target = desired.copy()
    target[locked] = np.maximum(h[locked], target[locked])
    target[frozen] = h[frozen]
    # Purchases of locked assets must not consume more than the existing
    # *unlocked* wealth. In particular, do not manufacture negative holdings
    # when private assets dominate a distressed portfolio.
    locked_buys = np.maximum(0.0, target[locked] - h[locked])
    available_unlocked = max(0.0, total - float(h[locked].sum()))
    if float(locked_buys.sum()) > available_unlocked:
        target[locked] = h[locked] + locked_buys * (available_unlocked / locked_buys.sum())

    remainder = max(0.0, total - float(target[locked].sum()))
    if movable.size:
        weights = np.maximum(0.0, desired[movable])
        if weights.sum() <= 1e-15:
            # No target weights for movable holdings: preserve their mix.
            weights = np.maximum(0.0, h[movable])
        if weights.sum() > 0:
            target[movable] = remainder * weights / weights.sum()
        else:
            target[movable] = 0.0
            if remainder > 1e-10:
                raise ArithmeticError('Unallocated wealth in quarterly rebalance.')

    if not np.isclose(target.sum(), total, atol=1e-8, rtol=1e-12):
        raise ArithmeticError('Quarterly target holdings do not conserve wealth.')
    delta = target - h
    full_cost = float(np.abs(delta) @ rates)
    liquid_before = float(h[payers].sum())
    liquid_change = float(delta[payers].sum())
    if full_cost <= 0.0:
        fraction = 1.0
    elif full_cost <= liquid_before + liquid_change + 1e-12:
        fraction = 1.0
    elif full_cost - liquid_change > 0:
        fraction = min(1.0, max(0.0, liquid_before / (full_cost - liquid_change)))
        if fraction < 1.0:
            fraction *= (1 - 1e-10)  # deterministic floating-point headroom
    else:
        fraction = 0.0
    post_trade = h + fraction * delta
    fee = fraction * full_cost
    if fee > float(post_trade[payers].sum()) + 1e-9:
        raise ArithmeticError('Constrained rebalance incorrectly exceeded available cash.')
    if (post_trade < -1e-9).any() or (post_trade[locked] < h[locked] - 1e-9).any():
        raise ArithmeticError('Constrained rebalance violated sale restrictions.')
    if frozen.size and not np.allclose(post_trade[frozen], h[frozen], atol=1e-9, rtol=0):
        raise ArithmeticError('Constrained rebalance traded frozen holdings.')
    return post_trade, fee, float(fraction)


def invest_year(holdings, records, share_weights, coverage_weights, stress_costs=False,
                return_total_snapshots=False, restrict_em_hy=False, crisis_observations=None):
    holdings = np.asarray(holdings, float).copy()
    _, normal_rates, stressed_rates = liquidity_inputs()
    returns, coverage_assets, shares, total_snapshots = [], [], [], []
    costs = 0.

    def observe():
        total = holdings.sum()
        if crisis_observations is not None:
            crisis_observations.append(float(holdings @ crisis_liquidity_weights()/total) if total>0 else 0.)
        coverage_assets.append(float(holdings @ coverage_weights))
        shares.append(float(holdings @ share_weights / total) if total > 0 else 0.)
        total_snapshots.append(float(total))

    for record in records:
        state = regime_name(record['investment_condition'])
        total = holdings.sum()
        if not record.get('freeze_rebalance', False):
            targets = record['targets'][state]
            target = rebalance(holdings, [targets[a] for a in ASSETS])
            # Investment sale-time constraints must also apply to *routine rebalancing*.
            # PE takes 12 months and VC is unavailable: a quarterly rebalance
            # cannot silently redeem either to manufacture payout cash.
            # HF is a 3-month redemption normally, but 12 months under stress.
            locked = [ASSETS.index('private_equity'), ASSETS.index('venture_capital')]
            if stress_costs or state == 'Turbulent':
                locked.append(ASSETS.index('hedge_funds'))
            if restrict_em_hy:
                frozen = np.flatnonzero(RESTRICTED_IN_SEVERE).tolist()
                locked.extend(frozen)
            else:
                frozen = []
            rates = stressed_rates if stress_costs or state == 'Turbulent' else normal_rates
            fee_payers = [ASSETS.index('cash_tbill'), ASSETS.index('treasuries')] + [
                i for i in LIQUID if i not in (ASSETS.index('cash_tbill'), ASSETS.index('treasuries'))]
            if restrict_em_hy:
                fee_payers = [i for i in fee_payers if not RESTRICTED_IN_SEVERE[i]]
            target, cost, fraction = feasible_rebalance(
                holdings, target, locked, frozen, rates, fee_payers)
            # The rebalancing plan is already scaled to the cash actually
            # available to pay its transaction costs. No exception and no
            # fictitious cash when a target cannot be reached.
            holdings = target.copy()
            remaining_cost = cost
            for i in fee_payers:
                paid = min(holdings[i], remaining_cost)
                holdings[i] -= paid
                remaining_cost -= paid
                if remaining_cost <= 1e-12:
                    break
            if remaining_cost > 1e-8:
                raise ArithmeticError('Trade-cost accounting did not reconcile.')
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
