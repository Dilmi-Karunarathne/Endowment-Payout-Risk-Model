"""Integrated scenario and one-factor sensitivity runs using the core engine.

All values below are illustrative user-adjustable scenarios, not estimated policies.
"""
from dataclasses import replace
from strategy_analysis import compare_cases
from portfolio_return_simulation import fit_mixture


def stress_cases(config, institution, liquidity, annual_return_shift=-.04,
                 inflation=.06, spending_increase=.01, liquid_haircut=.5, discount=.30):
    return {
        'Baseline': (config, institution, liquidity),
        'Lower returns': (replace(config, annual_return_shift=config.annual_return_shift+annual_return_shift), institution, liquidity),
        'Higher inflation': (replace(config, annual_inflation=inflation), institution, liquidity),
        'Higher spending': (config, replace(institution, effective_spending_rate=min(1., institution.effective_spending_rate+spending_increase)), liquidity),
        'Liquidity restriction': (config, institution, replace(liquidity, enabled=True, liquid_share_haircut=liquid_haircut, forced_sale_discount=discount)),
        'Combined stress': (replace(config, annual_return_shift=config.annual_return_shift+annual_return_shift, annual_inflation=inflation),
                            replace(institution, effective_spending_rate=min(1., institution.effective_spending_rate+spending_increase)),
                            replace(liquidity, enabled=True, liquid_share_haircut=liquid_haircut, forced_sale_discount=discount)),
    }


def mixture_sensitivity(data, config, institution, liquidity, history=None,
                        probabilities=None, severity_shifts=(-.02, 0., .02)):
    h = data.p4_quarterly if history is None else history
    fitted = fit_mixture(h.p4_return.to_numpy())
    p = config.adverse_probability if config.adverse_probability is not None else fitted['adverse_probability']
    mean = config.adverse_mean if config.adverse_mean is not None else fitted['adverse_mean']
    probabilities = probabilities if probabilities is not None else sorted(set([max(0., p-.05), p, min(1., p+.05)]))
    inflation = config.annual_inflation if config.annual_inflation is not None else float(h.cpi_yoy.mean())
    c = replace(config, return_method='Two-component Normal mixture', annual_inflation=inflation, stress_state=None, stress_quarters=0)
    cases = {f'Adverse probability {v:.1%}': (replace(c, adverse_probability=float(v), adverse_mean=mean), institution, liquidity) for v in probabilities}
    cases.update({f'Adverse mean shift {shift:+.1%} quarterly': (replace(c, adverse_probability=p, adverse_mean=mean+shift), institution, liquidity) for shift in severity_shifts})
    return compare_cases(data, cases, history=h)
