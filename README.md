# Endowment Payout-Risk Simulation App

This package implements the Research 3 integrated endowment model using:

- R1 P4 quarterly historical returns and liquidity classification
- R1 full-history Normal / Recession / Elevated Inflation transition matrix
- R2 Private/Public $101M-$250M Low/Base/High institutional parameters
- D1/R1 CPI inflation history
- Provisional R3-derived D2 Other Endowment Changes benchmark

## Files

- `endowment_simulation_model.py` — model engine, historical validation, Monte Carlo, stress tests and risk measures.
- `app.py` — Streamlit user interface.
- `data/` — model-ready calibration CSVs derived from the project files.
- `requirements.txt` — Python packages.

## Run locally

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Recommended workflow

1. Open **Historical validation** and verify the 2013-2022 mechanics backtest.
2. Use **Monte Carlo simulation** with `Regime-switching bootstrap` as the main forward-looking method, or `Quarterly block bootstrap` as a simpler empirical baseline.
3. Keep **liquidity constraints OFF** for the validated core model. When turned on, buffer, cash need and forced-sale assumptions are scenario assumptions because R2/D2 have not finalized institution-level liquidity-policy benchmarks.
4. Use **Stress comparison** to compare baseline, recession-start and elevated-inflation-start paths.

## Selected payout-risk measures

- Payout Shortfall Probability / Frequency
- Payout Shortfall Depth
- Expected Shortfall of terminal real-corpus loss

Expected Shortfall is calculated across Monte Carlo terminal real-corpus loss outcomes. In the deterministic validation path, only terminal real-corpus loss is reported.

## Important limitations

- P4 Medium | Normal is the current interim R1 portfolio; R1 is rebuilding portfolios around the seven NACUBO cohorts.
- R1 return observations cover 2007Q1-2023Q2. Regime transitions use the longer 1992Q2-2026Q2 history.
- Recession observations are limited, so recession-tail estimates should be interpreted cautiously.
- Other Endowment Changes for the private benchmark is provisional and R3-derived from raw D2 data.
- Operating revenue / budget-surplus mechanics remain outside the core model until revenue excluding investment income is available.
