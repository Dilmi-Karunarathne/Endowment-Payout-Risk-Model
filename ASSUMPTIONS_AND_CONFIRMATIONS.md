# Endowment model: current assumptions and R1/R2 confirmations

Prepared 3 November 2026. Source version: Endowment-Payout-Risk-Model-ngoc-v6-update.zip. This audit describes the supplied code/data plus the liquidity update, not an independently verified institutional calibration.

## What changed

Liquidity stays active in every analysis. Cash is separated from public securities, hedge funds, and private equity/venture capital for funding. Cash is used first, followed by eligible sales; net proceeds include the selected liquidation discount. Sale limits may leave unpaid obligations. Funded capital calls transfer value to private assets and do not reduce total endowment. Accounting checks prevent double-counting losses.

The Advanced options panel offers 1/3/12 months to raise cash (default 3). Main reserve and fixed-discount controls are removed. Additional reserve is zero for baseline and the two main stresses. The existing optional reserve-policy sensitivity is retained under Strategies. All scenarios use the same matrix instead of silently adding different reserve policies. A short provisional-assumption note and detailed expander retain a clean dashboard.

Portfolio choices, R2 median mapping, return-generation methods and the existing main stress magnitudes are retained from the uploaded version. They are not newly approved by this update. No automatic portfolio switching was introduced.

## 1. Current liquidity assumptions

| Months available | Base discount | Recession discount | Elevated-inflation discount |
|---|---:|---:|---:|
| 1 | 1.00% | 5.00% | 3.00% |
| 3 | 0.50% | 3.00% | 2.00% |
| 12 | 0.25% | 2.00% | 1.00% |

These nine figures are illustrative R3 sensitivity inputs, NOT empirical estimates, R1 approvals, or values published by ESMA/IMF. Their directional pattern represents a test hypothesis: more time lowers execution pressure and stress increases costs. Neither exact levels nor recession-versus-inflation ordering is established. They may materially overstate costs for highly liquid assets or understate costs for restricted holdings. Do not present the resulting probabilities as calibrated forecasts.

Edit `data/liquidity_matrix.csv` to replace them. Values are decimals (0.03 = 3%). Each row also contains public_access, hedge_access and private_access fractions.

| Input | Current setting | Rationale / reasonableness / limitation | Confirmation |
|---|---|---|---|
| Time to cash | 3 months; options 1/3/12 | Professor's proposed sensitivity horizons. Default is a project choice, not a surveyed benchmark. | R1/R2: payout timing and sale feasibility |
| Public securities sale access | 100% at all horizons before stress restrictions | Simplifies listed exposures; can be optimistic for large orders, pooled vehicles, gates, or stressed credit. No market-depth calibration. | R1: instrument vehicles, execution limits, stressed access |
| Hedge fund sale access | 0% at all horizons | Avoids assuming quarterly redemption without terms; conservative and can overstate shortfalls if redemptions are available. SEC supports considering lockups, not a universal zero-access rule. | R1: notice, gates, lockups and withdrawal limits |
| PE/VC sale access | 0% at all horizons | No verified secondary-sale mechanism. Conservative policy exclusion, not a claim they can never be sold. | R1: secondary-market access and discounts |
| Private distributions | No explicit schedule | Material missing cash-flow channel. Capital calls do not substitute for delayed distributions. | R1: distributions, commitments, calls; R2: cash planning |
| Cash balance | Selected R1 cash/T-bill weight initially; persists thereafter | Separates cash from public investments; T-bills treated as a cash proxy. Confirm eligible maturities and access. | R1 |
| Additional reserve | Zero | Simplification, not evidence of no institutional reserve policy. Not the same as zero portfolio cash. | R2 |
| Other annual cash need | $0M by default; editable | Excludes additional endowment-funded obligations pending evidence. It is not an estimate of zero university debt service. | R2 |
| Borrowing | None | No approved credit facility modeled. May overstate shortfalls relative to available credit. | R2 |
| Payment priority | Other cash needs, then calls, then payout | Existing engine convention; affects payout and unpaid-call results. | R2 with R1 |
| Gifts/positive other changes | Added to available cash before annual payout | May overstate access if restricted or received after the deadline. | R2: availability, restrictions and timing |
| Cash/public/HF/PE+VC returns | Common aggregate portfolio return | Retained simplified engine; cash does NOT earn a separately modeled cash yield. Funding-group balances are proxies, not a full asset-level trading model. | R1: approve proxy or supply joint asset return simulation |

## 2. Data received and used

| File | What it supplies | Status / remaining question |
|---|---|---|
| data/six_portfolio_weights.csv | 13 asset IDs and six allocations: Private/Public x Normal/Inflation/Recession | Supplied R1 weights retained. Confirm static full-sample versus dated as-of specifications for forward starting portfolios. Coverage is $101M-$250M, not all endowment sizes. |
| data/asset_monthly_returns.csv | Return observations for construction of selected portfolio histories | Supplied version retained; confirm identity/proxy mapping, native versus backfilled data, total returns/fees/currency, and equivalence to R1 final native sample. |
| data/condition_history.csv | Quarterly condition labels and CPI observations | Existing model source retained; not replaced with R1 monthly actionable signals. Confirm CPI units, release timing and annual aggregation. |
| data/transition_matrix.csv | Quarterly regime-transition probabilities | Existing matrix retained; provenance/estimation window and consistency with R1 signals need confirmation. |
| data/r2_scenarios.csv | Six institutional parameter rows: Private/Public x Low/Base/High | Baseline uses Base. Low/High are marginal percentile sensitivity values, not coherent stress regimes. |
| data/calibration.csv | Legacy summary statistics and other-changes rates | Selected history drives main model fitting. Private other changes remain provisional; public defaults to zero. Legacy summary statistics must not be cited as new portfolio performance. |
| data/liquidity_matrix.csv | Nine horizon/scenario costs plus group access limits | New illustrative configuration; pending calibration. |

R1 historical monthly target allocations are not implemented as dynamic trading. The supplied model already selects one static portfolio per run. The proposed interpretation of R2 Low/Base/High versus R1 economic allocations remains pending R1 confirmation.

## 3. Current R2 Base values (from bundled r2_scenarios.csv)

| Variable | Private | Public | Reasonableness and confirmation |
|---|---:|---:|---|
| Effective annual spending rate | 4.8907% | 4.0503% | Supplied median benchmarks, not mandatory policies; confirm intended spending rule. |
| Required support / operating expenses | 9.7620% | 1.3259% | Supplied cohort ratios; confirm whether fixed through stress. |
| Operating expenses / initial endowment | 0.499737x | 2.784382x | Supplied cohort ratios; public >1 is possible because institutional expenses exceed endowment value. |
| Annual expense growth | 2.7850% | 3.6900% | Supplied historical median assumptions; not forecasts or stress calibrations. |
| Gifts / beginning endowment | 1.6632% | 3.9290% | Supplied rates; unrestricted availability is a separate assumption. |
| Other endowment changes | +0.1997% | 0.0000% | Private provisional derived value; public exclusion pending data. Confirm no double count with gifts/returns. |

The app defaults to $150M starting assets, five years from 2027, 1,000 paths, Single Normal returns, fixed inflation 2.5%, and three-year trailing-average spending. Earlier prior endowment values equal the start unless overridden. These are editable model choices, not all R1/R2-approved benchmarks. The Python configuration class has different technical defaults (5,000 paths and regime bootstrap); record actual exported run settings.

## 4. Main stress assumptions retained

| Test / input | Current value | Status and reasonableness | Owner |
|---|---|---|---|
| Inflation initial shock | Selected portfolio's 2022Q1-Q4 returns and existing CPI | Historical template applied to projection start, not a prediction that 2022 repeats; retrospective static weights. Confirm histories. | R1 |
| Inflation regime window | 16 quarters including replay | Judgmental persistence, not estimated duration. | R1 |
| Extra CPI after replay | +1.4 percentage points for remaining window | Increment above generated CPI, not total inflation. | R1 |
| Post-replay return drag | 0%, zero years | No extra overlay; not proof rates have no further effect. | R1 |
| Expense growth during inflation stress | 4.6% for two annual growth transitions | Replaces baseline growth during window; stress severity not approved. | R2 |
| Downturn initial shock | Selected portfolio's 2008Q1-2009Q2 returns and CPI | Historical market stress template; no independent forward validation. | R1 |
| Downturn recovery drag | -3% multiplicative annual drag, two years after replay | Not simply subtracting 3 percentage points from every annual return. | R1 |
| Gifts during downturn | 88% of normal for two years from start | 12% reduction; not a supplied R2 stress benchmark. | R2 |
| Capital calls | 2% of beginning endowment for three years | Simplified demand proxy; not based on unfunded commitments; transfers cash to private assets. | R1 jointly R2 |
| Restricted sale eligibility | 50% reduction for two years | Provisional broad restriction on eligible noncash holdings; cash itself is not frozen. | R1 |
| Additional reserve / fixed private-sale discount | Zero / replaced by matrix | Removes previous one-year buffer and 30% sale discount from main downturn. Same policy basis as baseline. | R2 / R1 |
| Stress liquidity window | Annual years overlapping stress/recovery, rounded up | Inflation default four years; downturn default 3.5 years rounded to four. Afterward annual regime determines matrix column. Annual approximation needs agreement. | R1/R2 |

Remaining exploratory shock vectors, donor retreat, expense pressure, special draws and combined stresses are retained as hypothetical sensitivity scenarios. Their occurrence probabilities and severity are not empirically calibrated. Verify all values in scenario_stress.py before interpreting them as institutional scenarios. The liquidity squeeze/freeze library cases now use shared matrix costs and zero extra reserve, with 60%/75% sale restrictions respectively; 'freeze' is partial, not complete cessation of public sales.

## 5. Requests to R1

1. Confirm selected static portfolio per institution and the interpretation of Low/Base/High R2 sensitivities; distinguish static full-sample versus dated as-of weights. This update does not resolve the pending mapping decision.
2. Confirm each of 13 asset IDs maps to the correct return series, vehicles and proxies; validate the supplied monthly file and its historical backfills.
3. Confirm quarterly CPI/condition data and transition matrix, or supply a consistent signal/transition replacement with conversion instructions.
4. Supply normal and stressed sale costs by asset/vehicle, time horizon and expected sale size, plus supporting source/date. Aggregate to the simple matrix only after deciding which assets are sold.
5. Supply sale eligibility at 1/3/12 months, redemption notices/gates/lockups, and stressed restrictions. Do not infer tradability from liquid proxy return data.
6. Confirm calls relative to commitments, distribution schedules, secondary sales and cash/T-bill treatment.
7. Confirm inflation/downturn magnitudes, persistence and recovery; approve historical replay methodology for the new portfolios.
8. Confirm equity/rate-shock asset vectors and the portfolio-level common-return proxy; supply joint asset data/methodology if moving to holdings-based returns.

## 6. Requests to R2

1. Confirm Base median inputs, fixed support-ratio assumption and payout timing; clarify any stress-dependent support policy.
2. Confirm stress expense growth/duration and gift reductions/duration; distinguish restricted gifts from payout-available cash.
3. Confirm whether any additional cash reserve is required. State amount or payout-years and whether it is a hard restriction or a target that may be used in stress.
4. Supply endowment-funded annual debt service/other cash need directly, or debt balance, rate and repayment structure. Avoid counting university expenses again as endowment obligations.
5. Confirm payment priority among institutional payout, calls and other cash demands; identify available borrowing and its terms if included.
6. Confirm spending rule and caps/floors. Annual payout-growth limits differ from a spending-rate collar; the existing UI implements the former.
7. Confirm private/public other-changes rates, source and decomposition to avoid double counting gifts or returns.
8. Noninvestment revenue, tuition share, non-tuition growth and enrollment stress remain relevant to a future budget extension. This uploaded version calculates support as expenses x support ratio; it does not model a full tuition/enrollment revenue budget. Missing revenue data cannot be 'filled in' without adding that logic.

## 7. Credible methodological sources

[S1] ESMA, Guidelines on liquidity stress testing in UCITS and AIFs, 16 July 2020, ESMA34-39-897. Sections on asset liquidity and liquidation approaches support considering asset type, liquidation horizon, trade size and stressed conditions. They do NOT prescribe our nine percentages or govern U.S. endowments as such.
https://www.esma.europa.eu/sites/default/files/library/esma34-39-897_guidelines_on_liquidity_stress_testing_in_ucits_and_aifs_en.pdf

[S2] Antoine Bouveret, Liquidity Stress Tests for Investment Funds: A Practical Guide, IMF Working Paper 17/226 (2017). Provides a framework for measuring liquidity resources against stressed funding demands. We adapt the funding logic to payouts; it does not calibrate this endowment's costs.
https://www.imf.org/en/publications/wp/issues/2017/10/31/liquidity-stress-tests-for-investment-funds-a-practical-guide-45332

[S3] SEC Investor.gov, Hedge Funds. Describes redemption restrictions and lockups that may last a year or more. Supports requiring fund terms rather than assuming access after three months; does not establish all hedge funds are inaccessible.
https://www.investor.gov/introduction-investing/investing-basics/investment-products/private-investment-funds/hedge-funds

[S4] Project sources: R1 six portfolio file and methodology previously supplied; current uploaded ZIP files listed above; R2 cohort benchmark delivery previously reviewed. Numeric values here are read from this ZIP. Their underlying datasets/publication claims have not been independently audited in this update. Professor's screenshot supplies the 1/3/12-month framework, not numerical discounts.

## 8. Interpretation and validation

This is a working annual funding-risk model with provisional calibration. It is not a monthly treasury model. All annual gifts and gains precede payout; there are no within-year deadlines, contract-level gates, private distribution schedules, or asset-specific evolving returns. Initial weights affect benchmark returns, but liquidity-group depletion does not feed back into the return distribution. These limitations can materially affect outcomes over long horizons.

Payout-funding risk measures actual payout below planned payout; institutional support gap is a different measure (support requirement minus actual payout). Liquidation costs are additional execution costs on already marked assets, not a second market loss. No liquidation is charged when cash is sufficient.

Tests cover sufficient cash, discount gross-up, constrained sales, full sale restrictions, invalid inputs, horizon lookup, mandatory liquidity, payment priority, funded calls as transfers, balance-sheet reconciliation, stress windows, all six portfolios and every deterministic library scenario. Passing implementation checks does not validate the empirical calibration.

## Bundled file inventory (checked)

| File | Rows | Columns |
|---|---:|---:|
| asset_monthly_returns.csv | 427 | 19 |
| calibration.csv | 9 | 2 |
| condition_history.csv | 137 | 3 |
| liquidity_matrix.csv | 9 | 7 |
| r2_scenarios.csv | 6 | 7 |
| six_portfolio_weights.csv | 13 | 9 |
| transition_matrix.csv | 3 | 4 |
