# Endowment Payout Risk Lab

Consolidated R1/R2 model, updated 8 November 2026.

Run `pip install -r requirements.txt` then `streamlit run app.py`. Keep all bundled data folders alongside the Python files.

Choose an institution, one of nine R1 portfolio strategies, starting allocation regime, spending policy and horizon. Run analysis for baseline, spending-policy comparison and the two primary stresses. Open Strategies to compare all nine portfolios on identical draws. Advanced diagnostics and additional stresses run on demand.

The main engine uses dynamic quarterly R1 asset allocations and R2 institutional assumptions. Liquidity is measured through constraint breaches, with no liquidation-cost model. Public MeanCVaR provisionally shares Private target weights.

See [R1_UPDATE.md](R1_UPDATE.md) for methodology, sources, limitations and pending confirmations. [R2_UPDATE.md](R2_UPDATE.md) records the preceding R2 update; [MERGE_REVIEW.md](MERGE_REVIEW.md) records the original two-version consolidation. Earlier descriptions of static portfolios and liquidation costs are superseded.

Run tests: `python -m unittest test_r1 test_r2 test_liquidity -v`.

## Interface update
The dashboard now uses a light layout inspired by the supplied Payout Risk Lab reference: compact sidebar, top navigation, risk summary cards, paired charts, 5th–95th and 25th–75th percentile bands, and annual erosion probabilities. Simulate is the main results view; Paths provides detail, Compare covers portfolios/policies, and Stress tests contains primary and exploratory scenarios. Method contains sources and settings.

This is a presentation update. The R1/R2 simulation and stress engine files are unchanged. “Modeled payout” is explicitly conditional on funding availability; liquidity breaches remain separate. Reference-only cohorts, spending policies and recommendation features were not imported into this model.
