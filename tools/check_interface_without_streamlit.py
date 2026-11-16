"""Exercise every v13 dashboard branch without a browser or Streamlit dependency.
Uses real financial simulation at six developer-only paths. The public app remains 5k/10k.
"""
import contextlib,dataclasses,pathlib,runpy,sys,types
from unittest.mock import patch
root=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
import scenario_analysis
actual_run_suite=scenario_analysis.run_suite

def short_suite(options,scenarios,strategies,progress=None):
    return actual_run_suite(dataclasses.replace(options,paths=3),scenarios,strategies,progress=None)
scenario_analysis.run_suite=short_suite

class StopUI(Exception): pass
class FakeWidget(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit');self.session_state={};self.sidebar=self
        self.pressed=True;self.html=[];self.plot_count=0;self.table_count=0;self.metrics=[];self.figures=[]
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def set_page_config(self,*a,**k):pass
    def markdown(self,value,*a,**k):self.html.append(value)
    def columns(self,n,*a,**k):return [self for _ in range(n if isinstance(n,int) else len(n))]
    def radio(self,label,values,index=0,key=None,**k):
        choice=self.session_state.get(key,values[index]) if key else values[index]
        if choice not in values:choice=values[index]
        if key:self.session_state[key]=choice
        return choice
    def selectbox(self,label,values,index=0,key=None,**k):
        values=list(values)
        choice=self.session_state.get(key,values[index]) if key else values[index]
        if choice not in values:choice=values[index]
        if key:self.session_state[key]=choice
        return choice
    def multiselect(self,label,values,default=None,key=None,**k):
        values=list(values)
        selected=self.session_state.get(key,list(default or [])) if key else list(default or [])
        selected=[choice for choice in selected if choice in values]
        if key:self.session_state[key]=selected
        return selected
    def number_input(self,label,**k):return k.get('value',150)
    def checkbox(self,label,value=False,key=None,**k):
        val=self.session_state.get(key,value) if key else value
        if key:self.session_state[key]=val
        return val
    def slider(self,label,minimum,maximum,value,*a,**k):return value
    def button(self,label,*a,**k):
        if label.startswith('▶'):return self.pressed
        return False
    def progress(self,*a,**k):return self
    def empty(self,*a,**k):pass
    def container(self,*a,**k):return self
    def expander(self,*a,**k):return self
    def metric(self,label,value,*a,**k):self.metrics.append((label,value))
    def dataframe(self,*a,**k):self.table_count+=1
    def plotly_chart(self,fig,*a,**k):
        assert len(fig.data)>=1;self.plot_count+=1;self.figures.append(fig)
    def tabs(self,labels,**k):return [self for _ in labels]
    def stop(self):raise StopUI()
    def __getattr__(self,name):
        if name in ('write','caption','subheader','title','divider','info','warning','success','error','download_button','json'):
            return lambda *a,**k:None
        raise AttributeError(name)

fake=FakeWidget()
sys.modules['streamlit']=fake
for page in ('Overview','Portfolio analysis','Payout risk measures','Stress testing',
             'Policy responses under stress','Scenario comparison','Model guide'):
    # Different nav views of a shared baseline analysis don't rerun unless requested.
    fake.session_state['page_v12']=page
    fake.session_state['appearance']='Dark' if page=='Stress testing' else 'Light'
    fake.html.clear();fake.plot_count=0;fake.table_count=0
    with patch('simple_analysis.validate_options',lambda _:None):
        try:runpy.run_path(str(root/'app.py'),run_name='__main__')
        except StopUI:pass
    assert any('model-page-title' in h for h in fake.html), page
    if page != 'Model guide':
        assert any('model-kpi' in h for h in fake.html),page
        assert fake.table_count or fake.plot_count, page
    if page=='Overview':
        assert any('How to read these results' in h for h in fake.html)
        assert fake.plot_count >= 1
    print(f'PASS | {page:32s} | charts={fake.plot_count}, tables={fake.table_count}')
    fake.pressed=False
    # A changed mode is deliberately run once after navigation
    if page in ('Payout risk measures','Stress testing','Policy responses under stress','Scenario comparison'):
        fake.pressed=True

# A second iteration with each appearance checks theme state and baseline result reuse.
for theme in ('Light','Dark'):
    fake.session_state['page_v12']='Overview';fake.session_state['appearance']=theme
    fake.pressed=True;fake.html.clear();fake.plot_count=0
    with patch('simple_analysis.validate_options',lambda _:None):
        try:runpy.run_path(str(root/'app.py'),run_name='__main__')
        except StopUI:pass
    assert fake.plot_count>=1
    assert any('How to read these results' in x for x in fake.html)
    print('PASS | overview theme',theme)
# Three-way portfolio comparisons plot the three current handoff choices, not
# the older MinVar portfolio that is absent from the updated Research 1 files.
fake.session_state['page_v12']='Overview'
fake.session_state['selected_strategies_v13']=['HRP_Dynamic','MeanCVaR_Dynamic','EqualWeight_Dynamic']
fake.session_state['appearance']='Light'
fake.pressed=True;fake.html.clear();fake.figures.clear()
with patch('simple_analysis.validate_options',lambda _:None):
    try:runpy.run_path(str(root/'app.py'),run_name='__main__')
    except StopUI:pass
assert any(len(fig.data)>=3 for fig in fake.figures), 'Three-way chart missing'
print('PASS | three-portfolio real-data chart')

# Empty state must be presentable without inventing outcomes.
fake.session_state.pop('analysis',None)
fake.pressed=False;fake.html.clear()
with patch('simple_analysis.validate_options',lambda _:None):
    try:runpy.run_path(str(root/'app.py'),run_name='__main__')
    except StopUI:pass
assert any('Run analysis to calculate' in html for html in fake.html)
print('PASS | safe first-visit placeholder')
# User-selected two non-default STATIC portfolios must be shown as separate
# comparison results on both baseline and stressed runs, not silently reset.
fake.session_state['selected_strategies_v13']=['HRP_Static','EqualWeight_Static']
fake.session_state['page_v12']='Overview';fake.pressed=True;fake.html.clear();fake.figures.clear()
with patch('simple_analysis.validate_options',lambda _:None):
    try:runpy.run_path(str(root/'app.py'),run_name='__main__')
    except StopUI:pass
assert fake.session_state['selected_strategies_v13']==['HRP_Static','EqualWeight_Static']
assert any(len(fig.data)>=2 for fig in fake.figures), 'Custom two-strategy comparison chart missing'
assert fake.session_state['analysis'][1]['strategies']==('HRP_Static','EqualWeight_Static')
print('PASS | selectable non-default Static strategies')
fake.session_state['page_v12']='Stress testing';fake.pressed=True;fake.html.clear();fake.figures.clear()
with patch('simple_analysis.validate_options',lambda _:None):
    try:runpy.run_path(str(root/'app.py'),run_name='__main__')
    except StopUI:pass
assert fake.session_state['analysis'][1]['strategies']==('HRP_Static','EqualWeight_Static')
assert len(fake.session_state['analysis'][1]['cases'])>=4
print('PASS | custom strategies reused in stress testing')
print('Dashboard v13 branch smoke checks: all passed')
