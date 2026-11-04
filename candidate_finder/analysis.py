from .model import CRITERIA, UNKNOWN


def categories(c):
    if c.discovery:
        return ['D']
    result = []
    if c.consultant:
        result.append('B')
    if c.years is not None and 3 <= c.years <= 5 and 'responsibility' in c.evidence:
        result.append('C')
    if 'change' in c.evidence and not c.consultant:
        result.append('A')
    return result or ['D']


def analyze(c):
    rows, score, known = [], 0, 0
    for key, (label, weight) in CRITERIA.items():
        e = None if c.discovery else c.evidence.get(key)
        if e:
            score += e['level'] * weight
            known += weight
        rows.append({'Kriterium': label, 'Vikt': weight,
                     'Belägg / relevant erfarenhet': e['text'] if e else UNKNOWN,
                     'Nivå (1–3)': e['level'] if e else None,
                     'Säkerhet': e.get('confidence', 'Låg') if e else UNKNOWN,
                     'Källa': e.get('source', c.source_url) if e else ''})
    return {'criteria': rows, 'priority': round(score / 39 * 100),
            'coverage': round(known / 13 * 100), 'categories': categories(c),
            'missing': [r['Kriterium'] for r in rows if r['Nivå (1–3)'] is None]}


class OptionalAnalyzer:
    """Extension point for a licensed AI provider. Never called by the MVP.

    Implementations must require explicit data-sharing authorization and return
    sourced evidence for human review; they must not infer protected attributes.
    """
    def analyze(self, candidate, *, authorized=False):
        raise NotImplementedError('Ingen AI-leverantör är aktiverad.')
