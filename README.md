# Endowment Investment & Payout Sustainability Model — v8

A five-year, reproducible Monte Carlo model for comparing endowment **investment returns**, **university spending reliability**, **liquidity**, and **long-term purchasing power**. Designed for a university dean, project sponsor, investment committee, or anyone outside the research team.

## Run the dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

Choose:

1. **Analysis mode:** Single investment strategy, or Compare three strategies.
2. **Institution:** Private or Public. Both examples start with a $150 million endowment and use the corresponding $101M–$250M cohort assumptions; they are *not* simulations of named universities.
3. **Institutional benchmark profile:** Low, Base, or High. These are marginal percentiles of observed parameters, not coherent joint forecasts.
4. **Investment strategy:** For the single-strategy view, choose one of nine supplied portfolio strategies. Comparison mode runs Hierarchical Risk Parity (HRP), Minimum Variance, and Mean-CVaR.
5. **Starting endowment:** $150M by default. The institutional profiles were estimated for the $101M–$250M size bracket; other amounts extrapolate the profile.
6. **Monte Carlo paths:** 5,000 by default, or 10,000 for numerical stability checks. Comparison mode runs *that many paths per strategy*. Running three portfolios can take several minutes in Streamlit Cloud.

Choose **Run simulation**. For the two institutional examples, run the comparison first under Private/Base and then under Public/Base; the model does not combine their different spending and operating assumptions.

## Six-case comparison implemented in this version

| Institution | Strategy choices | Market inputs |
| --- | --- | --- |
| Private / Base | HRP; Minimum Variance; Mean-CVaR | Shared joint asset/CPI bootstrap paths |
| Public / Base | HRP; Minimum Variance; Mean-CVaR | Shared joint asset/CPI bootstrap paths |

All comparison strategies receive the exact same path-specific historical asset/inflation draws. Strategy-specific holdings, trading, sales, and funding policies still affect their results. Market-path matching uses explicit per-path seeds; it is not dependent on the internal random-number consumption of a strategy.

The **70% global equity / 30% US bond passive benchmark is not included** because matched MSCI ACWI and Bloomberg US Aggregate historical return series have not yet been approved. The model does not invent its returns.

## Model calculation sequence

1. Sample five years (20 quarters) of joint historical asset returns and inflation with four-quarter blocks, shared between strategies.
2. Apply portfolio weights, quarterly rebalancing and supported transaction costs.
3. Calculate the scheduled distribution using the selected institution's three-year average spending policy with 3%–5% constraints.
4. Track an existing payout-eligible investment pool separately from newly donated restricted endowment assets.
5. Raise payout cash from available eligible cash, then only assets saleable within three months, accounting for permitted sales and execution costs. Apply protected reserves and private-fund capital-call proxies.
6. Pay the lesser of the planned distribution and available funding. Record any unpaid amount.
7. Add new gifts *at year-end*: the gifts earn returns in future years but cannot fund payouts in the five-year modeled period under the model's stated conservative assumption.
8. Update both asset pools, discount by simulated inflation, calculate portfolio returns and risk measures, then compare strategies.

### Key definitions

**Investment return:** Compounded portfolio returns *excluding gifts and withdrawals*. Includes modeled rebalancing expenses, but **not all asset-management and administrative fees**.

**Payout-funding shortfall:** `max(0, planned distribution - actual distribution)`. A return below the spending rate is **not** automatically an unpaid distribution.

**Liquidity buffer (×):** `stressed one-month liquidity-weighted payout-eligible assets / annual planned distribution`. The yearly dashboard charts **post-payout** values. The reported **median minimum buffer** uses the minimum of within-year observations on each path, then the median of those path minima.

**Liquid-asset share:** `stressed one-month liquidity-weighted payout-eligible assets / total endowment market value`, with the total including restricted gift investments. We assess this fraction both intra-year at quarterly observations and after annual funding. The 40% and 20% path-level breach probabilities share these exact conventions. Therefore 20% breach probability must never exceed 40% breach probability. At a *constant* 5% payout rate, 40% and 20% liquidity correspond approximately to 8× and 4× annual distributions. The approximation is not an identity when investment values or spending rules vary.

**Cash-funding capacity:** Actual available cash plus proceeds from assets legally/per-policy saleable within **three months**, net of sale costs and competing modeled cash needs and protected reserves. This is **not identical to the one-month liquidity buffer**. The legacy field `payout_liquidity_coverage_ratio` remains a funding-capacity diagnostic and must **not** be relabeled as Joe's liquidity buffer.

**Purchasing-power Expected Shortfall (95%):** Average of the worst 5% of paths' *terminal* real endowment losses from the initial endowment, expressed as a fraction of its starting value; this is **not** the amount of unpaid payouts.

### Funding assumptions

- Asset weights, base/stressed sale costs, redemption eligibility and strategy-specific capital-call proportions come from the portfolio research handoff. These are research proxies, **not observed university cash liabilities**.
- The capital-call proxy applies in the first three years. Transfers into private assets are not portfolio losses.
- The protected cash reserve follows the strategy-specific payout buffer assumptions in the investment research (1.0× planned payout for the three comparison strategies).
- The cohort spending, gift rates and institutional support calculations come from an institutional benchmark guide for US private/public $101M–$250M cohorts.
- Newly received gifts and their investment earnings are separately invested but excluded from payout-eligible assets for five years. This is a *model policy assumption*, not proof every real donor gift is restricted.
- No borrowing, separate private-investment distribution schedule, additional annual university cash demands, or institution-specific donor restrictions are modeled.

## Read results

**Single strategy:** Headline median annualized return, payout risks, both liquidity thresholds, minimum liquidity buffer, real purchasing power and detailed account-level downloads.

**Compare three strategies:** Four sections: investment performance (table/return distributions); payout reliability and liquidity (table/buffer chart); purchasing-power sustainability (table/real endowment chart); model-calculation exports. All comparisons are made within one institution; select Public or Private and run again for the other.

### Caveats

Historical bootstrap paths are scenarios, not predictions; empirical backfills and simulated private holdings may not resemble real private asset liquidity. Market returns can be optimistic relative to university net-of-fees performance. The selected 40%/20% metrics are *monitoring* indicators, not binding payout constraints. The one-month monitoring basis is deliberately distinct from the three-month cash funding rule. No specific university portfolio or fund commitment schedule has been verified.

### File guide (internal filenames preserved for backward compatibility)

| File | Purpose |
| --- | --- |
| `app.py` | Human-readable Streamlit interface and charts |
| `simple_analysis.py` | Single case, comparisons, summary calculations and validation |
| `endowment_simulation_model.py` | Monte Carlo engine, quarterly/annual cash flows, new liquidity metrics |
| `r1_model.py` | Portfolio strategy input adapter and asset-level trading rules |
| `payout_funding.py` | Cash-first funding and sale mechanics |
| `dashboard_contract.py` | Schema checks for saved results and deployment updates |
| `data/r1/` | Historical asset returns, strategy weights and liquidity input research |
| `data/r2_scenarios.csv` | Institutional benchmark profiles |
| `test_simple_model.py` | Accounting, gift, liquidity and strategy comparison tests |

Internal source filenames and data-column identifiers retain legacy research identifiers to avoid corrupting input mappings. **All public-facing dashboard labels are descriptive.** Older technical source notes remain in `SOURCE_NOTES_EARLIER_RELEASE.md`.

## Validation / deployment

```bash
python test_simple_model.py
python test_dashboard_contract.py
```

Replace all project files together in GitHub and reboot the deployed Streamlit app; outdated saved results are invalidated by the v8 schema version. Re-run the model after deployment. This package has been checked programmatically, not visually confirmed on the user's Streamlit Cloud deployment.
