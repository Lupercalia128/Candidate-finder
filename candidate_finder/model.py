from dataclasses import dataclass, field, asdict
from urllib.parse import urlsplit, urlunsplit
import hashlib
import unicodedata

CRITERIA = {
    'change': ('Förändringsledning', 3),
    'customer': ('Kund- och relationsutveckling', 3),
    'analysis': ('Konsulthantverk och analytisk bredd', 2),
    'business': ('Affärsutveckling och merförsäljning', 2),
    'responsibility': ('Dokumenterat ansvar', 2),
    'industry': ('Relevant branscherfarenhet', 1),
}
UNKNOWN = 'Okänt – kräver manuell bedömning'

def safe_url(value):
    p = urlsplit(str(value).strip())
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('Källan måste vara en fullständig HTTP/HTTPS-länk utan inloggningsuppgifter.')
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), '', ''))

def norm(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())

@dataclass
class Candidate:
    name: str
    city: str = ''
    role: str = ''
    company: str = ''
    years: float | None = None
    education: str = ''
    source_url: str = ''
    description: str = ''
    consultant: bool = False
    evidence: dict = field(default_factory=dict)
    discovery: bool = False
    id: int | None = None
    status: str = 'Osäker'
    notes: str = ''

    def validate(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError('Namn eller sidtitel krävs.')
        self.source_url = safe_url(self.source_url)
        if self.years is not None and not 0 <= self.years <= 80:
            raise ValueError('Erfarenhet måste vara 0–80 år eller okänd.')
        if not isinstance(self.evidence, dict):
            raise ValueError('Belägg måste vara ett objekt.')
        for key, e in self.evidence.items():
            if key not in CRITERIA or not isinstance(e, dict):
                raise ValueError('Ogiltigt kriterium eller belägg.')
            if not str(e.get('text', '')).strip() or type(e.get('level')) is not int or e['level'] not in (1, 2, 3):
                raise ValueError('Varje belägg kräver text och nivå 1–3.')
            e['source'] = safe_url(e.get('source') or self.source_url)
            if e.get('confidence', 'Låg') not in ('Låg', 'Medel', 'Hög'):
                raise ValueError('Ogiltig säkerhetsnivå.')
        return self

    def identity(self):
        return hashlib.sha256(norm(self.source_url).encode()).hexdigest()

    def to_dict(self):
        return asdict(self)
