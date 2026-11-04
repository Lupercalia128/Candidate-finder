import io
import json
import pandas as pd
from .model import Candidate

FIELDS = ['name', 'city', 'role', 'company', 'years', 'education', 'source_url', 'description', 'consultant', 'evidence', 'discovery']

def read_csv(source):
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    if not {'name', 'source_url'}.issubset(frame.columns):
        raise ValueError('CSV måste innehålla name och source_url.')
    candidates, errors = [], []
    for number, row in enumerate(frame.to_dict('records'), start=2):
        try:
            data = {k: v for k, v in row.items() if k in FIELDS}
            data['years'] = float(data['years']) if data.get('years') else None
            for k in ('consultant', 'discovery'):
                raw = data.get(k, '').lower()
                if raw not in ('', 'false', 'true', '0', '1'):
                    raise ValueError(f'{k} måste vara true/false.')
                data[k] = raw in ('true', '1')
            data['evidence'] = json.loads(data.get('evidence') or '{}')
            candidates.append(Candidate(**data).validate())
        except (ValueError, TypeError) as exc:
            errors.append(f'Rad {number}: {exc}')
    return candidates, errors


def export_frame(candidates):
    from .analysis import analyze
    rows = []
    for c in candidates:
        a = analyze(c)
        row = c.to_dict()
        row['evidence'] = json.dumps(c.evidence, ensure_ascii=False)
        row.update(category=', '.join(a['categories']), priority=a['priority'], coverage=a['coverage'])
        # Prevent formula execution when opening user-supplied content in spreadsheets.
        rows.append({k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v) for k, v in row.items()})
    return pd.DataFrame(rows)


def excel_bytes(frame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, sheet_name='Kandidater')
    return output.getvalue()
