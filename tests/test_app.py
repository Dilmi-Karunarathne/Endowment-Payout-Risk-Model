"""Framework-level UI checks; a browser deployment is a separate step."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

class AppTests(unittest.TestCase):
    def test_all_analysis_buttons_and_invalidation(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(len(at.tabs),6)
        self.assertEqual(at.tabs[0].label,'Overview')
        self.assertEqual(len(at.sidebar.get('file_uploader')),0)
        self.assertFalse(any('Fall research framework' in str(x.value) or 'interim portfolio' in str(x.value) for x in at.caption))
        at.select_slider[0].set_value(100).run()
        next(w for w in at.selectbox if w.label=='Paths per scenario').set_value(100).run()
        for label in ['Run analysis','Compare policies','Compare return models',
                      'Run stress tests',
                      'Run historical check','Run holdout check',
                      'Check simulation stability']:
            next(b for b in at.button if b.label==label).click().run()
            self.assertEqual(len(at.exception),0,label)
            self.assertEqual(len(at.error),0,label)
        self.assertIn('baseline',at.session_state['results'])
        next(s for s in at.slider if s.label=='Projection horizon (years)').set_value(5).run()
        self.assertNotIn('baseline',at.session_state['results'])
        self.assertNotIn('main_stress',at.session_state['results'])
    def test_mixture_controls_reach_engine(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
        at.select_slider[0].set_value(100).run()
        next(w for w in at.selectbox if w.label=='Paths per scenario').set_value(100).run()
        next(s for s in at.selectbox if s.label=='Return model').select('Two-component Normal mixture').run()
        next(c for c in at.checkbox if c.label=='Customize adverse-return assumptions').check().run()
        next(v for v in at.number_input if v.label=='Adverse-quarter probability (%)').set_value(30.).run()
        next(b for b in at.button if b.label=='Run analysis').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(len(at.error),0)
        self.assertIn('baseline',at.session_state['results'])

if __name__=='__main__':unittest.main()

class StressScreenTests(unittest.TestCase):
    def test_main_controls_results_and_invalidation(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=90).run()
        self.assertEqual(len(at.exception),0)
        self.assertFalse(any(b.label=='Run additional scenarios' for b in at.button))
        next(w for w in at.selectbox if w.label=='Paths per scenario').set_value(100).run()
        next(b for b in at.button if b.label=='Run stress tests').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(len(at.error),0)
        table,detail=at.session_state['results']['main_stress']
        self.assertEqual(len(table),3)
        self.assertEqual(detail['Baseline']['metrics']['n_sims'],100)
        next(w for w in at.slider if w.label=='Extra inflation after replay (percentage points)').set_value(2.).run()
        self.assertNotIn('main_stress',at.session_state['results'])
        next(w for w in at.checkbox if w.label=='Prolonged downturn & liquidity squeeze').uncheck().run()
        next(b for b in at.button if b.label=='Run stress tests').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(len(at.session_state['results']['main_stress'][0]),2)
    def test_optional_tools_and_empty_selection(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=90).run()
        for name in ['High inflation & elevated rates','Prolonged downturn & liquidity squeeze']:
            next(w for w in at.checkbox if w.label==name).uncheck().run()
        next(b for b in at.button if b.label=='Run stress tests').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertNotIn('main_stress',at.session_state['results'])
        next(w for w in at.toggle if w.label=='Additional scenarios and tools').set_value(True).run()
        self.assertEqual(len(at.exception),0)
        next(w for w in at.selectbox if w.label=='Paths per additional scenario').set_value(100).run()
        next(w for w in at.multiselect if w.label=='Additional scenarios').set_value(['Custom scenario']).run()
        for label in ['Run additional scenarios','Find breaking point','Run spending sensitivity']:
            next(b for b in at.button if b.label==label).click().run()
            self.assertEqual(len(at.exception),0,label)
            self.assertEqual(len(at.error),0,label)
        self.assertEqual(list(at.session_state['results']['extra_stress'][0].Scenario),['Baseline','Custom scenario'])
