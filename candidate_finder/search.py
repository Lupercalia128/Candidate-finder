import os
from typing import Protocol
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
    return [f'"{role}" {city} {keywords}'.strip() for city in PLACES[place] for role in roles]

class SearchProvider(Protocol):
    def search(self, queries: list[str], limit: int) -> list[Candidate]: ...

class BraveSearch:
    """Search snippets only. Does not fetch or scrape discovered profile pages."""
    def search(self, queries, limit):
        key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not key:
            raise ValueError('BRAVE_SEARCH_API_KEY saknas. Använd CSV eller manuell inmatning utan nyckel.')
        found = {}
        for query in queries:
            response = requests.get('https://api.search.brave.com/res/v1/web/search',
                headers={'X-Subscription-Token': key, 'Accept': 'application/json'},
                params={'q': query, 'count': min(limit - len(found), 20), 'country': 'SE'}, timeout=25)
            response.raise_for_status()
            for hit in response.json().get('web', {}).get('results', []):
                try:
                    c = Candidate(name=hit['title'], source_url=hit['url'], description=hit.get('description', ''), discovery=True).validate()
                except (ValueError, KeyError):
                    continue
                found[c.identity()] = c
                if len(found) >= limit:
                    return list(found.values())
        return list(found.values())
