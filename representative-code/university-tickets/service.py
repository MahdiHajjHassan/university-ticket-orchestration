"""Independent service desk: SQLite storage, indexed retrieval and versioned staff actions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from orchestration import analyze
from retrieval import index_documents, search

ROOT = Path(__file__).resolve().parent
DIRECTORY = json.loads((ROOT / 'fixtures/directory.json').read_text(encoding='utf-8'))
SAMPLES = [
    {'title': 'Portal access', 'role': 'student', 'text': 'My course portal account is locked. The reset link fails and I need access restored.'},
    {'title': 'Find an answer', 'role': 'student', 'text': 'How do I reset my course portal password?'},
    {'title': 'Enrollment letter', 'role': 'student', 'text': 'I need an official enrollment letter for my scholarship application.'},
    {'title': 'Annual leave', 'role': 'staff', 'text': 'I need annual leave approval for October 20 to 22. My manager is Dana Ash.'},
    {'title': 'Needs triage', 'role': 'student', 'text': 'My portal account is locked and I also need an official enrollment letter.'},
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def value(data, name, minimum=2, maximum=2000):
    item = data.get(name)
    if not isinstance(item, str) or not minimum <= len(item.strip()) <= maximum:
        raise ValueError(f'{name.replace("_", " ").capitalize()} must contain {minimum} to {maximum} characters.')
    return item.strip()


@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


class Product:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / 'university-tickets.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connection(self.path) as db:
            db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
            db.execute("INSERT OR IGNORE INTO settings VALUES ('view','staff')")
            first = not db.execute("SELECT 1 FROM settings WHERE key='initialized'").fetchone()
            if first:
                for doc in json.loads((ROOT / 'fixtures/knowledge.json').read_text(encoding='utf-8')):
                    db.execute('INSERT INTO knowledge(id,title,body,department,visibility,updated) VALUES (?,?,?,?,?,?)', tuple(doc[k] for k in ('id','title','body','department','visibility','updated')))
                index_documents(db)
                db.execute("INSERT INTO settings VALUES ('indexed_at',?)", (now(),))
                db.execute("INSERT INTO settings VALUES ('initialized','yes')")
        if first:
            for requester, sample in zip(('Alex Rowan','Sara Vale','Adam Brook','Leila Stone'), (SAMPLES[0], SAMPLES[2], SAMPLES[3], SAMPLES[4])):
                self.action('submit', {'requester': requester, 'role': sample['role'], 'text': sample['text']})

    def state(self):
        with connection(self.path) as db:
            view = db.execute("SELECT value FROM settings WHERE key='view'").fetchone()[0]
            tickets = [json.loads(r[0]) for r in db.execute('SELECT document FROM tickets ORDER BY id DESC')]
            docs = [dict(zip(('id','title','body','department','visibility','updated'), r)) for r in db.execute("SELECT id,title,body,department,visibility,updated FROM knowledge WHERE visibility='all' OR ?='staff' ORDER BY id", (view,))]
            indexed_at = db.execute("SELECT value FROM settings WHERE key='indexed_at'").fetchone()[0]
            term_count = db.execute("SELECT COUNT(DISTINCT term) FROM postings JOIN knowledge ON postings.document_id=knowledge.id WHERE visibility='all' OR ?='staff'", (view,)).fetchone()[0]
        if view == 'student':
            tickets = [t for t in tickets if t['role'] == 'student']
        return {'view': view, 'tickets': tickets, 'knowledge': docs, 'directory': [p for p in DIRECTORY if view == 'staff' or 'student' in p['roles']], 'samples': [s for s in SAMPLES if view == 'staff' or s['role'] == 'student'], 'index': {'method': 'Role-filtered BM25 inverted index', 'documents': len(docs), 'terms': term_count, 'updated_at': indexed_at}, 'departments': sorted({p['department'] for p in DIRECTORY})}

    def action(self, name, payload):
        if not isinstance(payload, dict):
            raise ValueError('Provide an object payload.')
        with connection(self.path) as db:
            view = db.execute("SELECT value FROM settings WHERE key='view'").fetchone()[0]
            if name == 'view':
                target = payload.get('view')
                if target not in ('staff','student'):
                    raise ValueError('Choose a student or staff view.')
                db.execute("UPDATE settings SET value=? WHERE key='view'", (target,))
                return {'view': target}
            if name in ('search','submit'):
                role = payload.get('role', view)
                if role not in ('student','staff'):
                    raise ValueError('Choose a student or staff requester role.')
                if view == 'student' and role != 'student':
                    raise PermissionError('The student view can access only student knowledge and requests.')
                if name == 'search':
                    query = value(payload, 'query', 2, 500)
                    return {'results': search(db, query, role), 'role': role, 'query': query, 'method': 'Role-filtered indexed BM25 (k1=1.5, b=0.75; title weight 2)'}
                request = value(payload, 'text', 5, 4000)
                requester = value(payload, 'requester', 2, 80)
                stamp = now()
                result = analyze(request, role, search(db, request, role), DIRECTORY, stamp)
                ticket = {'requester': requester, 'role': role, 'text': request, 'title': request.split('. ')[0][:90], 'created_at': stamp, 'updated_at': stamp, 'version': 1, 'resolution': None, 'notes': [], **result}
                row = db.execute('INSERT INTO tickets(document) VALUES (?)', (json.dumps(ticket),))
                ticket['id'], ticket['reference'] = row.lastrowid, f'UT-{row.lastrowid:04}'
                db.execute('UPDATE tickets SET document=? WHERE id=?', (json.dumps(ticket), ticket['id']))
                return {'ticket': ticket}
            if name == 'export':
                ticket = self._ticket(db, payload.get('ticket_id'))
                if view == 'student' and ticket['role'] != 'student':
                    raise PermissionError('This request is outside the student view.')
                return {'content': json.dumps(ticket, indent=2), 'filename': ticket['reference'] + '.json', 'mime': 'application/json'}
            if view != 'staff':
                raise PermissionError('Switch to the staff service desk to perform this action.')
            if name == 'knowledge_add':
                title, body = value(payload, 'title', 5, 120), value(payload, 'body', 20, 5000)
                visibility = payload.get('visibility')
                department = payload.get('department')
                if visibility not in ('all','staff') or department not in {p['department'] for p in DIRECTORY}:
                    raise ValueError('Choose a valid visibility and directory department.')
                identifier = f'KB-{300 + db.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]}'
                db.execute('INSERT INTO knowledge(id,title,body,department,visibility,updated) VALUES (?,?,?,?,?,?)', (identifier,title,body,department,visibility,now()[:10]))
                index_documents(db)
                db.execute("UPDATE settings SET value=? WHERE key='indexed_at'", (now(),))
                return {'id': identifier, 'title': title}
            if name == 'reindex':
                index_documents(db)
                stamp = now()
                db.execute("UPDATE settings SET value=? WHERE key='indexed_at'", (stamp,))
                return {'indexed_at': stamp, 'documents': db.execute('SELECT COUNT(*) FROM knowledge').fetchone()[0]}
            if name not in ('assign','resolve','note','escalate'):
                raise ValueError('Unknown service desk action.')
            db.execute('BEGIN IMMEDIATE')
            ticket = self._ticket(db, payload.get('ticket_id'))
            actor = next((p for p in DIRECTORY if p['id'] == payload.get('actor')), None)
            if not actor or (actor['id'] != 'coordinator' and actor['id'] != ticket['assignee_id']):
                raise PermissionError('Only the assigned staff member or coordinator can manage this ticket.')
            if type(payload.get('version')) is not int or payload['version'] != ticket['version']:
                raise RuntimeError('This ticket changed. Refresh the inbox before saving.')
            if ticket['status'] == 'resolved':
                raise RuntimeError('This ticket has already been resolved.')
            note = value(payload, 'note', 5, 2000)
            if name == 'assign':
                person = next((p for p in DIRECTORY if p['id'] == payload.get('assignee_id') and p['id'] != 'coordinator'), None)
                if not person or ticket['role'] not in person['roles']:
                    raise PermissionError('Choose an eligible person from the service directory.')
                if actor['id'] != 'coordinator' and actor['department'] != person['department']:
                    raise PermissionError('Cross-department assignment requires the coordinator.')
                ticket.update({'status':'assigned', 'path':'workflow', 'department':person['department'], 'assignee_id':person['id'], 'assignee':person['name']})
                stage, detail = 'Staff assignment', f"{actor['name']} assigned {person['name']} in {person['department']}: {note}"
            elif name == 'resolve':
                if ticket['status'] != 'assigned':
                    raise RuntimeError('Assign a responsible staff member before resolving this ticket.')
                ticket.update({'status':'resolved', 'resolution': {'by':actor['name'], 'note':note, 'at':now()}})
                stage, detail = 'Resolution', f"{actor['name']} resolved the request: {note}"
            elif name == 'escalate':
                if ticket['status'] != 'answered':
                    raise RuntimeError('Only a knowledge answer can be escalated.')
                ticket.update({'path':'workflow','status':'triage','department':'Human Triage'})
                stage, detail = 'Escalation', f"{actor['name']} requested staff follow-up: {note}"
            else:
                stage, detail = 'Staff note', f"{actor['name']}: {note}"
                ticket['notes'].append({'by':actor['name'],'note':note,'at':now()})
            ticket['version'] += 1
            ticket['updated_at'] = now()
            ticket['trace'].append({'stage':stage,'detail':detail,'at':ticket['updated_at']})
            db.execute('UPDATE tickets SET document=? WHERE id=?', (json.dumps(ticket),ticket['id']))
            return {'ticket': ticket}

    @staticmethod
    def _ticket(db, identifier):
        if type(identifier) is not int or identifier < 1:
            raise ValueError('Choose a valid ticket ID.')
        row = db.execute('SELECT document FROM tickets WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise ValueError('The ticket does not exist.')
        return json.loads(row[0])
