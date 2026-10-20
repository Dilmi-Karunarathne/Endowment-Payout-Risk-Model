# Endowment Payout Risk Model — Streamlit App

A Streamlit interface for the Research 3 endowment payout-risk model. The app runs an annual endowment framework with deterministic analysis, Monte Carlo simulation, D2 institutional-budget calibration, and structured stress scenarios.

## Version note

This repository package corresponds to the **V3 structured-stress Python/Streamlit model** (`app_annual_hybrid_v3_stress.py` + `endowment_model_annual_hybrid_v3_stress.py`). It uses the D1/D2 upload workflow. The later October 19 R1 nine-portfolio integration currently exists in the Excel model and is **not yet incorporated into these Python files**.

## Files

- `app_annual_hybrid_v3_stress.py` — Streamlit user interface
- `endowment_model_annual_hybrid_v3_stress.py` — model calculations
- `requirements.txt` — Python packages installed by Streamlit Community Cloud
- `.gitignore` — prevents local environments and source data files from being committed accidentally

## Data required when running the app

The app currently asks the user to upload these workbooks through the browser:

1. D1 Asset & Economic Data
2. D2 IPEDS Data
3. D2 NACUBO Historical Data
4. D2 Tuition Dependence
5. D2 Net Tuition & Fees
6. D2 Tuition
7. D2 Total Expenses
8. D2 Spending Distribution

The source datasets do **not** need to be committed to GitHub if users will upload them at runtime.

## Run locally

Open PowerShell in the folder containing the files.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app_annual_hybrid_v3_stress.py
```

If PowerShell blocks activation, either adjust the local execution policy as appropriate for your environment or run the virtual-environment Python directly:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m streamlit run app_annual_hybrid_v3_stress.py
```

## Deploy with Streamlit Community Cloud

### 1. Create a GitHub repository

Create a new GitHub repository, preferably private while the project is still under development.

### 2. Upload these repository files

Upload:

- `app_annual_hybrid_v3_stress.py`
- `endowment_model_annual_hybrid_v3_stress.py`
- `requirements.txt`
- `README.md`
- `.gitignore`

Do not upload confidential or restricted project datasets unless your team has permission to store them in GitHub.

### 3. Connect GitHub to Streamlit Community Cloud

Sign in to Streamlit Community Cloud and connect the GitHub account containing the repository. Private repositories require permission for Streamlit Community Cloud to access them.

### 4. Deploy the app

Create a new app and select:

- Repository: your endowment-model repository
- Branch: normally `main`
- Main file path: `app_annual_hybrid_v3_stress.py`

Then deploy.

### 5. Share the deployed app

After deployment, Streamlit provides a fixed `*.streamlit.app` URL.

For a private app, use the app's sharing settings to grant access to specific viewers. For a public app, anyone with the URL can open it.

## How another person uses the deployed model

1. Open the Streamlit link in a web browser.
2. Upload the required D1 and D2 Excel files.
3. Choose the model settings in the sidebar.
4. Run the annual endowment model.
5. Review deterministic, Monte Carlo, and stress-scenario outputs.
6. Download the generated model-results workbook from the app.

They do not need Python or Streamlit installed on their own computer.

## Current model structure

The V3 application contains:

- annual endowment projection
- D1 market and inflation inputs
- IPEDS / D2 institutional calibration
- NACUBO peer validation
- Monte Carlo simulation
- high-inflation and elevated-rate stress scenario
- prolonged-downturn and liquidity-squeeze stress scenario
- payout-support, budget, drawdown, liquidity, and forced-sale outputs

## Security / data-handling note

Uploaded datasets are supplied by the user through the Streamlit interface during the app session. Do not commit private or restricted datasets to a public GitHub repository. Before sharing the app outside the project team, confirm that the underlying datasets may be uploaded to the chosen hosting environment.

## Troubleshooting

### `ModuleNotFoundError`

Install the dependencies again:

```powershell
python -m pip install -r requirements.txt
```

### Streamlit launcher path error

Use:

```powershell
python -m streamlit run app_annual_hybrid_v3_stress.py
```

instead of calling `streamlit.exe` directly.

### Import error for the model module

Make sure these two files are in the same folder:

```text
app_annual_hybrid_v3_stress.py
endowment_model_annual_hybrid_v3_stress.py
```

### Excel read/write error

Confirm `openpyxl` is installed:

```powershell
python -m pip install openpyxl
```
