# Release validation — v2.2

All 19 automated tests passed on Python 3.12. Tests include 17 engine/integration checks and two Streamlit framework tests. The app tests ran all eight analysis actions, the mixture override workflow, and result invalidation after changing inputs. Allocation construction was tested with synthetic asset histories; real alternative asset-return data are not supplied.

The retained v2.1 engine validation includes a 1,000-path, 10-year baseline, which completed with maximum absolute accounting residual of 2.28e-13 $M (floating-point precision). All return generators, the three-way comparison, four policy cases, six stress cases, and six mixture sensitivity cases executed.

The included stability example uses 200/500 paths and three seeds. Its ES estimates vary, so these sample outputs do not establish stable final tail-risk conclusions. See validation_outputs/README.md for run sizes and settings.

The redesigned app passed the Streamlit AppTest workflow checks, including all analysis actions, mixture controls, clearing stale results, Overview as the first tab and absence of a sidebar file uploader. Browser screenshot QA was unavailable because the browser binary download failed. The live Streamlit Community Cloud deployment was not tested. GitHub and the deployed app have not been modified.

No independent external-data/source audit was performed. Final cohort weights, institutional liquidity/payout policies, clean operating revenue and approved scenarios remain outstanding in PENDING_INPUTS.md.

To verify after installing requirements:

```bash
python -m unittest discover -s tests -v
```
