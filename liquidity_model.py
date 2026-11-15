"""Annual deadline liquidity proxy; matrix values are illustrative, not calibrated."""
from pathlib import Path
import numpy as np
import pandas as pd

SCENARIOS = ("Base", "Recession", "Elevated inflation")

def load_matrix(path=None):
    table = pd.read_csv(path or Path(__file__).parent / "data/liquidity_matrix.csv")
    keys = {(m, s) for m in (1, 3, 12) for s in SCENARIOS}
    if len(table) != 9 or set(zip(table.months, table.scenario)) != keys:
        raise ValueError("Liquidity matrix needs exactly one row for each horizon and scenario.")
    values = table[["discount", "public_access", "hedge_access", "private_access"]].to_numpy(float)
    if not np.isfinite(values).all() or (values < 0).any() or (values[:, 0] >= 1).any() or (values[:, 1:] > 1).any():
        raise ValueError("Invalid matrix discount or sale availability.")
    return tuple((int(r.months), r.scenario, float(r.discount), float(r.public_access),
                  float(r.hedge_access), float(r.private_access)) for r in table.itertuples())

def matrix_row(matrix, months, scenario):
    scenario = {"Normal": "Base", "Elevated Inflation": "Elevated inflation"}.get(scenario, scenario)
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown liquidity scenario: {scenario}")
    for row in matrix:
        if row[:2] == (months, scenario):
            return row[2:]
    raise ValueError("Missing liquidity matrix row.")

def fund_obligations(holdings, need, discount, access, restriction=0.):
    """Cash/public/HF/PE+VC. Sell only the gap; preserve exact balance sheet."""
    h = np.asarray(holdings, dtype=float).copy()
    if len(h) != 4 or not np.isfinite(h).all() or (h < -1e-10).any():
        raise ValueError("Invalid holdings.")
    if not np.isfinite([need,discount,restriction,*access]).all() or need < 0 or not 0 <= discount < 1 or not 0 <= restriction <= 1 or len(access)!=3 or any(not 0<=x<=1 for x in access):
        raise ValueError("Invalid funding inputs.")
    sales = np.zeros(3)
    for i, fraction in enumerate(access, start=1):
        eligible = h[i] * fraction * (1-restriction)
        gross = min(eligible, max(0., need-h[0])/(1-discount))
        h[i] -= gross
        h[0] += gross*(1-discount)
        sales[i-1] = gross
    return h, sales, float(sales.sum()*discount)
