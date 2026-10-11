CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, document TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, department TEXT NOT NULL, visibility TEXT NOT NULL CHECK(visibility IN ('all','staff')), updated TEXT NOT NULL, length INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS postings (term TEXT NOT NULL, document_id TEXT NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE, frequency REAL NOT NULL, PRIMARY KEY(term, document_id));
CREATE INDEX IF NOT EXISTS postings_document ON postings(document_id);
