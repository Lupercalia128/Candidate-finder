import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .model import Candidate

class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('''CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, candidate):
        c = candidate.validate()
        with self.connect() as db:
            if c.id is None:
                cur = db.execute('INSERT OR IGNORE INTO candidates(identity,payload,created_at) VALUES(?,?,?)',
                                 (c.identity(), json.dumps(c.to_dict(), ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
                return cur.rowcount == 1
            db.execute('UPDATE candidates SET identity=?,payload=? WHERE id=?',
                       (c.identity(), json.dumps(c.to_dict(), ensure_ascii=False), c.id))
            return True

    def all(self):
        with self.connect() as db:
            result = []
            for id_, payload in db.execute('SELECT id,payload FROM candidates ORDER BY id'):
                data = json.loads(payload)
                data['id'] = id_
                result.append(Candidate(**data))
            return result

    def delete(self, id_):
        with self.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('DELETE FROM candidates WHERE id=?', (id_,))
