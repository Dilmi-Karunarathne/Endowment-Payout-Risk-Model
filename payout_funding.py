"""R1 asset-level, cash-first annual payout execution.

All amounts are USD millions.  Market gains on securities are *not* automatically
cash: the only cash income represented in the R1 inputs is the return already
credited to the cash/T-bill holding.  No dividends, distributions, borrowing,
or restricted-gift ledger are supplied by R1/R2; these remain explicit limits.

The executor sells only assets whose R1 sale time is no greater than the
configured payout deadline.  Amounts raised are net of R1 asset-specific sale
costs and optional additional forced-sale discount.  Costs are booked once.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from r1_model import ASSETS, RESTRICTED_IN_SEVERE

CASH_INDEX = ASSETS.index('cash_tbill')
PE_INDEX = ASSETS.index('private_equity')
VC_INDEX = ASSETS.index('venture_capital')

@lru_cache(maxsize=1)
def r1_liquidation_table():
    frame = pd.read_csv(Path(__file__).resolve().parent / 'data/r1/liquidity_data_datateam.csv')
    frame = frame.set_index('asset_id').loc[ASSETS]
    for key in ('ttc_normal_m', 'ttc_stressed_m', 'cost_normal_mid', 'cost_stressed_mid'):
        a = frame[key].to_numpy(float)
        if np.isnan(a).any() or (a < 0).any():
            raise ValueError('R1 liquidation input is missing or negative: ' + key)
    return frame

@dataclass
class FundingResult:
    holdings: np.ndarray
    actual_payout: float
    other_paid: float
    capital_paid: float
    gross_sales: float
    sale_cost: float
    sales_by_asset: np.ndarray
    cash_before_sales: float
    funding_capacity: float
    net_eligible_sale_capacity: float
    available_cash_for_payout: float
    capital_unpaid: float
    other_unpaid: float
    reserve_target: float
    reserve_shortfall: float
    accessible_cash_after: float


def execute_r1_cash_first(holdings, *, payout, other_need=0., capital_call=0.,
                          reserve=0., months=3, stressed=False, restriction=0.,
                          restrict_em_hy=False, forced_sale_discount=0.,
                          allow_forced_sales=True):
    """Execute eligible sales cheapest net cost first, then satisfy cash obligations.

    Priority: other endowment obligations, capital calls, planned payout; an
    explicitly requested reserve is protected where feasible.  A capital call
    transfers cash into PE/VC holdings; it is not a corpus loss.  'restriction'
    gates a proportion of non-cash eligible positions (not the cash itself).
    """
    h = np.asarray(holdings, float).copy()
    if h.shape != (len(ASSETS),) or not np.isfinite(h).all() or (h < -1e-8).any():
        raise ValueError('Expected 13 nonnegative finite R1 holdings.')
    if any(not np.isfinite(x) or x < 0 for x in (payout, other_need, capital_call, reserve)):
        raise ValueError('Cash obligations must be finite and nonnegative.')
    if not 0 <= restriction <= 1 or not 0 <= forced_sale_discount < 1 or months not in (1,3,12):
        raise ValueError('Invalid liquidation restrictions, discount or deadline.')
    h = np.maximum(h, 0.)
    table = r1_liquidation_table()
    ttc = table['ttc_stressed_m' if stressed else 'ttc_normal_m'].to_numpy(float)
    rate = table['cost_stressed_mid' if stressed else 'cost_normal_mid'].to_numpy(float)
    extra = forced_sale_discount if allow_forced_sales else 0.
    net_factor = (1-rate)*(1-extra)
    eligible = np.where(ttc <= months, h*(1-restriction), 0.)
    eligible[CASH_INDEX] = 0.
    if restrict_em_hy:
        eligible[RESTRICTED_IN_SEVERE] = 0.

    cash_before = float(h[CASH_INDEX])
    cash_needed = float(payout+other_need+capital_call+reserve)
    max_net_sales = float(eligible @ net_factor)
    # Funding capacity for payout is computed before execution, after prioritized
    # obligations and reserve.  Sales of assets cannot be counted more than once.
    capacity = max(0., cash_before + max_net_sales - reserve - other_need - capital_call)
    sales = np.zeros(len(ASSETS))
    sale_cost = 0.
    remaining = max(0., cash_needed - cash_before)
    # Cheapest eligible liquidation first, respecting asset-specific time to cash.
    for i in sorted(range(len(ASSETS)), key=lambda idx: (-net_factor[idx], idx)):
        if i == CASH_INDEX or remaining <= 1e-12 or eligible[i] <= 0:
            continue
        gross = min(float(eligible[i]), remaining / net_factor[i])
        net = gross*net_factor[i]
        sales[i] = gross
        h[i] -= gross
        h[CASH_INDEX] += net
        sale_cost += gross - net
        remaining -= net

    available = float(h[CASH_INDEX])
    protected = min(reserve, available)
    spendable = max(0., available - protected)
    other_paid = min(other_need, spendable)
    spendable -= other_paid
    capital_paid = min(capital_call, spendable)
    spendable -= capital_paid
    actual = min(payout, spendable)
    spendable -= actual
    total_paid = other_paid + capital_paid + actual
    h[CASH_INDEX] -= total_paid
    # Commitments are a cash-to-private-asset transfer, not a new cash outflow from net worth.
    private_total = h[PE_INDEX] + h[VC_INDEX]
    pe_share = h[PE_INDEX]/private_total if private_total > 0 else .5
    h[PE_INDEX] += capital_paid*pe_share
    h[VC_INDEX] += capital_paid*(1-pe_share)
    h = np.maximum(h, 0.)
    end_cash = float(h[CASH_INDEX])
    return FundingResult(
        h, float(actual), float(other_paid), float(capital_paid),
        float(sales.sum()), float(sale_cost), sales,
        cash_before, float(capacity), float(max_net_sales),
        max(0., cash_before + max_net_sales - other_need - capital_call - reserve),
        float(capital_call-capital_paid), float(other_need-other_paid), float(reserve),
        max(0., reserve-end_cash), end_cash)
