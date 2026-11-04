import os
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from html import unescape
import re
import time
import requests
from .model import Candidate

ROLES = {
    'A': ['Business Development Manager', 'Strategy Manager', 'Verksamhetsutvecklare', 'Förändringsledare', 'Transformation Manager'],
    'B': ['Management Consultant', 'Senior Consultant', 'Strategy Consultant', 'Engagement Manager'],
    'C': ['Projektledare', 'Business Consultant', 'Project Manager'],
    'D': ['Affärsutvecklare', 'Change Management'],
}
PLACES = {'Umeå': ['Umeå', 'Västerbotten'], 'Stockholm': ['Stockholm'], 'Sundsvall': ['Sundsvall'],
          'Övriga Norrland': ['Norrbotten', 'Jämtland', 'Västernorrland', 'Gävleborg'], 'Hela Sverige': ['Sweden', 'Sverige']}

def queries(place, category='Alla', keywords=''):
    roles = ROLES.get(category) or list(dict.fromkeys(r for values in ROLES.values() for r in values))
    return [f'site:linkedin.com/in/ "{role}" {city} {keywords}'.strip() for city in PLACES[place] for role in roles]

class SearchProvider(Protocol):
    def search(self, queries: list[str], limit: int) -> list[Candidate]: ...

def linkedin_profile_url(value):
    """Accept only personal LinkedIn profile paths, never lookalike domains."""
    p = urlsplit(value)
    host = (p.hostname or '').lower()
    if (p.scheme not in ('http', 'https') or p.username or p.password
            or not (host == 'linkedin.com' or host.endswith('.linkedin.com'))
            or not re.fullmatch(r'/in/[^/]+/?', p.path)):
        raise ValueError('Inte en personlig LinkedIn-profillänk.')
    return urlunsplit(('https', 'www.linkedin.com', p.path.rstrip('/'), '', ''))


def snippet_text(value):
    return unescape(re.sub(r'<[^>]+>', '', str(value))).strip()


class BraveSearch:
    """Discover public LinkedIn profile URLs through the licensed search API.

    Never requests LinkedIn itself. Discovery text is unverified and is never
    converted into qualifications. At most 30 API calls per search.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key

    def search(self, queries, limit):
        key = self.api_key or os.getenv('BRAVE_SEARCH_API_KEY')
        if not key:
            raise ValueError('API-nyckel saknas. Ange din Brave Search API-nyckel i sökfliken.')
        if not 1 <= limit <= 100:
            raise ValueError('Antal resultat måste vara 1–100.')
        found = {}
        pending = list(dict.fromkeys(queries))
        calls = 0
        # Round-robin across titles before asking for additional result pages.
        for offset in range(5):
            next_page = []
            for query in pending:
                if calls >= 30:
                    return list(found.values())
                if calls:
                    time.sleep(1.1)  # Respect entry-level API rate limits.
                response = requests.get('https://api.search.brave.com/res/v1/web/search',
                    headers={'X-Subscription-Token': key, 'Accept': 'application/json'},
                    params={'q': query, 'count': 20, 'offset': offset, 'country': 'SE'}, timeout=25)
                calls += 1
                response.raise_for_status()
                payload = response.json()
                for hit in payload.get('web', {}).get('results', []):
                    try:
                        url = linkedin_profile_url(hit['url'])
                        c = Candidate(name=snippet_text(hit['title']), source_url=url,
                                      description=snippet_text(hit.get('description', '')),
                                      discovery=True).validate()
                    except (ValueError, KeyError, TypeError):
                        continue
                    found[c.identity()] = c
                    if len(found) >= limit:
                        return list(found.values())
                if payload.get('query', {}).get('more_results_available', False):
                    next_page.append(query)
            pending = next_page
            if not pending:
                break
        return list(found.values())
