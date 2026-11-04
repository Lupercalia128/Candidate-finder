import os
import sqlite3
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from candidate_finder.model import Candidate, CRITERIA, UNKNOWN
from candidate_finder.storage import Store
from candidate_finder.analysis import analyze
from candidate_finder.ingestion import read_csv, export_frame, excel_bytes
from candidate_finder.search import BraveSearch, queries, PLACES

load_dotenv()
st.set_page_config(page_title='Pro&Pro · Candidate finder', page_icon='◈', layout='wide')
st.markdown('''<style>.stApp {background: #f7f8fa;} h1,h2,h3 {color:#183a38;}
[data-testid="stSidebar"] {background:#e9efed;} div.stButton > button[kind="primary"] {background:#23645a;border:0;}
</style>''', unsafe_allow_html=True)
store = Store(os.getenv('CANDIDATE_DB', 'data/candidates.sqlite3'))
st.sidebar.title('Pro&Pro')
st.sidebar.caption('CANDIDATE FINDER · MVP')
page = st.sidebar.radio('Arbetsyta', ['Sök kandidater', 'Kandidatöversikt', 'Kandidatdetaljer'])
st.sidebar.info('Beslutsstöd för manuell granskning. Underlag och belägg ska verifieras av en människa.')
st.sidebar.caption('Personliga egenskaper bedöms vid intervju. Ålder, kön och andra skyddade egenskaper ingår inte i modellen.')


def import_candidates(candidates):
    added = sum(store.save(c) for c in candidates)
    st.success(f'{added} tillagda · {len(candidates) - added} dubbletter hoppades över. Befintliga uppgifter behålls.')


if page == 'Sök kandidater':
    st.title('Hitta nästa kollega')
    st.caption('Yrkeserfarenhet, tydliga källor och mänsklig bedömning.')
    tab_import, tab_manual, tab_search = st.tabs(['CSV & demodata', 'Manuell profil', 'Sök LinkedIn'])
    with tab_import:
        st.subheader('Börja med ett underlag')
        st.write('Importera endast yrkesuppgifter som ni har rätt att behandla. CSV kräver name och source_url. Se README för beläggformat.')
        uploaded = st.file_uploader('Välj CSV (UTF-8)', type='csv')
        if uploaded is not None:
            try:
                candidates, errors = read_csv(uploaded)
                st.write(f'{len(candidates)} giltiga rader')
                for error in errors:
                    st.error(error)
                if st.button('Importera giltiga rader', disabled=not candidates):
                    import_candidates(candidates)
            except (ValueError, pd.errors.ParserError, UnicodeError) as exc:
                st.error(str(exc))
        st.divider()
        st.write('15 helt fiktiva kandidater för att utforska verktyget utan API-nyckel.')
        if st.button('Ladda fiktiva demoprofiler', type='primary'):
            candidates, errors = read_csv(Path(__file__).parent / 'data/demo_candidates.csv')
            import_candidates(candidates)
        st.download_button('Hämta exempel-CSV', (Path(__file__).parent / 'data/demo_candidates.csv').read_bytes(), 'demo_candidates.csv', 'text/csv')
    with tab_manual:
        st.subheader('Lägg till en dokumenterad profil')
        with st.form('manual'):
            name = st.text_input('Namn *')
            city = st.selectbox('Ort', list(PLACES))
            role = st.text_input('Nuvarande roll')
            company = st.text_input('Företag')
            years_known = st.checkbox('Erfarenhet är dokumenterad')
            years = st.number_input('Arbetslivserfarenhet (år)', 0.0, 80.0, 5.0, 0.5)
            education = st.text_input('Utbildning (valfritt)')
            url = st.text_input('Källänk *')
            description = st.text_area('Yrkesbeskrivning')
            consultant = st.checkbox('Dokumenterad erfarenhet från managementkonsultföretag')
            st.caption('Ange ett konkret belägg och källa per kriterium. Tomt fält = okänt. Nivåer är manuella: 1 relevant, 2 konkret ansvar, 3 dokumenterat resultat.')
            evidence = {}
            for key, (label, _) in CRITERIA.items():
                text = st.text_area(label, key=f'text_{key}')
                cols = st.columns(3)
                level = cols[0].selectbox('Nivå', [1, 2, 3], key=f'level_{key}')
                confidence = cols[1].selectbox('Säkerhet i underlaget', ['Låg', 'Medel', 'Hög'], key=f'confidence_{key}')
                source = cols[2].text_input('Beläggets källa (annars huvudkälla)', key=f'source_{key}')
                if text.strip():
                    evidence[key] = dict(text=text, level=level, confidence=confidence, source=source or url)
            submitted = st.form_submit_button('Spara profil', type='primary')
        if submitted:
            try:
                import_candidates([Candidate(name=name, city=city, role=role, company=company, years=years if years_known else None,
                    education=education, source_url=url, description=description, consultant=consultant, evidence=evidence)])
            except ValueError as exc:
                st.error(str(exc))
    with tab_search:
        st.subheader('Hitta kandidater på LinkedIn')
        st.write('Välj ort och yrkesbakgrund. Appen söker efter offentliga LinkedIn-profiler via Brave Search och sparar profilernas länkar och sökutdrag i kandidatöversikten.')
        st.caption('Sökningen omfattar sökmotorns index, inte alla LinkedIn-medlemmar. Fullständiga profiler hämtas inte. Namn och meriter i utdragen behöver verifieras.')
        api_key = None
        if not os.getenv('BRAVE_SEARCH_API_KEY'):
            st.markdown('**Första gången:** skapa en nyckel på [Brave Search API](https://api-dashboard.search.brave.com/). Välj ett abonnemang som tillåter er användning och lagring av sökresultat.')
            api_key = st.text_input('Brave Search API-nyckel', type='password', key='brave_api_key')
            st.caption('Nyckeln används under den här sessionen och sparas inte i kandidatdatabasen eller i projektfiler. Klistra aldrig in den i chatten.')
        else:
            st.success('Sök-API är konfigurerat.')
        place = st.selectbox('Geografiskt område', list(PLACES), key='search_place')
        category = st.selectbox('Yrkesbakgrund / kategori', ['Alla', 'A', 'B', 'C', 'D'])
        keywords = st.text_input('Roller och sökord')
        st.caption('Filtrera dokumenterade erfarenhetsår efter granskning i Kandidatöversikt. Erfarenhet gissas inte från sökutdrag.')
        limit = st.number_input('Maximalt antal resultat', 1, 100, 15)
        generated = queries(place, category, keywords)
        with st.expander('Genererade frågor och synonymer'):
            st.write(generated)
        authorized = st.checkbox('Jag har kontrollerat användningsrättigheter och API-villkor för sökning och lagring av utdrag.')
        st.caption('Maximalt 30 API-anrop per sökning. Resultatet kan innehålla färre profiler än önskat; API-kostnad och kvoter beror på ert abonnemang.')
        if st.button('Sök LinkedIn och hämta kandidater', type='primary', disabled=not authorized or not (api_key or os.getenv('BRAVE_SEARCH_API_KEY'))):
            try:
                with st.spinner('Söker efter offentliga LinkedIn-profiler…'):
                    results = BraveSearch(api_key=api_key).search(generated, int(limit))
                    import_candidates(results)
                    if results:
                        st.info('Öppna Kandidatöversikt i vänstermenyn för att se profilerna. Ort och yrkesmeriter är ännu obekräftade och behöver granskas i källan.')
                    else:
                        st.info('Inga LinkedIn-profiler hittades. Prova färre extra sökord, annan yrkesbakgrund eller Hela Sverige.')
            except (ValueError, requests.RequestException) as exc:
                # Avoid showing request headers or secret values.
                if isinstance(exc, requests.HTTPError):
                    status_code = exc.response.status_code if exc.response is not None else None
                    st.error({401: 'API-nyckeln godkändes inte. Kontrollera din Brave Search-nyckel.',
                              403: 'Brave nekade åtkomst. Kontrollera att nyckeln har rätt abonnemang och åtkomst.',
                              429: 'Brave har begränsat antalet anrop eller kvoten är slut. Kontrollera abonnemanget och försök senare.'}.get(status_code, 'Söktjänsten svarade med ett fel. Försök senare.'))
                elif isinstance(exc, requests.RequestException):
                    st.error('Kunde inte nå söktjänsten. Kontrollera nätverksåtkomst till api.search.brave.com och försök igen.')
                elif isinstance(exc, ValueError):
                    st.error('Kontrollera API-nyckeln och sökinställningarna. Söktjänstens svar kunde inte behandlas.')

elif page == 'Kandidatöversikt':
    st.title('Kandidatöversikt')
    candidates = store.all()
    cols = st.columns(3)
    cols[0].metric('Profiler i underlaget', len(candidates))
    cols[1].metric('Intressanta', sum(c.status == 'Intressant' for c in candidates))
    cols[2].metric('Granskade', sum(c.status == 'Granskad' for c in candidates))
    query = st.text_input('Sök namn, roll, företag eller yrkesbeskrivning')
    filters = st.columns(4)
    city = filters[0].multiselect('Ort', sorted({c.city for c in candidates if c.city}))
    company = filters[1].multiselect('Företag', sorted({c.company for c in candidates if c.company}))
    category = filters[2].multiselect('Kategori', ['A', 'B', 'C', 'D'])
    status = filters[3].multiselect('Status', ['Intressant', 'Osäker', 'Granskad'])
    years_range = st.slider('Dokumenterad erfarenhet', 0, 80, (0, 80))
    include_unknown = st.checkbox('Inkludera okänd erfarenhet', value=True)
    sort = st.selectbox('Sortera', ['Prioritet för manuell granskning', 'Namn', 'Underlagets täckning'])
    filtered = []
    for c in candidates:
        a = analyze(c)
        if query.casefold() not in ' '.join([c.name, c.role, c.company, c.description]).casefold(): continue
        if city and c.city not in city: continue
        if company and c.company not in company: continue
        if category and not set(category).intersection(a['categories']): continue
        if status and c.status not in status: continue
        if c.years is None and not include_unknown: continue
        if c.years is not None and not years_range[0] <= c.years <= years_range[1]: continue
        filtered.append(c)
    filtered.sort(key=lambda c: c.name.casefold() if sort == 'Namn' else -analyze(c)['coverage' if sort == 'Underlagets täckning' else 'priority'])
    st.caption('Prioritet visar dokumenterade viktade belägg (0–100), inte lämplighet eller sannolikhet för framgång. Okänt är inte bristande förmåga. A: Intraprenören · B: Managementkonsulten · C: Lovande kandidaten · D: Manuell bedömning.')
    table = []
    for c in filtered:
        a = analyze(c)
        table.append({'ID': c.id, 'Namn / sidtitel': c.name, 'Ort': c.city, 'Nuvarande roll': c.role, 'Företag': c.company,
            'Erfarenhet': f'{c.years:g} år' if c.years is not None else 'Okänd', 'Kategori': ' / '.join(a['categories']),
            'Bedömning': f"{a['priority']} · täckning {a['coverage']}%", 'Status': c.status, 'Källa': c.source_url})
    st.dataframe(pd.DataFrame(table), hide_index=True, width='stretch', column_config={'Källa': st.column_config.LinkColumn('Källa')})
    if filtered:
        selected = st.selectbox('Välj kandidat för detaljer (öppna sidan Kandidatdetaljer)', [c.id for c in filtered], format_func=lambda id_: next(c.name for c in filtered if c.id == id_), key='overview_selected')
        st.session_state['selected_id'] = selected
        frame = export_frame(filtered)
        st.download_button('Exportera CSV', frame.to_csv(index=False).encode('utf-8-sig'), 'kandidater.csv', 'text/csv')
        st.download_button('Exportera Excel', excel_bytes(frame), 'kandidater.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        st.info('Inga profiler matchar filtret. Lägg till underlag på Sök kandidater.')

else:
    st.title('Kandidatdetaljer')
    candidates = store.all()
    if not candidates:
        st.info('Ladda demoprofiler eller importera underlag på Sök kandidater.')
    else:
        ids = [c.id for c in candidates]
        current = st.session_state.get('selected_id', ids[0])
        id_ = st.selectbox('Kandidat', ids, index=ids.index(current) if current in ids else 0,
            format_func=lambda value: next(c.name for c in candidates if c.id == value))
        c = next(c for c in candidates if c.id == id_)
        a = analyze(c)
        st.subheader(c.name)
        st.write(' · '.join(x for x in [c.role, c.company, c.city] if x))
        st.link_button('Öppna profilens källa', c.source_url)
        if c.discovery:
            st.warning('Upptäckt sida – identitet och kvalifikationer är obekräftade. Verifiera manuellt innan profilen analyseras.')
        st.write(f"Erfarenhet: {str(c.years) + ' år' if c.years is not None else UNKNOWN}")
        st.write('Utbildning: ' + (c.education or UNKNOWN))
        st.write(c.description)
        st.write(f"Primär kategori: {a['categories'][0]} · Sekundär: {', '.join(a['categories'][1:]) or 'Ingen'}")
        st.write(f"Prioritet för manuell granskning: {a['priority']}/100 · Underlagets täckning: {a['coverage']}%")
        st.caption('Kategori B kräver markerad konsulterfarenhet. C kräver 3–5 dokumenterade år och belägg för ansvar. A kräver belägg för intern förändringsledning. D används när underlaget inte räcker.')
        st.dataframe(pd.DataFrame(a['criteria']), hide_index=True, width='stretch', column_config={'Källa': st.column_config.LinkColumn('Källa')})
        st.write('Motivering: ' + ('Profilen innehåller dokumenterade belägg för ' + ', '.join(r['Kriterium'] for r in a['criteria'] if r['Nivå (1–3)'] is not None) + '.' if a['coverage'] else 'Underlaget saknar strukturerade belägg och behöver granskas manuellt.'))
        st.write('Saknade uppgifter: ' + (', '.join(a['missing']) or 'Inga kriterier saknar belägg; kontrollera källornas aktualitet.'))
        st.info('Intervjufrågor: Be om exempel på samarbete, nyfikenhet, ambition och ödmjukhet. Dessa egenskaper bedöms inte automatiskt.')
        with st.expander('Komplettera yrkesuppgifter och belägg'):
            with st.form(f'edit_{c.id}'):
                edited_name = st.text_input('Namn / verifierad identitet', c.name)
                edited_city = st.text_input('Dokumenterad ort', c.city)
                edited_role = st.text_input('Yrkesroll', c.role)
                edited_company = st.text_input('Organisation', c.company)
                edited_education = st.text_input('Utbildning', c.education)
                edited_url = st.text_input('Huvudkälla', c.source_url)
                edited_description = st.text_area('Dokumenterad yrkesbeskrivning', c.description)
                edited_years_known = st.checkbox('Antal erfarenhetsår är verifierat', value=c.years is not None)
                edited_years = st.number_input('Verifierade erfarenhetsår', 0.0, 80.0, float(c.years or 0), 0.5)
                edited_consultant = st.checkbox('Verifierad managementkonsulterfarenhet', c.consultant)
                edited_evidence = {}
                for key, (label, _) in CRITERIA.items():
                    previous = c.evidence.get(key, {})
                    text = st.text_area(label, value=previous.get('text', ''), key=f'edit_text_{c.id}_{key}')
                    columns = st.columns(3)
                    level = columns[0].selectbox('Nivå', [1, 2, 3], index=previous.get('level', 1) - 1, key=f'edit_level_{c.id}_{key}')
                    confidence = columns[1].selectbox('Säkerhet', ['Låg', 'Medel', 'Hög'], index=['Låg', 'Medel', 'Hög'].index(previous.get('confidence', 'Låg')), key=f'edit_confidence_{c.id}_{key}')
                    source = columns[2].text_input('Källa', previous.get('source', ''), key=f'edit_source_{c.id}_{key}')
                    if text.strip():
                        edited_evidence[key] = dict(text=text, level=level, confidence=confidence, source=source or edited_url)
                edit_verified = st.checkbox('Jag har verifierat profilen och beläggen mot källorna', value=not c.discovery)
                if st.form_submit_button('Spara yrkesunderlag'):
                    try:
                        updated = Candidate(**{**c.to_dict(), 'name': edited_name, 'city': edited_city,
                            'role': edited_role, 'company': edited_company, 'education': edited_education,
                            'source_url': edited_url, 'description': edited_description,
                            'years': edited_years if edited_years_known else None,
                            'consultant': edited_consultant, 'evidence': edited_evidence, 'discovery': not edit_verified})
                        store.save(updated)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except sqlite3.IntegrityError:
                        st.error('En annan profil använder redan källänken. Granska dubbletten innan du fortsätter.')
        with st.form(f'review_{c.id}'):
            new_status = st.selectbox('Granskningsstatus', ['Osäker', 'Intressant', 'Granskad'], index=['Osäker', 'Intressant', 'Granskad'].index(c.status))
            notes = st.text_area('Egna anteckningar – endast nödvändiga yrkesuppgifter', value=c.notes)
            verified = st.checkbox('Jag har verifierat identitet och yrkesuppgifter i källan', value=not c.discovery)
            if st.form_submit_button('Spara granskning'):
                c.status, c.notes = new_status, notes
                c.discovery = not verified
                store.save(c)
                st.success('Granskningen sparad.')
        st.caption('Komplettera verifierade belägg i formuläret ovan. Dubbletter skrivs aldrig över vid import.')
        confirm = st.checkbox('Bekräfta permanent radering av den här profilen', key=f'delete_{c.id}')
        if st.button('Radera kandidatuppgifter', disabled=not confirm):
            store.delete(c.id)
            st.rerun()
