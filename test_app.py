"""Exercise dashboard controls, rendering, stale results and exports."""
from dataclasses import replace
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
import scenario_analysis

@pytest.mark.parametrize('mode',['Baseline & strategies','Stress testing','Policy responses under stress','What-if scenarios'])
def test_dashboard_runs_and_exports(mode):
    run=scenario_analysis.run_suite
    def short(options,*args,**kwargs):
        with patch('simple_analysis.validate_options',lambda _:None):
            return run(replace(options,paths=3),*args,**kwargs)
    with patch('scenario_analysis.run_suite',short):
        app=AppTest.from_file('app.py',default_timeout=30).run()
        app.radio(key='navigation').set_value(mode).run()
        assert not app.exception
        if mode=='Baseline & strategies':
            app.sidebar.checkbox[0].check().run()
        if mode=='What-if scenarios':
            next(c for c in app.checkbox if c.label=='Add a custom scenario').check().run()
        next(b for b in app.button if b.label=='Run analysis').click().run()
        assert not app.exception
        assert any(x.value=='Results' for x in app.subheader)
        assert len(app.dataframe)>0
        next(b for b in app.button if b.label=='Prepare full calculation download').click().run()
        assert not app.exception
        assert app.session_state['download_data'][:2]==b'PK'
        app.sidebar.number_input[0].set_value(160.).run()
        assert any('settings have changed' in x.value for x in app.info)
        assert not any(x.value=='Results' for x in app.subheader)


def test_guide_renders():
    app=AppTest.from_file('app.py',default_timeout=30).run()
    app.radio(key='navigation').set_value('Model guide').run()
    assert not app.exception
