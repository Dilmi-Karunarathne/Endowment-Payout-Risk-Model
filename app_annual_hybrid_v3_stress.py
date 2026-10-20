import streamlit as st
import pandas as pd
from io import BytesIO

from endowment_model_annual_hybrid_v3_stress import (
    Params,
    load_d1_asset_returns,
    load_d1_inflation,
    load_ipeds_calibration,
    apply_ipeds_calibration,
    load_d2_budget_calibration,
    apply_d2_budget_calibration,
    load_nacubo_validation,
    latest_complete_annual_scenario,
    run_annual_model,
    summarize_annual,
    monte_carlo_annual,
    run_structured_stress_test,
    compare_stress_scenarios,
)


# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------

st.set_page_config(
    page_title="Endowment Payout Risk Model",
    layout="wide"
)

st.title("Endowment Payout Risk Model")
st.caption(
    "Hybrid annual framework: monthly D1 market data are compounded "
    "to annual returns, while IPEDS and NACUBO are used at annual frequency."
)


# ---------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------

st.sidebar.header("Model Settings")

initial_endowment = st.sidebar.number_input(
    "Initial Endowment ($ millions)",
    min_value=1.0,
    value=100.0,
    step=10.0
)

horizon_years = st.sidebar.number_input(
    "Projection Horizon (Years)",
    min_value=1,
    max_value=20,
    value=10,
    step=1
)

n_sims = st.sidebar.number_input(
    "Monte Carlo Simulations",
    min_value=100,
    max_value=10000,
    value=2000,
    step=100
)

block_size = st.sidebar.number_input(
    "Bootstrap Block Size (Months)",
    min_value=1,
    max_value=12,
    value=3,
    step=1
)


st.sidebar.markdown("---")
st.sidebar.subheader("Institutional Budget Settings")

starting_operating_revenue = st.sidebar.number_input(
    "Year 1 Operating Revenue excl. Endowment Payout ($M)",
    min_value=0.0, value=18.0, step=1.0
)

starting_expenses = st.sidebar.number_input(
    "Year 1 Operating Expenses ($M)",
    min_value=0.0, value=24.0, step=1.0
)

non_tuition_growth = st.sidebar.number_input(
    "Non-Tuition Revenue Growth",
    min_value=-0.20, max_value=0.30, value=0.00, step=0.005, format="%.3f"
)

support_scenario = st.sidebar.selectbox(
    "Endowment Support Scenario",
    ["Low (25th percentile)", "Median", "High (75th percentile)"],
    index=1
)

tuition_growth_basis = st.sidebar.radio(
    "Tuition Revenue Growth Basis",
    ["Net tuition revenue growth", "Undergraduate tuition price growth"],
    index=0,
    help=(
        "Net tuition revenue growth is preferred for projecting revenue because it reflects "
        "both price and enrollment/discounting effects. Tuition-price growth is retained as a scenario option."
    )
)


st.sidebar.markdown("---")
st.sidebar.subheader("Structured Stress Scenarios")
st.sidebar.caption(
    "Defaults are illustrative. Replace them with calibrated assumptions when confirmed."
)

high_inflation_peak = st.sidebar.number_input(
    "High-inflation peak", min_value=0.00, max_value=0.20,
    value=0.06, step=0.005, format="%.3f"
)
high_inflation_years = st.sidebar.number_input(
    "High-inflation stress duration (years)", min_value=1, max_value=10,
    value=3, step=1
)
high_inflation_return_shock = st.sidebar.number_input(
    "Portfolio-return adjustment during inflation stress",
    min_value=-0.30, max_value=0.20, value=-0.02, step=0.01, format="%.3f"
)
high_inflation_extra_expense_growth = st.sidebar.number_input(
    "Extra expense growth during inflation stress",
    min_value=0.00, max_value=0.20, value=0.02, step=0.005, format="%.3f"
)

downturn_initial_return = st.sidebar.number_input(
    "Downturn Year 1 portfolio return",
    min_value=-0.80, max_value=0.30, value=-0.20, step=0.01, format="%.3f"
)
downturn_second_return = st.sidebar.number_input(
    "Downturn Year 2 portfolio return",
    min_value=-0.80, max_value=0.30, value=-0.10, step=0.01, format="%.3f"
)
downturn_recovery_return = st.sidebar.number_input(
    "Downturn recovery-year portfolio return",
    min_value=-0.50, max_value=0.50, value=0.05, step=0.01, format="%.3f"
)
stressed_liquid_allocation = st.sidebar.number_input(
    "Stressed liquid allocation",
    min_value=0.00, max_value=1.00, value=0.35, step=0.05, format="%.2f"
)
stressed_forced_sale_discount = st.sidebar.number_input(
    "Stressed forced-sale discount",
    min_value=0.00, max_value=0.90, value=0.30, step=0.05, format="%.2f"
)
stressed_cash_need_multiplier = st.sidebar.number_input(
    "Stressed annual cash-need multiplier",
    min_value=1.00, max_value=5.00, value=1.50, step=0.10, format="%.2f"
)


# ---------------------------------------------------------
# FILE UPLOADS
# ---------------------------------------------------------

st.subheader("1. Upload Source Data")

col1, col2, col3 = st.columns(3)

with col1:
    d1_file = st.file_uploader("D1 Asset & Economic Data", type=["xlsx"], key="d1")
    ipeds_file = st.file_uploader("D2 IPEDS Data", type=["xlsx"], key="ipeds")
    nacubo_file = st.file_uploader("D2 NACUBO Historical Data", type=["xlsx"], key="nacubo")

with col2:
    tuition_dependence_file = st.file_uploader(
        "D2 Tuition Dependence", type=["xlsx"], key="tuition_dependence"
    )
    net_tuition_file = st.file_uploader(
        "D2 Net Tuition & Fees", type=["xlsx"], key="net_tuition"
    )
    tuition_file = st.file_uploader(
        "D2 Tuition", type=["xlsx"], key="tuition"
    )

with col3:
    total_expenses_file = st.file_uploader(
        "D2 Total Expenses", type=["xlsx"], key="expenses"
    )
    spending_distribution_file = st.file_uploader(
        "D2 Spending Distribution", type=["xlsx"], key="spending_distribution"
    )

all_files_uploaded = all([
    d1_file, ipeds_file, nacubo_file, tuition_dependence_file,
    net_tuition_file, tuition_file, total_expenses_file, spending_distribution_file
])

if all_files_uploaded:
    st.success("All market, endowment, and institutional-budget datasets uploaded successfully.")
else:
    st.info(
        "Upload the D1 market workbook, IPEDS/NACUBO files, and the five D2 budget files "
        "to run the fully calibrated version."
    )


# ---------------------------------------------------------
# RUN MODEL
# ---------------------------------------------------------

if all_files_uploaded:

    if st.button(
        "Run Annual Endowment Model",
        type="primary"
    ):

        try:

            with st.spinner("Running deterministic and Monte Carlo models..."):

                # -------------------------------------------------
                # 1. BASE PARAMETERS
                # -------------------------------------------------

                params = Params(
                    initial_endowment=float(initial_endowment),
                    horizon_years=int(horizon_years),
                    other_revenue_y1=float(starting_operating_revenue),
                    opex_y1=float(starting_expenses),
                    non_tuition_revenue_growth=float(non_tuition_growth),
                )


                # -------------------------------------------------
                # 2. IPEDS CALIBRATION
                # -------------------------------------------------

                ipeds_summary = load_ipeds_calibration(
                    ipeds_file
                )

                params = apply_ipeds_calibration(
                    params,
                    ipeds_summary
                )

                # -------------------------------------------------
                # 3. D2 INSTITUTIONAL-BUDGET CALIBRATION
                # -------------------------------------------------

                d2_budget_calibration = load_d2_budget_calibration(
                    tuition_dependence_file=tuition_dependence_file,
                    net_tuition_file=net_tuition_file,
                    tuition_file=tuition_file,
                    total_expenses_file=total_expenses_file,
                    spending_distribution_file=spending_distribution_file,
                )

                params = apply_d2_budget_calibration(
                    params,
                    d2_budget_calibration,
                    use_net_tuition_growth=(tuition_growth_basis == "Net tuition revenue growth"),
                    support_scenario=support_scenario,
                    non_tuition_growth=float(non_tuition_growth),
                )


                # -------------------------------------------------
                # 4. NACUBO VALIDATION BENCHMARKS
                # -------------------------------------------------

                nacubo_summary = load_nacubo_validation(
                    nacubo_file
                )


                # -------------------------------------------------
                # 5. D1 MARKET DATA
                # -------------------------------------------------

                monthly_returns = load_d1_asset_returns(
                    d1_file
                )

                inflation_history = load_d1_inflation(
                    d1_file
                )


                # -------------------------------------------------
                # 6. DETERMINISTIC ANNUAL SCENARIO
                # -------------------------------------------------

                deterministic_scenario = latest_complete_annual_scenario(
                    monthly_returns,
                    params.weights,
                    years=params.horizon_years
                )

                deterministic_inflation = (
                    inflation_history["Inflation"]
                    .reindex(deterministic_scenario.index)
                    .fillna(0.0)
                )

                annual_result = run_annual_model(
                    params,
                    deterministic_scenario,
                    annual_inflation=deterministic_inflation
                )

                summary = summarize_annual(
                    annual_result,
                    params,
                    ipeds_summary,
                    nacubo_summary
                )


                # -------------------------------------------------
                # 7. MONTE CARLO
                # -------------------------------------------------

                mc = monte_carlo_annual(
                    params,
                    historical_returns=monthly_returns,
                    n_sims=int(n_sims),
                    seed=42,
                    block_size=int(block_size),
                    inflation_history=inflation_history,
                    nacubo_summary=nacubo_summary
                )

                # -------------------------------------------------
                # 8. STRUCTURED STRESS SCENARIOS
                # -------------------------------------------------
                stress_settings = dict(
                    high_inflation_peak=float(high_inflation_peak),
                    high_inflation_years=int(high_inflation_years),
                    high_inflation_return_shock=float(high_inflation_return_shock),
                    high_inflation_extra_expense_growth=float(high_inflation_extra_expense_growth),
                    downturn_initial_return=float(downturn_initial_return),
                    downturn_second_return=float(downturn_second_return),
                    downturn_recovery_return=float(downturn_recovery_return),
                    downturn_stress_years=3,
                    stressed_liquid_allocation=float(stressed_liquid_allocation),
                    stressed_forced_sale_discount=float(stressed_forced_sale_discount),
                    stressed_cash_need_multiplier=float(stressed_cash_need_multiplier),
                )

                stress_comparison = compare_stress_scenarios(
                    params,
                    deterministic_scenario,
                    deterministic_inflation,
                    scenario_settings=stress_settings,
                )

                high_inflation_result = run_structured_stress_test(
                    params,
                    deterministic_scenario,
                    deterministic_inflation,
                    "High Inflation & Elevated Rates",
                    **stress_settings,
                )

                downturn_result = run_structured_stress_test(
                    params,
                    deterministic_scenario,
                    deterministic_inflation,
                    "Prolonged Downturn & Liquidity Squeeze",
                    **stress_settings,
                )


            st.success("Model completed successfully.")


            # ---------------------------------------------------------
            # KEY MODEL INFORMATION
            # ---------------------------------------------------------

            st.subheader("2. Model Calibration")

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Peer Cohort",
                str(params.peer_cohort)
            )

            c2.metric(
                "IPEDS Spending Rate",
                f"{params.spending_rate:.2%}"
            )

            c3.metric(
                "IPEDS Gift Rate",
                f"{params.annual_gift_rate:.2%}"
            )

            c4.metric(
                "Projection Horizon",
                f"{len(annual_result)} years"
            )

            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Tuition Dependence", f"{params.tuition_dependence:.2%}")
            b2.metric("Tuition Revenue Growth", f"{params.tuition_revenue_growth:.2%}")
            b3.metric("Expense Growth", f"{params.expense_growth:.2%}")
            b4.metric("Endowment Support Ratio", f"{params.support_ratio:.2%}")

            st.caption(
                "The tuition/non-tuition split is a provisional calibration because D2 tuition dependence "
                "uses total institutional revenue as its denominator, while this model's operating-revenue "
                "base excludes endowment payout. Treat it as a scenario assumption until Research/Data 2 confirms alignment."
            )


            # ---------------------------------------------------------
            # KEY DETERMINISTIC RESULTS
            # ---------------------------------------------------------

            st.subheader("3. Deterministic Results")

            d1, d2, d3, d4 = st.columns(4)

            d1.metric(
                "Ending Endowment",
                f"${summary['Ending endowment ($mm)']:,.2f}M"
            )

            d2.metric(
                "Nominal CAGR",
                f"{summary['Nominal endowment CAGR']:.2%}"
            )

            d3.metric(
                "Maximum Nominal Drawdown",
                f"{summary['Maximum nominal drawdown']:.2%}"
            )

            d4.metric(
                "Maximum Real Drawdown",
                f"{summary['Maximum real drawdown']:.2%}"
            )

            d5, d6, d7, d8 = st.columns(4)

            d5.metric(
                "Ending Real Endowment",
                f"${summary['Ending real endowment ($mm, base-year dollars)']:,.2f}M"
            )

            d6.metric(
                "Total Payout",
                f"${summary['Total payout ($mm)']:,.2f}M"
            )

            d7.metric(
                "Liquidity Shortfall Frequency",
                f"{summary['Liquidity-shortfall frequency']:.1%}"
            )

            d8.metric(
                "Years with Budget Deficit",
                f"{int(summary['Years with budget deficit'])}"
            )


            s1, s2, s3 = st.columns(3)
            s1.metric(
                "Years with Payout Support Gap",
                f"{int(summary['Years with payout support gap'])}"
            )
            s2.metric(
                "Max Payout Support Gap",
                f"${summary['Maximum payout support gap ($mm)']:,.2f}M"
            )
            s3.metric(
                "Minimum Payout Adequacy Ratio",
                f"{summary['Minimum payout adequacy ratio']:.2f}x"
            )


            # ---------------------------------------------------------
            # DETERMINISTIC TABLES
            # ---------------------------------------------------------

            left, right = st.columns(2)

            with left:
                st.markdown("#### Annual Model Summary")
                st.dataframe(
                    summary.to_frame("Result"),
                    use_container_width=True
                )

            with right:
                st.markdown("#### Annual Market Scenario")
                st.dataframe(
                    deterministic_scenario,
                    use_container_width=True
                )


            # ---------------------------------------------------------
            # MONTE CARLO RESULTS
            # ---------------------------------------------------------

            st.subheader("4. Monte Carlo Risk Results")

            m1, m2, m3, m4 = st.columns(4)

            m1.metric(
                "Mean Ending Endowment",
                f"${mc['Mean ending endowment ($mm)']:,.2f}M"
            )

            m2.metric(
                "5th Percentile Ending Endowment",
                f"${mc['5th percentile ending endowment ($mm)']:,.2f}M"
            )

            m3.metric(
                "P(Real Endowment < Initial)",
                f"{mc['P(ending real endowment below initial)']:.1%}"
            )

            m4.metric(
                "P(Liquidity Shortfall)",
                f"{mc['P(liquidity shortfall in any year)']:.1%}"
            )

            m5, m6, m7, m8 = st.columns(4)

            m5.metric(
                "Mean Max Nominal Drawdown",
                f"{mc['Mean maximum nominal drawdown']:.1%}"
            )

            m6.metric(
                "Mean Max Real Drawdown",
                f"{mc['Mean maximum real drawdown']:.1%}"
            )

            m7.metric(
                "P(Budget Deficit)",
                f"{mc['P(budget deficit in any year)']:.1%}"
            )

            if "P(drawdown worse than NACUBO peer median)" in mc.index:
                m8.metric(
                    "P(Drawdown Worse Than Peer)",
                    f"{mc['P(drawdown worse than NACUBO peer median)']:.1%}"
                )
            else:
                m8.metric(
                    "NACUBO Drawdown Comparison",
                    "N/A"
                )

            ms1, ms2 = st.columns(2)
            ms1.metric(
                "P(Payout Support Gap)",
                f"{mc['P(payout support gap in any year)']:.1%}"
            )
            ms2.metric(
                "Mean Minimum Payout Adequacy",
                f"{mc['Mean minimum payout adequacy ratio']:.2f}x"
            )

            st.dataframe(
                mc.to_frame("Result"),
                use_container_width=True
            )


            # ---------------------------------------------------------
            # STRUCTURED STRESS-SCENARIO RESULTS
            # ---------------------------------------------------------

            st.subheader("5. Structured Stress-Scenario Results")
            st.caption(
                "Base case versus the two proposed adverse regimes. "
                "Scenario parameters are adjustable and should be replaced by calibrated assumptions when confirmed."
            )

            st.dataframe(
                stress_comparison.style.format({
                    "Ending Endowment ($M)": "${:,.2f}",
                    "Ending Real Endowment ($M)": "${:,.2f}",
                    "Nominal CAGR": "{:.2%}",
                    "Maximum Nominal Drawdown": "{:.2%}",
                    "Maximum Real Drawdown": "{:.2%}",
                    "Total Payout ($M)": "${:,.2f}",
                    "Maximum Payout Support Gap ($M)": "${:,.2f}",
                    "Maximum Liquidity Shortfall ($M)": "${:,.2f}",
                    "Total Forced-Sale Loss ($M)": "${:,.2f}",
                }),
                use_container_width=True
            )

            st.markdown("#### Stress Endowment Paths")
            stress_path_chart = pd.DataFrame({
                "Base": annual_result["Ending Assets"].to_numpy(),
                "High Inflation & Elevated Rates": high_inflation_result["Ending Assets"].to_numpy(),
                "Prolonged Downturn & Liquidity Squeeze": downturn_result["Ending Assets"].to_numpy(),
            }, index=annual_result.index)
            st.line_chart(stress_path_chart, use_container_width=True)

            with st.expander("View High Inflation Stress Details"):
                st.dataframe(high_inflation_result, use_container_width=True)

            with st.expander("View Downturn & Liquidity Stress Details"):
                st.dataframe(downturn_result, use_container_width=True)


            # ---------------------------------------------------------
            # CHARTS
            # ---------------------------------------------------------

            st.subheader("6. Endowment Path")

            endowment_chart = annual_result[
                [
                    "Beginning Assets",
                    "Ending Assets",
                    "Real Ending Assets"
                ]
            ]

            st.line_chart(
                endowment_chart,
                use_container_width=True
            )


            st.subheader("7. Drawdown")

            drawdown_chart = annual_result[
                [
                    "Nominal Drawdown",
                    "Real Drawdown"
                ]
            ]

            st.line_chart(
                drawdown_chart,
                use_container_width=True
            )


            st.subheader("8. Annual Payout and Liquidity")

            payout_liquidity_chart = annual_result[
                [
                    "Actual Payout",
                    "Required Liquidity",
                    "Liquidity Shortfall"
                ]
            ]

            st.bar_chart(
                payout_liquidity_chart,
                use_container_width=True
            )


            # ---------------------------------------------------------
            # DETAIL TABLES
            # ---------------------------------------------------------

            with st.expander("View Detailed Annual Results"):
                st.dataframe(
                    annual_result,
                    use_container_width=True
                )

            with st.expander("View IPEDS Calibration"):
                st.dataframe(
                    ipeds_summary,
                    use_container_width=True
                )

            with st.expander("View D2 Institutional Budget Calibration"):
                st.dataframe(
                    d2_budget_calibration.to_frame("Value"),
                    use_container_width=True
                )

            with st.expander("View NACUBO Peer Benchmarks"):
                st.dataframe(
                    nacubo_summary,
                    use_container_width=True
                )


            # ---------------------------------------------------------
            # CREATE OUTPUT EXCEL
            # ---------------------------------------------------------

            def create_output_excel(
                annual_result,
                summary,
                mc,
                deterministic_scenario,
                ipeds_summary,
                d2_budget_calibration,
                nacubo_summary,
                stress_comparison,
                high_inflation_result,
                downturn_result
            ):

                output = BytesIO()

                with pd.ExcelWriter(
                    output,
                    engine="openpyxl"
                ) as writer:

                    annual_result.to_excel(
                        writer,
                        sheet_name="Annual Results"
                    )

                    summary.to_frame(
                        "Result"
                    ).to_excel(
                        writer,
                        sheet_name="Summary"
                    )

                    mc.to_frame(
                        "Result"
                    ).to_excel(
                        writer,
                        sheet_name="Monte Carlo"
                    )

                    deterministic_scenario.to_excel(
                        writer,
                        sheet_name="Annual Market Scenario"
                    )

                    ipeds_summary.to_excel(
                        writer,
                        sheet_name="IPEDS Calibration"
                    )

                    d2_budget_calibration.to_frame("Value").to_excel(
                        writer,
                        sheet_name="D2 Budget Calibration"
                    )

                    nacubo_summary.to_excel(
                        writer,
                        sheet_name="NACUBO Validation"
                    )

                    stress_comparison.to_excel(
                        writer,
                        sheet_name="Stress Comparison"
                    )

                    high_inflation_result.to_excel(
                        writer,
                        sheet_name="Stress High Inflation"
                    )

                    downturn_result.to_excel(
                        writer,
                        sheet_name="Stress Downturn Liquidity"
                    )

                output.seek(0)

                return output


            output_file = create_output_excel(
                annual_result,
                summary,
                mc,
                deterministic_scenario,
                ipeds_summary,
                d2_budget_calibration,
                nacubo_summary,
                stress_comparison,
                high_inflation_result,
                downturn_result
            )


            # ---------------------------------------------------------
            # DOWNLOAD
            # ---------------------------------------------------------

            st.subheader("9. Download Results")

            st.download_button(
                "Download Annual Model Results",
                data=output_file,
                file_name="Endowment_Annual_Hybrid_Model_Output.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )


        except Exception as error:

            st.error(
                "The model could not be completed."
            )

            st.exception(error)
