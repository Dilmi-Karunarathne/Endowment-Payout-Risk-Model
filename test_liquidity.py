"""Run: python -m unittest -v test_liquidity"""
import unittest
from dataclasses import replace
import numpy as np
import pandas as pd
from liquidity_model import fund_obligations, matrix_row, load_matrix
from endowment_simulation_model import (load_default_data, liquidity_params_from_data,
    institutional_params_from_data, SimulationConfig, LiquidityParams, InstitutionalParams, run_path)
from scenario_stress import (run_stress_scenario, run_deterministic_stress, scenario_library,
    framework_scenarios, scenario_year_overrides)

class FundingTests(unittest.TestCase):
    def test_cash_sufficient(self):
        h,s,loss=fund_obligations([8,50,10,32],5,.1,[1,0,0])
        np.testing.assert_allclose(h,[8,50,10,32]);self.assertEqual(s.sum(),0);self.assertEqual(loss,0)
    def test_gross_up(self):
        h,s,loss=fund_obligations([2,60,8,30],5,.1,[1,0,0])
        self.assertAlmostEqual(s.sum(),3/.9);self.assertAlmostEqual(h[0],5)
        self.assertAlmostEqual(loss,1/3);self.assertAlmostEqual(h.sum(),100-loss)
    def test_sale_limit(self):
        h,s,loss=fund_obligations([2,2,10,86],5,.1,[1,0,0])
        self.assertAlmostEqual(h[0],3.8);self.assertAlmostEqual(5-h[0],1.2)
        self.assertAlmostEqual(loss,.2)
    def test_frozen_assets_cash_unrestricted(self):
        h,s,loss=fund_obligations([2,50,10,38],5,.1,[1,1,1],1)
        self.assertEqual(h[0],2);self.assertEqual(s.sum(),0)
    def test_zero_discount_and_no_double_count(self):
        h,s,loss=fund_obligations([2,60,8,30],5,0,[1,0,0])
        self.assertEqual(s.sum(),3);self.assertEqual(h.sum(),100)
    def test_invalid_discount(self):
        with self.assertRaises(ValueError):fund_obligations([2,60,8,30],5,1,[1,0,0])
    def test_horizon_lookup(self):
        matrix=load_matrix()
        self.assertEqual(matrix_row(matrix,1,'Recession')[0],.05)
        self.assertEqual(matrix_row(matrix,12,'Recession')[0],.02)
    def test_path_rollforward_call_and_shortfall(self):
        c=SimulationConfig(initial_endowment=100,prior_endowment_1y=100,prior_endowment_2y=100,horizon_years=1)
        i=InstitutionalParams(effective_spending_rate=.1,gift_rate=0,other_changes_rate=0)
        l=LiquidityParams(cash_share=.02,illiquid_share=.96,hedge_share=.1)
        # old aggregate liquid_share must remain consistent for legacy validation
        l=replace(l,liquid_share=.04)
        annual=pd.DataFrame([dict(year=2027,portfolio_return=0,inflation=0,dominant_condition='Recession')])
        out=run_path(annual,c,i,l,pd.DataFrame({'capital_call_rate':[.01]})).iloc[0]
        self.assertAlmostEqual(out.capital_call_paid,1)
        self.assertAlmostEqual(out.actual_payout,2.94)
        self.assertAlmostEqual(out.payout_shortfall_amount,7.06)
        self.assertAlmostEqual(out.ending_assets,100-2.94-.06)
        self.assertAlmostEqual(out.accounting_residual,0)
    def test_all_scenarios_and_six_portfolios(self):
        c=SimulationConfig(n_sims=2,horizon_years=5,return_method='Single Normal')
        for institution in ['Private','Public']:
            for allocation in ['Normal','Elevated Inflation','Recession']:
                d=load_default_data(institution_type=institution,allocation=allocation)
                i=institutional_params_from_data(d,institution);l=liquidity_params_from_data(d)
                for sc in framework_scenarios(i):
                    r=run_stress_scenario(d,c,i,l,sc)['annual_results']
                    self.assertLess(r.accounting_residual.abs().max(),1e-8)
                    self.assertTrue((r.actual_payout<=r.planned_payout+1e-10).all())
                    self.assertTrue((r.ending_cash>=0).all())
                for sc in scenario_library().values():
                    r=run_deterministic_stress(d,c,i,l,sc)
                    self.assertLess(r.accounting_residual.abs().max(),1e-8)
    def test_stress_window_and_policy_consistency(self):
        d=load_default_data();i=institutional_params_from_data(d)
        for sc in framework_scenarios(i):
            ov=scenario_year_overrides(sc,6)
            self.assertNotEqual(ov.liquidity_regime.iloc[0],0)
            self.assertEqual(ov.liquidity_regime.iloc[-1],0)
            self.assertEqual(sc.endowment.liquidity_overrides,{})
    def test_mandatory(self):
        self.assertTrue(LiquidityParams(enabled=False).enabled)

if __name__=='__main__':unittest.main()
