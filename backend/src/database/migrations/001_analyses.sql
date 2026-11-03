CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  uploaded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  status TEXT NOT NULL CHECK(status IN ('pending','processing','completed','failed')),
  duration_seconds REAL, error TEXT,
  summary TEXT NOT NULL DEFAULT '{}', capabilities TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS analyses_user ON analyses(user_id, uploaded_at);
CREATE TABLE IF NOT EXISTS analysis_entities (
  analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('subjects','connections','fingerprints','relationships','anomalies')),
  id TEXT NOT NULL, data TEXT NOT NULL,
  PRIMARY KEY(analysis_id, kind, id)
);
CREATE TABLE IF NOT EXISTS analysis_status_events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS analysis_events ON analysis_status_events(analysis_id, sequence);
CREATE TRIGGER IF NOT EXISTS analysis_created AFTER INSERT ON analyses BEGIN
  INSERT INTO analysis_status_events(analysis_id,status) VALUES(NEW.id,NEW.status);
END;
CREATE TRIGGER IF NOT EXISTS analysis_status_changed AFTER UPDATE OF status ON analyses
WHEN OLD.status != NEW.status BEGIN
  INSERT INTO analysis_status_events(analysis_id,status) VALUES(NEW.id,NEW.status);
END;
PRAGMA user_version = 1;
