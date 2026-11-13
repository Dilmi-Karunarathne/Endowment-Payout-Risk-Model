# v5.1 — Fix for `KeyError: mean_total_assets_m`

## What happened

The Streamlit dashboard loads its last simulation from `st.session_state.sim_result`.
The v5 asset-pool section expects `yearly["mean_total_assets_m"]` and other columns.
Older result formats (v3/v4) lack these columns. If a browser session keeps
such a result across an app update, or files are deployed from mixed versions,
the dashboard raises a Pandas `KeyError` instead of displaying the charts.

## Fix

* `dashboard_contract.py` defines the v5.1 schema and verifies required
  annual and path-year columns.
* `simple_analysis.py` stamps newly generated results with the v5.1 version.
* `app.py` detects stale session results, removes them safely, and requests
  a new run. If the deployed engine is incompatible, it shows a clear message
  telling you to update the project files, rather than a raw `KeyError`.
* **No return, gift, payout, or risk calculation has been changed.**

## Deployment

1. Replace your repo files with **all** files from the v5.1 ZIP.
2. Commit/push to GitHub.
3. Restart the Streamlit Cloud app (Manage app -> Reboot app).
4. Click **Run simulation** to recalculate the results.

You can also try reloading and clicking **Run simulation** on v5, but if the
repository contains old `simple_analysis.py` code, the full update is needed.

## Verification

Fresh 100-path Private/Base results include all three annual asset columns:
`mean_total_assets_m`, `mean_spendable_assets_m`, and
`mean_restricted_gift_assets_m`. Their values reconcile by year.
The schema validator rejects v4-like saved results and accepts v5.1 outputs.
