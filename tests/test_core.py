import io
import json
import pytest
from candidate_finder.model import Candidate, UNKNOWN
from candidate_finder.analysis import analyze, categories
from candidate_finder.storage import Store
from candidate_finder.ingestion import read_csv, export_frame, excel_bytes
from candidate_finder.search import BraveSearch, queries, linkedin_profile_url


def profile(**kwargs):
    return Candidate(name='Fiktiv person', source_url='https://example.com/profile', **kwargs).validate()


def evidence(key='change'):
    return {key: {'text': 'Ledde ett dokumenterat projekt.', 'level': 2, 'confidence': 'Medel'}}

@pytest.mark.parametrize('kwargs,expected', [
    ({'evidence': evidence()}, ['A']),
    ({'consultant': True}, ['B']),
    ({'years': 4, 'evidence': evidence('responsibility')}, ['C']),
    ({}, ['D']),
    ({'consultant': True, 'years': 4, 'evidence': evidence('responsibility')}, ['B', 'C']),
    ({'discovery': True, 'consultant': True, 'evidence': evidence()}, ['D']),
])
def test_categories(kwargs, expected):
    assert categories(profile(**kwargs)) == expected


def test_missing_is_unknown_not_negative():
    a = analyze(profile())
    assert len(a['missing']) == 6
    assert a['coverage'] == 0
    assert all(row['Belägg / relevant erfarenhet'] == UNKNOWN and row['Nivå (1–3)'] is None for row in a['criteria'])


def test_weighted_evidence_is_traceable():
    a = analyze(profile(evidence=evidence()))
    assert a['priority'] == round(6 / 39 * 100)
    assert a['criteria'][0]['Källa'] == 'https://example.com/profile'
    assert a['coverage'] == 23


def test_discovery_never_scores_snippets():
    c = profile(description='Expert change leader', discovery=True, evidence=evidence())
    assert analyze(c)['coverage'] == 0
    assert analyze(c)['priority'] == 0


def test_title_does_not_invent_qualifications():
    assert analyze(profile(role='Senior Management Consultant'))['coverage'] == 0
    assert categories(profile(role='Senior Management Consultant')) == ['D']


def test_store_dedup_preserves_notes_and_delete(tmp_path):
    store = Store(tmp_path / 'test.sqlite3')
    assert store.save(profile())
    c = store.all()[0]
    c.notes = 'Viktigt underlag'
    store.save(c)
    duplicate = profile()
    duplicate.source_url += '/?utm_source=search#about'
    assert not store.save(duplicate)
    assert len(store.all()) == 1
    assert store.all()[0].notes == 'Viktigt underlag'
    store.delete(c.id)
    assert not Store(tmp_path / 'test.sqlite3').all()


def test_csv_validation_and_demo():
    candidates, errors = read_csv('data/demo_candidates.csv')
    assert len(candidates) == 15
    assert not errors
    assert {categories(c)[0] for c in candidates} == set('ABCD')
    candidates, errors = read_csv(io.StringIO('name,source_url,years\nTest,https://example.com,not-a-number\n'))
    assert not candidates and len(errors) == 1


def test_roundtrip_exports():
    candidates, _ = read_csv('data/demo_candidates.csv')
    frame = export_frame(candidates)
    reimported, errors = read_csv(io.StringIO(frame.to_csv(index=False)))
    assert len(reimported) == 15 and not errors
    import pandas as pd
    assert len(pd.read_excel(io.BytesIO(excel_bytes(frame)))) == 15


def test_formula_injection_neutralized():
    c = profile()
    c.name = '=HYPERLINK("bad")'
    assert export_frame([c]).iloc[0]['name'].startswith("'=")

@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///tmp/data', 'https://user:password@example.com'])
def test_unsafe_links_rejected(url):
    with pytest.raises(ValueError):
        Candidate(name='Test', source_url=url).validate()


def test_bad_evidence_rejected():
    with pytest.raises(ValueError):
        profile(evidence={'change': {'text': 'Merit', 'level': 7}})


def test_query_expansion_and_no_api_key(monkeypatch):
    assert any('Strategy Manager' in q for q in queries('Umeå', 'A'))
    assert any('Västerbotten' in q for q in queries('Umeå', 'A'))
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    with pytest.raises(ValueError, match='saknas'):
        BraveSearch().search(['example'], 5)


def test_search_adapter_deduplicates_and_marks_unknown(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'web': {'results': [{'title': 'Fiktiv profil', 'url': 'https://se.linkedin.com/in/fiktiv-person?tracking=1', 'description': '<b>En kort</b> beskrivning'}]}}
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY', 'test-key')
    monkeypatch.setattr('candidate_finder.search.requests.get', lambda *args, **kwargs: Response())
    monkeypatch.setattr('candidate_finder.search.time.sleep', lambda _: None)
    result = BraveSearch().search(['one', 'two'], 5)
    assert len(result) == 1 and result[0].discovery
    assert analyze(result[0])['coverage'] == 0


@pytest.mark.parametrize('url', [
    'https://linkedin.com/company/example', 'https://linkedin.com/jobs/view/1',
    'https://linkedin.com.evil.example/in/person', 'https://notlinkedin.com/in/person',
    'https://example.com/in/person', 'https://linkedin.com/in/person/detail/contact-info/',
    'https://user:pass@linkedin.com/in/person', 'javascript:alert(1)',
])
def test_only_personal_linkedin_profiles(url):
    with pytest.raises(ValueError):
        linkedin_profile_url(url)


def test_regional_linkedin_urls_normalized():
    assert linkedin_profile_url('https://se.linkedin.com/in/example/?trk=123#about') == 'https://www.linkedin.com/in/example'
    assert all(q.startswith('site:linkedin.com/in/') for q in queries('Stockholm'))


def test_search_paginates_filters_and_limits(monkeypatch):
    calls = []
    class Response:
        def __init__(self, offset): self.offset = offset
        def raise_for_status(self): pass
        def json(self):
            return {'query': {'more_results_available': True}, 'web': {'results': [
                {'title': 'Company', 'url': 'https://www.linkedin.com/company/example'},
                {'title': 'Wrong domain', 'url': 'https://example.com/profile'},
                {'title': 'Fiktiv profil', 'url': f'https://www.linkedin.com/in/person-{self.offset}', 'description': '<b>Obekräftat</b>'}
            ]}}
    def get(url, **kwargs):
        assert url == 'https://api.search.brave.com/res/v1/web/search'
        assert kwargs['headers']['X-Subscription-Token'] == 'session-test-key'
        calls.append(kwargs['params'])
        return Response(kwargs['params']['offset'])
    monkeypatch.setattr('candidate_finder.search.requests.get', get)
    monkeypatch.setattr('candidate_finder.search.time.sleep', lambda _: None)
    result = BraveSearch(api_key='session-test-key').search(['query'], 2)
    assert len(result) == 2 and len(calls) == 2
    assert result[0].description == 'Obekräftat'
    assert all(c.discovery and c.years is None and not c.evidence for c in result)


def test_search_request_budget(monkeypatch):
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'web': {'results': []}}
    def get(*args, **kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr('candidate_finder.search.requests.get', get)
    monkeypatch.setattr('candidate_finder.search.time.sleep', lambda _: None)
    assert not BraveSearch(api_key='test').search([str(n) for n in range(50)], 100)
    assert len(calls) == 30
