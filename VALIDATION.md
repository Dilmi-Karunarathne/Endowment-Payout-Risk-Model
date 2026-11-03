# Validation — 3 November 2026

- 11 unittest cases passed. Includes six portfolio combinations, both main stress scenarios and all deterministic scenario-library entries.
- Funding checks: sufficient cash, discounted-sale gross-up, limited sale capacity, frozen sales, zero discount, invalid parameters, required liquidity, time lookup, priority, capital-call transfer and accounting reconciliation.
- Streamlit AppTest: initial render; complete Run analysis with 100 paths and two-year horizon; all seven dashboard jobs completed without app errors; overview, stress, data, strategies, checks and return-model pages rendered successfully.
- Original six input CSVs verified byte-for-byte unchanged. New liquidity_matrix.csv added separately.
- Python compilation passed. No live deployment performed.

These checks establish software behavior for tested cases, not empirical calibration or forecasting reliability. No browser screenshot/visual pixel review was performed.

Run engine tests: `python -m unittest -v test_liquidity`
