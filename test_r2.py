import unittest
from dataclasses import replace
import pandas as pd
from endowment_simulation_model import *
from scenario_stress import *
class R2Tests(unittest.TestCase):
 def setUp(self):
  self.d=load_default_data();self.i=institutional_params_from_data(self.d);self.l=liquidity_params_from_data(self.d)
  self.c=SimulationConfig(horizon_years=3)
  self.m=pd.DataFrame(dict(year=[2027,2028,2029],portfolio_return=[0.,0.,0.],inflation=[0.,0.,0.],dominant_condition=['Normal']*3))
 def test_final_data(self):
  self.assertAlmostEqual(self.i.effective_spending_rate,.04897258021797972)
  self.assertEqual(self.i.other_changes_rate,0)
 def test_collar(self):
  for rate,target in [(.01,.03),(.09,.05)]:
   r=run_path(self.m,self.c,replace(self.i,effective_spending_rate=rate),self.l)
   self.assertAlmostEqual(r.planned_payout.iloc[0],150*target)
 def test_expense_timing_and_recovery(self):
  base=run_path(self.m,self.c,self.i,self.l)
  sc=framework_scenarios(self.i)[0]
  stressed=run_path(self.m,self.c,self.i,self.l,scenario_year_overrides(sc,3))
  self.assertAlmostEqual(stressed.operating_expenses.iloc[0]/base.operating_expenses.iloc[0],1.0945/(1+self.i.annual_expense_growth))
  self.assertAlmostEqual(stressed.operating_expenses.iloc[1]/stressed.operating_expenses.iloc[0],1+self.i.annual_expense_growth)
 def test_gifts_and_budget(self):
  a,b=r2_stress_defaults(self.i,'Severe');self.assertEqual(b.gift_multiplier,.57);self.assertEqual(b.gift_years,2)
  r=run_path(self.m,self.c,self.i,self.l)
  self.assertAlmostEqual(r.operating_balance.iloc[0],r.net_tuition.iloc[0]+r.other_operating_revenue.iloc[0]+r.actual_payout.iloc[0]-r.operating_expenses.iloc[0])
  self.assertAlmostEqual(r.net_tuition.iloc[1]/r.net_tuition.iloc[0],1+self.i.net_tuition_growth)
 def test_enrollment_effect(self):
  base=run_path(self.m,self.c,self.i,self.l)
  worse=run_path(self.m,self.c,replace(self.i,enrollment_growth_override=self.i.enrollment_growth-.01),self.l)
  self.assertLess(worse.net_tuition.iloc[1],base.net_tuition.iloc[1])
 def test_both_cohorts_severe(self):
  for cohort,growth,gift in [('Private',.1253,.57),('Public',.0966,.56)]:
   i=institutional_params_from_data(self.d,cohort);a,b=r2_stress_defaults(i,'Severe')
   self.assertEqual(a.expense_growth,growth);self.assertEqual(b.gift_multiplier,gift)
   self.assertNotIn('Special appropriation',scenario_library(i))
if __name__=='__main__':unittest.main()
