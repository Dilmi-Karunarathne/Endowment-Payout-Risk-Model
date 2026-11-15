# Current November 15 portfolio handoff validation

The Private/Base and Public/Base examples use $150 million opening endowment and
5,000 joint historical asset/CPI paths per institution under the updated
**Hierarchical Risk Parity (Dynamic)** forward targets.

This folder contains **new** results of the November R1 handoff, not the prior
nine-strategy model's historical validation tables. These are conditional model
outputs, not real-world projections and not a validation of all 10 portfolios
at 5,000 paths.

Full result data are reproduced by running Baseline & strategies, selecting
HRP Dynamic, and Private/Base or Public/Base with 5,000 paths. For full
path-year exports use the Streamlit app's Detailed calculations ZIP.

Current standard and severe stress templates were smoke-tested with short
simulation counts. Full 5,000-path runs of every stress/portfolio combination
are not included in this validation folder. A live Streamlit render was not
available in the test container; syntax and Monte Carlo engine checks passed.

Comparison caveat: Investment simulations use R1 asset return data and R3
path-specific trading costs and payout rules. R1's historical `Net_Return`
reference series are *not* charged as a second transaction fee. All return
figures exclude full investment-management and administration fees.
