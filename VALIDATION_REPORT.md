# Release validation — v2.1

All 19 automated tests passed on Python 3.12. Tests include 17 engine/integration checks and two Streamlit framework tests. The app tests ran all eight analysis actions, the mixture override workflow, and result invalidation after changing inputs. Allocation construction was tested with synthetic asset histories; real alternative asset-return data are not supplied.

The 1,000-path, 10-year baseline completed with maximum absolute accounting residual of 2.28e-13 $M (floating-point precision). All return generators, the three-way comparison, four policy cases, six stress cases, and six mixture sensitivity cases executed.

The included stability example uses 200/500 paths and three seeds. Its ES estimates vary, so these sample outputs do not establish stable final tail-risk conclusions. See validation_outputs/README.md for run sizes and settings.

The app was tested through Streamlit AppTest, not in a browser or a live Streamlit Community Cloud deployment. GitHub and the deployed app have not been modified.

No independent external-data/source audit was performed. Final cohort weights, institutional liquidity/payout policies, clean operating revenue and approved scenarios remain outstanding in PENDING_INPUTS.md.

To verify after installing requirements:

```bash
python -m unittest discover -s tests -v
```
