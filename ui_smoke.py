"""Dashboard integration check; uses 100 paths for the live analysis action."""
from streamlit.testing.v1 import AppTest
from pathlib import Path
at=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=180).run()
assert not at.exception,at.exception
at.select_slider[0].set_value(100).run()
next(b for b in at.button if b.label=='Run analysis').click().run()
assert not at.exception,at.exception
assert not at.error,[e.value for e in at.error]
print('SIMULATE, BASELINE AND STRESSES PASSED',flush=True)
for page in ['overview','strategies','stress','returns','data','checks','home']:
 next(b for b in at.button if b.key=='open_'+page).click().run()
 assert not at.exception,at.exception
 assert not at.error,[e.value for e in at.error]
 print(page.upper()+' PASSED',flush=True)
next(s for s in at.selectbox if s.label=='Institution').select('Public').run()
next(s for s in at.selectbox if s.label=='Portfolio strategy').select('MeanCVaR').run()
assert not at.exception,at.exception
assert 'baseline' not in at.session_state['results']
print('INPUT INVALIDATION PASSED',flush=True)
