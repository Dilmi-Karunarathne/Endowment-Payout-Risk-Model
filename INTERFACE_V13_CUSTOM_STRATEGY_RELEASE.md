# v13 — Executive dashboard with customizable investment comparisons

## Source and scope

This release is an **interface-only** update to the provided v12 archive, using the
professional light/dark reference screenshots as a *visual design target*. The
portfolio handoff data and every model calculation file remain byte-identical to
v12 (`investment_model.py`, `simple_analysis.py`, `scenario_analysis.py`,
`endowment_simulation_model.py`, `payout_funding.py`, `dashboard_contract.py`).

The screenshots are illustrative design references only. No numerical result has
been copied from them, no new spending rules have been invented, and the model
has not been recalibrated to match their visual example values.

## Interface improvements

- Seven navigation pages remain: **Overview, Portfolio analysis, Payout risk
  measures, Stress testing, Policy responses, Scenario comparison, Model guide**.
- The sidebar navigation uses clean, icon-style menu labels and a full-width
  selected state, instead of displaying large default radio controls.
- An immediately visible **What this section tells you** note on all seven
  sections explains what that page does to nontechnical users.
- A more compact horizontal control bar, professional light/dark color palette,
  four prominently styled risk cards, a large chart and a companion **How to
  read these results** panel match the supplied references more closely.
- The top-bar **Investment strategies** selector is a functional multi-select
  for *all ten* strategies from the latest Research 1 handoff, including Static
  and Dynamic variants. The **three representative Dynamic portfolios** are
  selected on first use:
    - Hierarchical Risk Parity (`HRP_Dynamic`)
    - Mean-CVaR (`MeanCVaR_Dynamic`)
    - Equal-Weight (1/N) (`EqualWeight_Dynamic`)
- A single selected strategy produces a single-portfolio simulation, including
  a shaded 10th–90th percentile wealth band. Multiple selections produce a
  comparison using identical market-path seeds. Any selection—including
  non-default Static portfolios—is honored in baseline, stress testing and
  all other analysis sections.
- The overview chart displays data-derived five-year end-point labels for up
  to five selected strategies. More strategies remain available through the
  legend and comparison tables without crowded labels.
- The 5-year time horizon and original 3-year trailing average spending rule
  remain **fixed** as in the existing engine; their UI labels intentionally do
  not claim to be configurable.
- The empty state displays dashes and instructions, never fabricated numbers.
- Calculated results and downloads continue to use model outputs.

## Use it

1. Select **Overview** and choose **Light** or **Dark** in the left panel.
2. In **Investment strategies**, keep the three default Dynamic portfolios,
   remove one, or choose any alternative from the 10 available portfolios.
3. Choose an institution (Private/Public), a profile (Low/Base/High), starting
   endowment amount, and simulation count (5,000 or 10,000 per case).
4. Click **Run analysis**. Results appear as four risk cards and the wealth
   comparison chart. For additional outputs select **Portfolio analysis** or
   **Payout risk measures**.
5. Select **Stress testing**. The same 10-portfolio multi-select is available
   in the top control bar; choose an adverse scenario below it, then run. Each
   selected strategy receives the same sampled market paths. Large tests with
   many strategies and stresses can take several minutes or exceed available
   Streamlit Cloud computing limits.
6. In **Policy responses**, compare the original stress with a spending or
   reserve policy adjustment on matched market paths.

**Deployment:** Extract the ZIP, copy **all contents inside `Endowment_Final_Model`**
into your GitHub repository's root, commit them, and **reboot Streamlit Cloud**.
Avoid placing an extra `Endowment_Final_Model/` directory above `app.py` unless
that matches your deployment entrypoint. `app.py`, `scenario_analysis.py`,
`simple_analysis.py`, and `dashboard_contract.py` must be deployed together.

## Verification

- `python -m py_compile app.py` passes.
- The app passed compatibility, schema, and Research 1 integration tests on
  developer-sized simulation samples.
- The Streamlit-free screen-path runner checked all seven pages, light and
  dark mode, real multi-strategy charts, first-visit placeholders, two manually
  selected non-default Static strategies, and the **same selection in stress
  testing**: `python tools/check_interface_without_streamlit.py`.
- The Python analysis/finance modules are byte-for-byte unchanged from v12;
  no new full-scale 5,000- or 10,000-path numerical validation run has been
  performed for this UI-only release.
- **Important:** A direct screenshot of the actual deployed Streamlit web
  application has not yet been checked against the user's reference images.
  Native Streamlit widget behavior, browser size and Streamlit Cloud version
  can produce modest visual differences from a static design mockup.
