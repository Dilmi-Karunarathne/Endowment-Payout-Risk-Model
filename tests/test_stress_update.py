import unittest,json
from pathlib import Path
from dataclasses import replace
import pandas as pd
import numpy as np
from endowment_simulation_model import (SimulationConfig,InstitutionalParams,LiquidityParams,
    load_default_data,institutional_params_from_data,liquidity_params_from_data,run_path,run_monte_carlo,
    sample_quarterly_path)
from scenario_stress import (InflationStress,LiquidityStress,framework_scenarios,scenario_library,
    EndowmentShock,MarketShock,StressScenario,build_year_overrides,make_path_transform,
    run_stress_suite,run_stress_scenario,reverse_stress_test,sensitivity_grid)

class StressUpdateTests(unittest.TestCase):
    def setUp(self):
        self.d=load_default_data()
        self.c=SimulationConfig(initial_endowment=100,prior_endowment_1y=100,prior_endowment_2y=100,
            horizon_years=3,n_sims=4,return_method='Single Normal',annual_inflation=.025)
        self.i=InstitutionalParams(effective_spending_rate=.05,gift_rate=0,other_changes_rate=0,
            annual_expense_growth=0,spending_rule='Current assets')
        self.l=LiquidityParams(enabled=False,liquid_share=.5,illiquid_share=.5)
        self.a=pd.DataFrame({'year':[2027,2028,2029],'portfolio_return':[0.]*3,'inflation':[0.]*3})
    def test_uploaded_baseline_is_unchanged(self):
        c=SimulationConfig(n_sims=20,horizon_years=4,return_method='Single Normal',annual_inflation=.025)
        r=run_monte_carlo(self.d,c,institutional_params_from_data(self.d),liquidity_params_from_data(self.d))
        expected=pd.read_csv(Path(__file__).parent/'uploaded_baseline_annual.csv')
        pd.testing.assert_frame_equal(r['annual_results'][expected.columns],expected,check_dtype=False,rtol=1e-12,atol=1e-12)
        metrics=json.loads((Path(__file__).parent/'uploaded_baseline_metrics.json').read_text())
        for k,v in metrics.items():
            if pd.isna(v):self.assertTrue(pd.isna(r['metrics'][k]))
            else:self.assertAlmostEqual(r['metrics'][k],v,places=11,msg=k)
    def test_main_scenario_controls_reach_engine(self):
        a,b=framework_scenarios(self.i,InflationStress(9,.02,.06,1,-.02,2),LiquidityStress(gift_multiplier=.5,gift_years=1))
        self.assertEqual(a.market.regime_quarters,9)
        self.assertEqual(a.market.inflation_years,1.25)
        self.assertEqual(a.endowment.expense_growth_add,.06)
        ov=build_year_overrides(b.endowment,3)
        np.testing.assert_allclose(ov.gift_multiplier,[.5,1,1])
        table,detail=run_stress_suite(self.d,self.c,self.i,self.l,[a,b])
        self.assertEqual(len(table),3)
        for r in detail.values():self.assertLess(r['annual_results'].accounting_residual.abs().max(),1e-8)
    def test_forced_inflation_overrides_only_stress_window(self):
        c=replace(self.c,stress_state='Elevated inflation',stress_quarters=5)
        q=sample_quarterly_path(np.random.default_rng(4),self.d,c)
        self.assertFalse(np.allclose(q.cpi_yoy.iloc[:5],.025))
        np.testing.assert_allclose(q.cpi_yoy.iloc[5:],.025)
    def test_replay_and_quarter_exact_inflation_window(self):
        sc=framework_scenarios(self.i,InflationStress(regime_quarters=9,inflation_add=.02))[0]
        q=pd.DataFrame({'p4_return':[0.]*12,'cpi_yoy':[.025]*12,'condition':['Normal']*12})
        actual=make_path_transform(self.d,sc.market)(np.random.default_rng(1),q)
        h=self.d.p4_quarterly.set_index('quarter')
        np.testing.assert_allclose(actual.p4_return.iloc[:4],h.loc[list(sc.market.replay_quarters),'p4_return'])
        np.testing.assert_allclose(actual.cpi_yoy.iloc[4:9],.045)
        np.testing.assert_allclose(actual.cpi_yoy.iloc[9:],.025)
    def test_capital_calls_transfer_assets_not_expense(self):
        ov=build_year_overrides(EndowmentShock(capital_call_rate=.1,capital_call_years=1),3)
        p=run_path(self.a,self.c,replace(self.i,effective_spending_rate=0),replace(self.l,enabled=True),ov)
        self.assertEqual(p.ending_assets.iloc[0],100)
        self.assertEqual(p.ending_liquid_assets.iloc[0],40)
        self.assertEqual(p.ending_illiquid_assets.iloc[0],60)
        np.testing.assert_allclose(p.accounting_residual,0,atol=1e-10)
    def test_unfunded_call_and_payout_priority(self):
        ov=build_year_overrides(EndowmentShock(capital_call_rate=.1,capital_call_years=1),3)
        l=replace(self.l,enabled=True,liquid_share=.06,illiquid_share=.94,allow_forced_sales=False)
        p=run_path(self.a,self.c,self.i,l,ov)
        self.assertAlmostEqual(p.capital_call_paid.iloc[0],6)
        self.assertAlmostEqual(p.unpaid_capital_call.iloc[0],4)
        self.assertEqual(p.actual_payout.iloc[0],0)
    def test_forced_sale_accounting(self):
        ov=build_year_overrides(EndowmentShock(capital_call_rate=.1,capital_call_years=2),3)
        l=replace(self.l,enabled=True,liquid_share=.02,illiquid_share=.98,forced_sale_discount=.3)
        p=run_path(self.a,self.c,self.i,l,ov)
        self.assertGreater(p.forced_sale_loss.sum(),0)
        np.testing.assert_allclose(p.ending_assets,p.pre_payout_assets-p.actual_payout-p.other_cash_paid-p.forced_sale_loss)
    def test_gift_expense_and_special_draw_timing(self):
        ov=build_year_overrides(EndowmentShock(gift_multiplier=.5,gift_years=1,expense_level_shock=.1,
            expense_growth_add=.1,expense_growth_years=1,special_draw_rate=.03,special_draw_years=1),3)
        p=run_path(self.a,self.c,replace(self.i,gift_rate=.1,expenses_to_endowment_ratio=.5),self.l,ov)
        self.assertAlmostEqual(p.actual_payout.iloc[0],8)
        self.assertAlmostEqual(p.special_draw_paid.iloc[0],3)
        np.testing.assert_allclose(p.operating_expenses,[55,60.5,60.5])
        self.assertEqual(p.endowment_gifts.iloc[0],5)
    def test_every_library_scenario_runs(self):
        for sc in scenario_library().values():
            with self.subTest(sc.name):
                r=run_stress_scenario(self.d,replace(self.c,n_sims=2),self.i,self.l,sc)
                self.assertLess(r['annual_results'].accounting_residual.abs().max(),1e-8)
    def test_reverse_and_spending_grid(self):
        v=reverse_stress_test(self.d,self.c,self.i,self.l,.8)
        self.assertTrue(-.95<=v['breaking_shock']<=0)
        g=sensitivity_grid(self.d,self.c,self.i,self.l,shocks=[0,-.2],spending_rates=[.04,.05])
        self.assertTrue(np.isfinite(g.to_numpy()).all())
    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):make_path_transform(self.d,MarketShock(replay_quarters=('1900Q1',)))
        with self.assertRaises(ValueError):run_path(self.a,self.c,self.i,self.l,pd.DataFrame({'bad':[0,0,0]}))
        with self.assertRaises(ValueError):run_stress_scenario(self.d,self.c,self.i,self.l,StressScenario('bad','','',MarketShock(portfolio_shock=-2)))

if __name__=='__main__':unittest.main()
