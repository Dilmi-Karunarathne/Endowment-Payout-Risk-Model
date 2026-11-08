import unittest
from dataclasses import replace
import numpy as np
from endowment_simulation_model import *
from r1_model import *
from scenario_stress import *

class R1Tests(unittest.TestCase):
 def setUp(self):
  self.d=load_default_data();self.i=institutional_params_from_data(self.d);self.l=liquidity_params_from_data(self.d)
  self.c=SimulationConfig(n_sims=3,horizon_years=3)
 def test_all_nine_both_cohorts_and_accounting(self):
  for strategy in STRATEGIES:
   for cohort in ['Private','Public']:
    d=load_default_data(institution_type=cohort,strategy=strategy)
    i=institutional_params_from_data(d,cohort);l=liquidity_params_from_data(d)
    out=run_monte_carlo(d,self.c,i,l)
    a=out['annual_results']
    self.assertLess(a.accounting_residual.abs().max(),1e-8)
    self.assertTrue((a.forced_sale_loss==0).all())
    np.testing.assert_allclose(a[['ending_'+x for x in ASSETS]].sum(axis=1),a.ending_assets)
 def test_public_uses_private_meancvar_only_weights(self):
  a=load_default_data(strategy='MeanCVaR');b=load_default_data(strategy='MeanCVaR',institution_type='Public')
  np.testing.assert_allclose(a.r1_targets,b.r1_targets)
  self.assertNotEqual(institutional_params_from_data(a).effective_spending_rate,institutional_params_from_data(b,'Public').effective_spending_rate)
 def test_forced_regime_switches_at_first_quarter(self):
  q=draw_path(np.random.default_rng(42),self.d,replace(self.c,stress_state='Recession',stress_quarters=6))
  self.assertEqual(q.r1_condition.iloc[0],'Recession')
  self.assertFalse(q.freeze_rebalance.iloc[0])
  self.assertTrue((q.r1_condition.iloc[:6]=='Recession').all())
 def test_pacing_and_drift(self):
  h=np.ones(13)/13*100;target=self.d.r1_targets.loc['Recession'].to_numpy()
  out=rebalance(h,target)
  self.assertAlmostEqual(out.sum(),100)
  self.assertTrue((abs(out[PRIVATE]/100-h[PRIVATE]/100)<=.05000000001).all())
  np.testing.assert_allclose(out[LIQUID]/out[LIQUID].sum(),target[LIQUID]/target[LIQUID].sum())
 def test_joint_sampling_common_random_numbers(self):
  other=load_default_data(strategy='MinVar')
  a=draw_path(np.random.default_rng(42),self.d,self.c);b=draw_path(np.random.default_rng(42),other,self.c)
  np.testing.assert_allclose(np.stack(a.asset_returns),np.stack(b.asset_returns))
  np.testing.assert_allclose(a.cpi_quarter,b.cpi_quarter)
  self.assertTrue(a.freeze_rebalance.iloc[0])
 def test_replay_matches_current_weights_buyhold(self):
  cfg=replace(self.c,horizon_years=1)
  sc=framework_scenarios(self.i)[0]
  q=draw_path(np.random.default_rng(42),self.d,cfg)
  q=make_path_transform(self.d,sc.market)(np.random.default_rng(42),q)
  h=self.d.portfolio_weights.weight.to_numpy()*150
  end,returns,_,_=invest_year(h,q.to_dict('records'))
  historical=self.d.r1_joint.set_index('quarter').loc[['2022Q1','2022Q2','2022Q3','2022Q4']]
  expected=h*np.prod(1+historical[ASSETS].to_numpy(),axis=0)
  np.testing.assert_allclose(end,expected)
  annual=quarterly_to_annual(q,2027)
  self.assertAlmostEqual(annual.inflation.iloc[0],np.prod(1+historical.cpi_quarter)-1)
 def test_additive_drag_only_after_replay(self):
  c=replace(self.c,horizon_years=3)
  q=draw_path(np.random.default_rng(42),self.d,c)
  shock=MarketShock(replay_quarters=('2022Q1','2022Q2','2022Q3','2022Q4'),return_drag_annual=-.04,drag_years=1)
  t=make_path_transform(self.d,shock)(None,q)
  np.testing.assert_allclose(t.return_add,[0]*4+[-.01]*4+[0]*4)
 def test_liquidity_breach_not_payout_cut(self):
  import pandas as pd
  market=pd.DataFrame([dict(year=2027,portfolio_return=0,inflation=0,dominant_condition='Normal')])
  cfg=replace(self.c,horizon_years=1)
  base=run_path(market,cfg,self.i,self.l)
  stressed=run_path(market,cfg,self.i,self.l,pd.DataFrame({'liquid_share_haircut_add':[1.]}))
  self.assertEqual(stressed.liquidity_breach.iloc[0],1)
  self.assertAlmostEqual(base.actual_payout.iloc[0],stressed.actual_payout.iloc[0])
 def test_stress_inputs_and_full_stress_suite(self):
  a,b=r2_stress_defaults(self.i,'Severe')
  self.assertEqual((a.regime_quarters,a.inflation_add,a.return_drag,a.drag_years),(24,.024,-.04,5))
  self.assertEqual((b.recovery_drag,b.recovery_years),(-.04,3))
  for sc in framework_scenarios(self.i)+list(scenario_library(self.i,'Severe',self.d).values()):
   result=run_stress_scenario(self.d,self.c,self.i,self.l,sc)
   self.assertLess(result['annual_results'].accounting_residual.abs().max(),1e-8)
if __name__=='__main__':unittest.main()
