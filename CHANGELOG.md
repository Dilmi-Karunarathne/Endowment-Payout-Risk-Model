# v2.2 interface update

- Opens on Overview with a simplified sidebar and one Run analysis button.
- Removes the Fall/version/cohort banner, repeated provisional-status notices, and sidebar workbook uploader.
- Moves imports, raw settings and detailed assumptions to Data & downloads; technical controls are under Advanced options.
- Adds the dark teal theme in .streamlit/config.toml and reusable presentation functions in dashboard_ui.py.
- Displays shaded 10th–90th percentile bands, median outcomes and starting-value reference lines for real payouts and real endowment.
- Labels current metrics precisely: annual return-coverage frequency, any-year funding shortfall risk, and any-year real principal erosion. No screenshot percentages are reused.
- Formats comparison percentages and money values for reading; detailed simulation tables remain expandable.
- Clears stale results when settings change and preserves all analysis workflows.
- Uses starting assets as both prior values unless historical values are explicitly selected; workbook prior values remain available.
- Main calculation engine and source datasets are unchanged from v2.1. Data gaps remain documented outside the main interface.

# v2.1 changes from the uploaded main_v2 package

- Always cap actual payouts and other payments by available assets; separately report unfunded obligations.
- Replace annual liquidity resets with persistent liquid/moderate/illiquid holdings and optional moderate access; retain reserves explicitly.
- Add single-Normal generator and three-way controlled method comparison.
- Add adverse-component probability, mean and volatility overrides plus probability/severity sensitivity.
- Add return-coverage shortfall frequency/depth alongside funding shortfalls.
- Add separate longest spells, real corpus threshold breaches, first-event censored recovery and cumulative real distributions.
- Add current-assets/trailing spending rules and optional growth collar.
- Add policy trade-off comparisons and data-backed allocation calibration from uploaded asset histories and weights.
- Replace incompatible unused advanced stress scripts with connected stress/sensitivity implementations calling the core engine. The former reverse-stress interface is not retained; it was not part of the revised minimum scope.
- Rebuild app into six research-focused tabs with independent run controls, CSV/settings downloads and input-change invalidation.
- Preserve workbook institutional/liquidity values in editable controls rather than replacing them with defaults; show when selecting another R2 cohort replaces the workbook values.
- Add calibration fit diagnostics, chronological holdout density scores and seed/path-count stability.
- Correct floating-point rounding in the empirical ES tail count; keep aggregate metrics consistent when detailed annual paths are not retained.
- Document timing, definitions, remaining inputs and scope limitations; add regression/integration checks.
