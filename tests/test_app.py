from streamlit.testing.v1 import AppTest


def test_demo_overview_review_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv('CANDIDATE_DB', str(tmp_path / 'ui.sqlite3'))
    app = AppTest.from_file('app.py', default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label == 'Ladda fiktiva demoprofiler').click().run()
    assert not app.exception
    assert '15 tillagda' in app.success[0].value
    app.sidebar.radio[0].set_value('Kandidatöversikt').run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 15
    app.text_input[0].set_value('Fiktiv kandidat 01').run()
    assert len(app.dataframe[0].value) == 1
    app.sidebar.radio[0].set_value('Kandidatdetaljer').run()
    assert not app.exception
    next(s for s in app.selectbox if s.label == 'Granskningsstatus').set_value('Intressant')
    next(t for t in app.text_area if t.label.startswith('Egna anteckningar')).set_value('Fiktiv granskningsanteckning')
    next(b for b in app.button if b.label == 'Spara granskning').click().run()
    assert not app.exception
    next(c for c in app.checkbox if c.label.startswith('Bekräfta permanent')).check().run()
    next(b for b in app.button if b.label == 'Radera kandidatuppgifter').click().run()
    assert not app.exception
    app.sidebar.radio[0].set_value('Kandidatöversikt').run()
    assert app.metric[0].value == '14'


def test_manual_profile_and_edit_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv('CANDIDATE_DB', str(tmp_path / 'manual.sqlite3'))
    app = AppTest.from_file('app.py', default_timeout=30).run()
    next(t for t in app.text_input if t.label == 'Namn *').set_value('Fiktiv manuell profil')
    next(t for t in app.text_input if t.label == 'Källänk *').set_value('https://example.com/manual')
    next(b for b in app.button if b.label == 'Spara profil').click().run()
    assert not app.exception
    app.sidebar.radio[0].set_value('Kandidatdetaljer').run()
    next(t for t in app.text_area if t.label == 'Förändringsledning').set_value('Ledde dokumenterat förändringsprogram.')
    next(b for b in app.button if b.label == 'Spara yrkesunderlag').click().run()
    assert not app.exception
    from candidate_finder.storage import Store
    from candidate_finder.analysis import analyze
    stored = Store(tmp_path / 'manual.sqlite3').all()[0]
    assert analyze(stored)['categories'] == ['A']
    assert stored.evidence['change']['text'] == 'Ledde dokumenterat förändringsprogram.'
