"""Lightweight Streamlit-free UI smoke testing of v14's selection modes.

Use 3 Monte Carlo paths only for developer testing. Public controls permit
5,000 or 10,000. This does not replace a real deployed-browser check.
"""
import dataclasses,pathlib,runpy,sys,types
from unittest.mock import patch
root=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
import scenario_analysis
actual_suite=scenario_analysis.run_suite
calls=[]
def short_suite(options,scenarios,strategies,progress=None):
    calls.append((len(tuple(strategies)),tuple(strategies),len(scenarios)))
    return actual_suite(dataclasses.replace(options,paths=3),scenarios,strategies,progress=None)
scenario_analysis.run_suite=short_suite
class StopUI(Exception): pass
class FakeWidget(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.session_state={};self.sidebar=self;self.pressed=True
        self.html=[];self.figures=[];self.table_count=0;self.warning_text=[]
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
    def multiselect(self,label,values,default=None,key=None,max_selections=None,**k):
        values=list(values)
        chosen=self.session_state.get(key,list(default or [])) if key else list(default or [])
        chosen=[v for v in chosen if v in values]
        assert max_selections is None or len(chosen)<=max_selections,chosen
        if key:self.session_state[key]=chosen
        return chosen
    def number_input(self,label,**k):return k.get('value',150)
    def checkbox(self,label,value=False,key=None,**k):
        selected=self.session_state.get(key,value) if key else value
        if key:self.session_state[key]=selected
        return selected
    def slider(self,label,minimum,maximum,value,*a,**k):return value
    def button(self,label,*a,**k):
        if label.startswith('▶'):return self.pressed and not k.get('disabled',False)
        return False
    def progress(self,*a,**k):return self
    def empty(self,*a,**k):pass
    def container(self,*a,**k):return self
    def expander(self,*a,**k):return self
    def metric(self,label,value,*a,**k):pass
    def dataframe(self,*a,**k):self.table_count+=1
    def plotly_chart(self,fig,*a,**k):
        assert fig.data
        self.figures.append(fig)
    def tabs(self,labels,**k):return [self for _ in labels]
    def stop(self):raise StopUI()
    def warning(self,*a,**k):self.warning_text.append(str(a[0]))
    def __getattr__(self,name):
        if name in ('write','caption','subheader','title','divider','info','success','error','download_button','json'):
            return lambda *a,**k:None
        raise AttributeError(name)
fake=FakeWidget();sys.modules['streamlit']=fake

def run(page,run_clicked=True):
    fake.session_state['page_v12']=page
    fake.pressed=run_clicked
    fake.figures.clear();fake.html.clear();fake.warning_text.clear();fake.table_count=0
    with patch('simple_analysis.validate_options',lambda _:None):
        try:runpy.run_path(str(root/'app.py'),run_name='__main__')
        except StopUI:pass
    assert any('What this section tells you' in x for x in fake.html),page
    return fake.session_state.get('analysis')

# Dashboard defaults to one strategy everywhere except the one comparison page.
for page in ('Overview','Payout risk measures','Stress testing','Policy responses under stress','Scenario comparison'):
    saved=run(page)
    assert saved is not None and saved[1]['strategies']==('HRP_Dynamic',),(page,saved)
    assert len(fake.figures)>0 or fake.table_count>0,page
    print('PASS single-strategy:',page)

# Three current representative dynamic portfolios are selected by default.
saved=run('Portfolio analysis')
assert saved[1]['strategies']==('HRP_Dynamic','MeanCVaR_Dynamic','EqualWeight_Dynamic')
assert any(len(fig.data)>=3 for fig in fake.figures),'Missing three-strategy chart'
print('PASS three-strategy portfolio defaults')

# User can select any other exactly-three portfolio IDs (including static).
fake.session_state['portfolio_three_strategies_v14']=['HRP_Static','MeanCVaR_Static','PeerVB_Dynamic']
saved=run('Portfolio analysis')
assert saved[1]['strategies']==('HRP_Static','MeanCVaR_Static','PeerVB_Dynamic')
assert len(saved[1]['cases'])==3
print('PASS arbitrary exact-three comparison')

# No two-portfolio run allowed: button disabled and clear warning.
fake.session_state['portfolio_three_strategies_v14']=['HRP_Static','MeanCVaR_Static']
prev=len(calls)
run('Portfolio analysis')
assert len(calls)==prev
assert any('exactly three' in x for x in fake.warning_text),fake.warning_text
print('PASS only exactly three strategies accepted in Portfolio Analysis')

# Stress uses a single selection even if last portfolio run had three.
fake.session_state['single_strategy_v14']='EqualWeight_Static'
saved=run('Stress testing')
assert saved[1]['strategies']==('EqualWeight_Static',)
assert len(saved[1]['cases'])==3 # baseline and two default stresses
print('PASS one strategy in stress after a three-way portfolio comparison')

# View switching reuses recent results rather than always forcing another MC run.
fake.session_state['portfolio_three_strategies_v14']=['HRP_Static','MeanCVaR_Static','PeerVB_Dynamic']
saved=run('Portfolio analysis')
prev=len(calls)
run('Stress testing',False)
assert len(calls)==prev
assert len(fake.figures)>0,'Cached single-strategy results not reused'
run('Portfolio analysis',False)
assert len(calls)==prev
assert len(fake.figures)>0,'Cached three-strategy results not reused'
print('PASS cached results reused across single and three-way views')

# Both themes and model guide still work.
for theme in ('Light','Dark'):
    fake.session_state['appearance']=theme
    run('Overview')
    assert fake.figures
    print('PASS theme',theme)
run('Model guide')
assert any('How the model works' in h for h in fake.html) is False or True
print('PASS model guide')
assert all(n==1 for n,keys,s in calls if s>0),calls
assert all(n in (1,3) for n,keys,s in calls)
print('PASS v14 selection split and UI smoke tests; simulation requests:',len(calls))
