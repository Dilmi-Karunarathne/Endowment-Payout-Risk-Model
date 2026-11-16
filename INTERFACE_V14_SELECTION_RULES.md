# v14 — Three-portfolio comparisons only in Portfolio Analysis

## Requested behavior

The investment strategy controls now depend on the section:

| Dashboard section | Investment selection | What it runs |
| --- | --- | --- |
| **Overview** | One portfolio | One baseline and its real-wealth distribution |
| **Portfolio analysis** | **Exactly three portfolios, customizable** | Three baseline portfolios on the same market/asset/inflation draws |
| **Payout risk measures** | One portfolio | One baseline with the detailed payout risk measures |
| **Stress testing** | One portfolio | One portfolio: unchanged baseline + user-selected adverse scenarios |
| **Policy responses** | One portfolio | One portfolio: baseline, unchanged stress, same stress with policy adjustment |
| **Scenario comparison** | One portfolio | One portfolio: baseline + selected what-if assumptions |
| **Model guide** | No financial run needed | Definitions and assumptions (global single selector visible) |

### Default comparison choices

Portfolio Analysis initially selects the following three from the actual November
2026 Research 1 handoff:

1. Hierarchical Risk Parity — Dynamic (`HRP_Dynamic`)
2. Mean-CVaR — Dynamic (`MeanCVaR_Dynamic`)
3. Equal-Weight — Dynamic (`EqualWeight_Dynamic`)

Any three **different** current portfolios may be selected, including Static
versions. The selector will not allow more than three. If the user removes one,
the comparison run button is disabled and a plain-language warning asks for a
third. The other sections use one selectbox, defaulting to HRP Dynamic; no
second or third portfolio can enter their simulation request.

All ten Research 1 portfolio choices remain available to both selectors. The
old Minimum Variance portfolio is not in the current handoff and is therefore
not offered as a default.

### Reruns and saved results

Two matching simulation results are retained in Streamlit session state, keyed
by the complete model signature, so switching between a single-portfolio view
and the three-way Portfolio Analysis view can reuse matching results without
rerunning the Monte Carlo paths. Changing an assumption changes the signature;
old results are never presented as belonging to different inputs. Only the last
two experiment signatures are retained to limit memory use.

### Calculation and framework preservation

**Only `app.py`, documentation, and UI tests changed.** No model engine, return,
payout, spending, capital-call, liquidity, crisis-sale-value, or Expected
Shortfall formulas were changed. The single-portfolio and three-way selectors
continue to use the same `run_suite()` method and the current Research 1 inputs.

### Validation

- Streamlit-free execution of all seven navigation views, both themes, default
  single/three selectors, arbitrary three strategies including Static portfolios,
  rejection of only two comparison portfolios, stress-testing after switching
  from a comparison, and session result reuse.
- 35 non-UI model and source compatibility tests passed (see `test_results.txt`
  in the build log; not included in package).
- Python syntax compilation passed.
- Live browser appearance has not been verified in Streamlit Cloud. Public UI
  simulation counts remain 5,000 and 10,000. UI smoke runs use 3 paths only
  as a developer test.

### Deployment

Replace the **entire** old GitHub project directory with the contents of
`Endowment_Final_Model` in the ZIP, preserving `.streamlit/config.toml`, then
commit and reboot Streamlit Cloud. Do not combine an old `app.py` with this
release. No screenshots' illustrative numerical results are used in the app.
