"""Role-filtered BM25 search over a persisted inverted index, with source extraction."""
from collections import Counter
import math
import re

STOP = set('a an the to and or for of is it in my me with this that please can could would should need have has not how do i what where when we our your'.split())


def tokens(value):
    words = re.findall(r'[a-z0-9]+', value.lower().replace('wi-fi', 'wifi'))
    # Small normalization preserves meaningful domain terms and makes plurals searchable.
    return [w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w for w in words if w not in STOP]


def index_documents(db):
    db.execute('DELETE FROM postings')
    for row in db.execute('SELECT id,title,body FROM knowledge').fetchall():
        doc_id, title, body = row
        frequencies = Counter(tokens(body))
        for term, count in Counter(tokens(title)).items():
            frequencies[term] += count * 2
        db.execute('UPDATE knowledge SET length=? WHERE id=?', (sum(frequencies.values()), doc_id))
        db.executemany('INSERT INTO postings(term,document_id,frequency) VALUES (?,?,?)', [(term, doc_id, count) for term, count in frequencies.items()])


def search(db, query, role, limit=4):
    # The visible corpus supplies N, average length, document frequency AND candidates.
    # Hidden documents never influence ranking statistics or returned snippets.
    rows = db.execute("SELECT id,title,body,department,visibility,updated,length FROM knowledge WHERE visibility='all' OR ?='staff'", (role,)).fetchall()
    docs = {r[0]: dict(zip(('id','title','body','department','visibility','updated','length'), r)) for r in rows}
    if not docs:
        return []
    terms = set(tokens(query))
    avg_length = sum(d['length'] for d in docs.values()) / len(docs) or 1
    scores, matched = {}, {}
    for term in terms:
        postings = [(doc_id, tf) for doc_id, tf in db.execute('SELECT document_id,frequency FROM postings WHERE term=?', (term,)) if doc_id in docs]
        idf = math.log(1 + (len(docs) - len(postings) + .5) / (len(postings) + .5))
        for doc_id, tf in postings:
            denominator = tf + 1.5 * (1 - .75 + .75 * docs[doc_id]['length'] / avg_length)
            scores[doc_id] = scores.get(doc_id, 0) + idf * tf * 2.5 / denominator
            matched.setdefault(doc_id, set()).add(term)
    results = []
    for doc_id in sorted(scores, key=lambda key: (-scores[key], key))[:limit]:
        doc = docs[doc_id]
        sentences = re.split(r'(?<=[.!?])\s+', doc['body'])
        problem_terms = terms & {'locked','fail','failed','incorrect','lost','fault','missed','correction'}
        excerpt = max(sentences, key=lambda s: (len(set(tokens(s)) & terms) + 2 * len(set(tokens(s)) & problem_terms), -len(s)))
        results.append({**doc, 'score': round(scores[doc_id], 4), 'matched_terms': sorted(matched[doc_id]), 'excerpt': excerpt})
    return results
