"""Reproducibility and calibration diagnostics; not claims of predictive validation."""
from dataclasses import replace
import numpy as np
import pandas as pd
from portfolio_return_simulation import fit_mixture, checked_history
from endowment_simulation_model import run_monte_carlo


def calibration_diagnostics(history):
    h = checked_history(history)
    x = h.p4_return.to_numpy()
    m = fit_mixture(x)
    mean, std = x.mean(), x.std(ddof=1)
    def density(mu, sigma):
        return np.exp(-.5*((x-mu)/sigma)**2)/(sigma*np.sqrt(2*np.pi))
    single = density(mean, std)
    mixed = (1-m['adverse_probability'])*density(m['ordinary_mean'], m['ordinary_std']) + m['adverse_probability']*density(m['adverse_mean'], m['adverse_std'])
    ll = [np.log(np.maximum(single, 1e-300)).sum(), np.log(np.maximum(mixed, 1e-300)).sum()]
    table = pd.DataFrame({'Model': ['Single Normal', 'Two-component Normal mixture'],
                          'Parameters': [2, 5], 'Log likelihood': ll})
    table['AIC'] = 2*table.Parameters-2*table['Log likelihood']
    table['BIC'] = np.log(len(x))*table.Parameters-2*table['Log likelihood']
    return table, m


def holdout_diagnostics(history, training_fraction=.7):
    """Chronological density-score holdout. This is return-model validation only."""
    h = checked_history(history)
    cut = int(len(h)*training_fraction)
    if cut < 12 or len(h)-cut < 4:
        raise ValueError('Need at least 12 training and 4 holdout quarters.')
    train, test = h.iloc[:cut], h.iloc[cut:]
    x = test.p4_return.to_numpy()
    m = fit_mixture(train.p4_return.to_numpy())
    def density(mu, std):
        return np.exp(-.5*((x-mu)/std)**2)/(std*np.sqrt(2*np.pi))
    normal = density(train.p4_return.mean(), train.p4_return.std(ddof=1))
    mixture = (1-m['adverse_probability'])*density(m['ordinary_mean'], m['ordinary_std']) + m['adverse_probability']*density(m['adverse_mean'], m['adverse_std'])
    return pd.DataFrame({'Model':['Single Normal','Two-component Normal mixture'],
        'Mean holdout log density (higher is better)': [np.log(np.maximum(normal,1e-300)).mean(),np.log(np.maximum(mixture,1e-300)).mean()],
        'Training start': train.quarter.iloc[0], 'Training end': train.quarter.iloc[-1],
        'Holdout start': test.quarter.iloc[0], 'Holdout end': test.quarter.iloc[-1],
        'Training quarters': len(train), 'Holdout quarters':len(test)})


def stability_check(data, config, institution, liquidity, history=None, seeds=(11,42,93), counts=None):
    counts = counts or (config.n_sims, config.n_sims*2)
    rows=[]
    for n in counts:
        for seed in seeds:
            m=run_monte_carlo(data,replace(config,n_sims=int(n),seed=int(seed)),institution,liquidity,p4_history=history,keep_paths=False)['metrics']
            p=m['probability_at_least_one_shortfall']
            rows.append({'Paths':n,'Seed':seed,'Pr(any funding shortfall)':p,
                'Binomial standard error':np.sqrt(p*(1-p)/n),
                'Median terminal real corpus ($M)':m['median_terminal_real_assets'],
                'Terminal real-corpus ES':m['expected_shortfall_terminal_real_corpus_loss']})
    return pd.DataFrame(rows)
