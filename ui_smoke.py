from streamlit.testing.v1 import AppTest
from pathlib import Path
at=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=180).run()
assert not at.exception,at.exception
at.select_slider[0].set_value(100).run()
next(b for b in at.button if b.label=='Run analysis').click().run()
assert not at.exception,at.exception
assert not at.error,[e.value for e in at.error]
print('BASELINE AND PRIMARY STRESSES PASSED',flush=True)
next(b for b in at.button if b.key=='open_overview').click().run()
assert not at.exception,at.exception
print('OVERVIEW PASSED',flush=True)
next(b for b in at.button if b.key=='back_to_dashboard').click().run()
next(b for b in at.button if b.key=='open_stress').click().run()
assert not at.exception,at.exception
next(s for s in at.selectbox if s.label=='Stress severity').select('Severe').run()
assert not at.exception,at.exception
next(b for b in at.button if b.label=='Run stress tests').click().run()
assert not at.exception,at.exception
assert not at.error,[e.value for e in at.error]
print('SEVERE STRESS PASSED',flush=True)
next(b for b in at.button if b.key=='back_to_dashboard').click().run()
next(b for b in at.button if b.key=='open_strategies').click().run()
next(b for b in at.button if b.label=='Compare all nine portfolios').click().run()
assert not at.exception,at.exception
assert not at.error,[e.value for e in at.error]
print('NINE STRATEGY UI COMPARISON PASSED',flush=True)
next(b for b in at.button if b.key=='back_to_dashboard').click().run()
next(b for b in at.button if b.key=='open_data').click().run()
assert not at.exception,at.exception
next(s for s in at.selectbox if s.label=='Institution').select('Public').run()
next(s for s in at.selectbox if s.label=='Portfolio strategy').select('MeanCVaR').run()
assert not at.exception,at.exception
next(b for b in at.button if b.label=='Run analysis').click().run()
assert not at.exception,at.exception
assert not at.error,[e.value for e in at.error]
print('PUBLIC MEANCVAR PASSED',flush=True)
